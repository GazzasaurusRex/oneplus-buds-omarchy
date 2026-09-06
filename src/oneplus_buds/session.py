from __future__ import annotations

from time import monotonic

from .bluez import Device
from .models import ControlResult, EventBatch, SafeEvent
from .timing import AncRequestError, PhaseTimer
from .profiles import DeviceProfile
from .protocol import (
    HELLO,
    NOTIFY_STATE,
    QUERY_BROADCAST_CODES,
    QUERY_CAPABILITIES,
    QUERY_ANC,
    SET_ANC,
    RESPONSE_SET_ANC,
    REGISTER,
    RESPONSE_ANC,
    RESPONSE_BATTERY,
    RESPONSE_STATUS,
    SUBSCRIBE_BROADCAST,
    Frame,
    FEATURE_SWITCH_NAMES,
    parse_anc_state,
    parse_battery,
    parse_broadcast_codes,
    parse_feature_switches,
    parse_set_anc_status,
)
from .transport import RfcommTransport


class OpoSession:
    def __init__(self, device: Device, profile: DeviceProfile) -> None:
        self.device = device
        self.profile = profile
        self._transport = RfcommTransport(device.address, connect_attempts=4)
        self._connected = False
        self._authenticated = False
        self.advertised_event_codes: tuple[int, ...] = ()

    def __enter__(self) -> "OpoSession":
        self._transport.__enter__()
        self._connected = True
        return self

    def __exit__(self, *args: object) -> None:
        self._connected = False
        self._authenticated = False
        self._transport.__exit__(*args)

    def authenticate_and_subscribe(self) -> EventBatch:
        self._require_connected()
        frames: list[Frame] = []
        frames.extend(self._transport.query(QUERY_CAPABILITIES))
        frames.extend(self._transport.exchange_raw(HELLO, wait=2.0))
        frames.extend(self._transport.exchange_raw(REGISTER, wait=1.5))
        advertised_frames = self._transport.query(QUERY_BROADCAST_CODES, wait=0.5)
        frames.extend(advertised_frames)
        advertised = next(
            (codes for frame in advertised_frames if (codes := parse_broadcast_codes(frame)) is not None),
            b"",
        )
        self.advertised_event_codes = tuple(advertised)
        if advertised:
            payload = bytes((len(advertised),)) + advertised
            frames.extend(self._transport.query(SUBSCRIBE_BROADCAST, payload, wait=0.5))
        self._authenticated = True
        return self._redact(frames)

    def set_anc(self, mode: str) -> tuple[ControlResult, EventBatch]:
        """Reuse authentication; verify with a fresh, correlated state query.

        Notifications and SET status alone are never proof of the new state.
        The caller discards a failed transaction's session before recovery.
        """
        self._require_connected()
        if not self._authenticated:
            raise RuntimeError("session authentication has not completed")
        if not self.profile.verified or mode not in self.profile.anc.write_indices:
            raise ValueError("ANC mode is not supported by a verified profile")
        timer = PhaseTimer()
        events: list[SafeEvent] = []
        ignored = 0

        def collect(frames: list[Frame]) -> None:
            nonlocal ignored
            batch = self._redact(frames)
            events.extend(batch.events)
            # Keep memory bounded even if the peer floods notifications.
            del events[:-64]
            ignored += batch.ignored_frames

        try:
            try:
                acknowledgement = self._transport.request(
                    SET_ANC, self.profile.anc.payload_for(mode), RESPONSE_SET_ANC,
                    sequence=self.profile.anc.sequence_for(mode),
                    on_sent=lambda: timer.elapsed("command_sent_elapsed"), on_frames=collect,
                )
            except TimeoutError:
                # Some firmware omits SET acknowledgement. Never replay SET;
                # a fresh query is still the only success criterion.
                acknowledgement = None
            timer.mark("set_response")
            expected_mode = mode if mode in ("off", "transparency", "on") else "on"
            expected_level = None if mode in ("off", "transparency", "on") else mode
            # SET acknowledgement can precede physical application. A first
            # fresh query may legitimately return the previous mode. Re-query
            # on each response, bounded by both time and count; never replay SET.
            observed = None
            deadline = monotonic() + 2.0
            for query_count in range(1, 33):
                remaining = deadline - monotonic()
                if remaining <= 0:
                    break
                state = self._transport.request(
                    QUERY_ANC, b"\x01\x01", RESPONSE_ANC, on_frames=collect,
                    timeout=remaining,
                )
                observed = parse_anc_state(state, self.profile.anc) if state.payload[:1] == b"\x00" else None
                if observed is not None and observed.mode == expected_mode and (
                    expected_level is None or observed.level == expected_level
                ):
                    break
            else:
                observed = None
            timer.mark("verify_query")
            if observed is None or observed.mode != expected_mode or (
                expected_level is not None and observed.level != expected_level
            ):
                raise RuntimeError("ANC verification failed: fresh state did not match request")
            timer.elapsed("verified_elapsed")
            result = ControlResult(
                name=self.device.name, product_id=self.profile.product_id,
                anc=observed.mode, anc_level=observed.level,
                set_status=parse_set_anc_status(acknowledgement) if acknowledgement else None,
                verified=True,
                timings_ms=timer.finish("session_total"),
                verification_queries=query_count,
            )
            return result, EventBatch(tuple(events), ignored)
        except (OSError, RuntimeError, ValueError) as error:
            timer.mark("failed_phase")
            raise AncRequestError("ANC session request failed: " + str(error),
                                  timer.finish("session_total")) from error

    def poll(self, wait: float = 0.2) -> EventBatch:
        self._require_connected()
        return self._redact(self._transport.receive(wait))

    def _redact(self, frames: list[Frame]) -> EventBatch:
        events: list[SafeEvent] = []
        ignored = 0
        for frame in frames:
            event = self._safe_event(frame)
            if event is None:
                ignored += 1
            else:
                events.append(event)
        return EventBatch(tuple(events), ignored)

    def _safe_event(self, frame: Frame) -> SafeEvent | None:
        if frame.command == RESPONSE_BATTERY:
            battery = parse_battery(frame)
            return SafeEvent("battery", battery) if battery is not None else None
        if frame.command == RESPONSE_ANC:
            state = parse_anc_state(frame, self.profile.anc)
            if state is not None:
                return SafeEvent("anc", {"mode": state.mode, "level": state.level})
            return None
        if frame.command == RESPONSE_STATUS:
            switches = parse_feature_switches(frame)
            if switches is None:
                return None
            named = {
                name: switches[feature]
                for feature, name in FEATURE_SWITCH_NAMES.items()
                if feature in switches
            }
            return SafeEvent("feature_switches", named)
        if frame.command == NOTIFY_STATE and frame.payload:
            return SafeEvent("notification", {"event_code": frame.payload[0]})
        return None

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("session is not connected")
