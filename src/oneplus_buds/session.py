from __future__ import annotations

from dataclasses import asdict
from time import monotonic

from .bluez import Device
from .lifecycle_trace import mark, span
from .models import ControlResult, EventBatch, SafeEvent, StatusResult
from .timing import AncRequestError, PhaseTimer
from .profiles import DeviceProfile, profile_for_product
from .protocol import (
    HELLO,
    NOTIFY_STATE,
    QUERY_BROADCAST_CODES,
    QUERY_CAPABILITIES,
    QUERY_PRODUCT_ID,
    QUERY_BATTERY,
    QUERY_REMOTE_VERSION,
    RESPONSE_PRODUCT_ID,
    RESPONSE_REMOTE_VERSION,
    parse_product_id,
    parse_remote_version,
    format_firmware_version,
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
    def __init__(self, device: Device, profile: DeviceProfile,
                 *, transport: RfcommTransport | None = None) -> None:
        self.device = device
        self.profile = profile
        self._transport = transport or RfcommTransport(device.address, connect_attempts=4)
        self._version_pending = False
        self._version_sequence: int | None = None
        self._subscription_pending = False
        self._connected = False
        self._authenticated = False
        self.advertised_event_codes: tuple[int, ...] = ()

    @classmethod
    def bootstrap(cls, device: Device) -> tuple["OpoSession", StatusResult, EventBatch]:
        """Identify, authenticate and read essential state on one owned socket."""
        transport = RfcommTransport(device.address, connect_attempts=4)
        transport.__enter__()
        try:
            # Preserve the existing capability primer and authentication waits.
            transport.query(QUERY_CAPABILITIES)
            with span("query", command=QUERY_PRODUCT_ID):
                product = parse_product_id(transport.request(
                    QUERY_PRODUCT_ID, b"", RESPONSE_PRODUCT_ID))
            profile = profile_for_product(product)
            if profile is None:
                raise RuntimeError("cannot open event session for an unknown product")
            mark("profile_resolved", product_id=product)
            session = cls(device, profile, transport=transport)
            session._connected = True
            initial = session.authenticate(primed=True)
            received: list[Frame] = []
            with span("query", command=QUERY_BATTERY):
                battery = parse_battery(transport.request(
                    QUERY_BATTERY, b"", RESPONSE_BATTERY, on_frames=received.extend))
            with span("query", command=QUERY_ANC):
                anc = parse_anc_state(transport.request(
                    QUERY_ANC, b"\x01\x01", RESPONSE_ANC, on_frames=received.extend), profile.anc)
            if battery is None or anc is None:
                raise RuntimeError("essential device state is not available")
            status = StatusResult(device=device, product_id=product, model=profile.name,
                remote_version=(), firmware_version=None, battery=battery,
                anc=anc.mode, anc_level=anc.level)
            # Essential query responses are newer than setup notifications.
            extra = session._redact(received)
            events = tuple(event for event in initial.events + extra.events
                           if event.kind not in ("battery", "anc"))
            session._version_pending = True
            session._subscription_pending = True
            return session, status, EventBatch(events, initial.ignored_frames + extra.ignored_frames)
        except BaseException:
            transport.__exit__(None, None, None)
            raise

    def __enter__(self) -> "OpoSession":
        self._transport.__enter__()
        self._connected = True
        return self

    def __exit__(self, *args: object) -> None:
        self._connected = False
        self._authenticated = False
        self._transport.__exit__(*args)

    def authenticate_and_subscribe(self, *, primed: bool = False) -> EventBatch:
        authenticated = self.authenticate(primed=primed)
        subscribed = self._subscribe()
        return EventBatch(
            authenticated.events + subscribed.events,
            authenticated.ignored_frames + subscribed.ignored_frames,
        )

    def authenticate(self, *, primed: bool = False) -> EventBatch:
        mark("authentication.begin")
        self._require_connected()
        frames: list[Frame] = []
        if not primed:
            frames.extend(self._transport.query(QUERY_CAPABILITIES))
        frames.extend(self._transport.exchange_raw(HELLO, wait=2.0))
        frames.extend(self._transport.exchange_raw(REGISTER, wait=1.5))
        self._authenticated = True
        mark("authentication.end")
        return self._redact(frames)

    def _subscribe(self) -> EventBatch:
        self._require_connected()
        if not self._authenticated:
            raise RuntimeError("session authentication has not completed")
        mark("subscription.begin")
        frames: list[Frame] = []
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
        mark("subscription.end")
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
        setup = EventBatch((), 0)
        if self._subscription_pending:
            self._subscription_pending = False
            setup = self._subscribe()
        if self._version_pending:
            self._version_pending = False
            self._version_sequence = self._transport.send_query(QUERY_REMOTE_VERSION)
            mark("optional_firmware_sent")
        received = self._redact(self._transport.receive(wait))
        return EventBatch(
            setup.events + received.events,
            setup.ignored_frames + received.ignored_frames,
        )

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
        if (frame.command == RESPONSE_REMOTE_VERSION
                and self._version_sequence is not None
                and frame.sequence == self._version_sequence):
            records = parse_remote_version(frame)
            if records is not None:
                self._version_sequence = None
                mark("optional_firmware_received")
                return SafeEvent("firmware", {"records": [asdict(record) for record in records],
                    "version": format_firmware_version(records)})
            return None
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
