from __future__ import annotations

from dataclasses import asdict
from time import monotonic

from .bluez import Device
from .lifecycle_trace import mark, span
from .models import ControlResult, EqControlResult, EqStatusResult, EventBatch, SafeEvent, StatusResult
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
    QUERY_EQ,
    QUERY_EQ_ALL,
    SET_ANC,
    SET_EQ,
    SET_EQ_DETAIL,
    RESPONSE_SET_ANC,
    REGISTER,
    RESPONSE_ANC,
    RESPONSE_EQ,
    RESPONSE_EQ_ALL,
    RESPONSE_SET_EQ,
    RESPONSE_SET_EQ_DETAIL,
    RESPONSE_BATTERY,
    RESPONSE_STATUS,
    SUBSCRIBE_BROADCAST,
    Frame,
    FEATURE_SWITCH_NAMES,
    EQ_ALL_QUERY_PAYLOAD,
    EqEntry,
    encode_eq_detail_payload,
    parse_anc_state,
    parse_battery,
    parse_broadcast_codes,
    parse_eq_entries,
    parse_eq_id,
    parse_feature_switches,
    parse_set_anc_status,
    parse_set_eq_status,
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

    def eq_status(self) -> tuple[EqStatusResult, EventBatch]:
        self._require_eq_session(write=False)
        frames: list[Frame] = []
        current_frame = self._transport.request(
            QUERY_EQ, b"", RESPONSE_EQ, on_frames=frames.extend,
        )
        entries_frame = self._transport.request(
            QUERY_EQ_ALL, EQ_ALL_QUERY_PAYLOAD, RESPONSE_EQ_ALL, on_frames=frames.extend,
        )
        current_id = parse_eq_id(current_frame)
        entries = parse_eq_entries(entries_frame)
        if current_id is None or entries is None:
            raise RuntimeError("device returned malformed native EQ state")
        return self._eq_result(current_id, entries), self._redact(frames)

    def set_eq(self, preset: str) -> tuple[EqControlResult, EventBatch]:
        """Select one native EQ entry once, then verify with fresh device state."""
        self._require_eq_session(write=True)
        timer = PhaseTimer()
        before, initial = self.eq_status()
        timer.mark("preserve_read")
        target_id, target_name = self._resolve_eq_target(preset, before)
        events = list(initial.events)
        ignored = initial.ignored_frames

        def collect(frames: list[Frame]) -> None:
            nonlocal ignored
            batch = self._redact(frames)
            events.extend(batch.events)
            del events[:-64]
            ignored += batch.ignored_frames

        try:
            try:
                acknowledgement = self._transport.request(
                    SET_EQ, bytes((target_id,)), RESPONSE_SET_EQ,
                    on_sent=lambda: timer.elapsed("command_sent_elapsed"), on_frames=collect,
                )
            except TimeoutError:
                acknowledgement = None
            timer.mark("set_response")
            observed_id = None
            deadline = monotonic() + 2.0
            for query_count in range(1, 33):
                remaining = deadline - monotonic()
                if remaining <= 0:
                    break
                frame = self._transport.request(
                    QUERY_EQ, b"", RESPONSE_EQ, on_frames=collect, timeout=remaining,
                )
                observed_id = parse_eq_id(frame)
                if observed_id == target_id:
                    break
            timer.mark("verify_query")
            if observed_id != target_id:
                raise RuntimeError("EQ verification failed: fresh state did not match request")
            # Re-read the device-authored catalogue. This independently proves
            # custom definitions were not overwritten by a preset selection.
            verified, batch = self.eq_status()
            events.extend(batch.events)
            ignored += batch.ignored_frames
            if verified.current_id != target_id:
                raise RuntimeError("EQ verification failed: catalogue state did not match request")
            timer.elapsed("verified_elapsed")
            return EqControlResult(
                self.device.name, self.profile.product_id, target_id, target_name,
                before.current_id, before.current_name,
                parse_set_eq_status(acknowledgement) if acknowledgement else None,
                True, timer.finish("session_total"), query_count,
            ), EventBatch(tuple(events), ignored)
        except (OSError, RuntimeError) as error:
            raise RuntimeError("EQ session request failed: " + str(error)) from error

    def set_custom_eq(self, entry_id: int, gains_db: tuple[int, ...]) -> tuple[EqControlResult, EventBatch]:
        """Update an existing device-declared custom curve; never invent a layout."""
        self._require_eq_session(write=True)
        if self.profile.eq is None or not self.profile.eq.custom_write_verified:
            raise ValueError("custom EQ writes are not hardware-verified for this device profile")
        timer = PhaseTimer()
        before, initial = self.eq_status()
        timer.mark("preserve_read")
        entry = next((item for item in before.custom_entries if item.eq_id == entry_id), None)
        if entry is None:
            raise ValueError("custom EQ id was not declared by the connected earbuds")
        payload = encode_eq_detail_payload(entry, gains_db)
        events = list(initial.events)
        ignored = initial.ignored_frames

        def collect(frames: list[Frame]) -> None:
            nonlocal ignored
            batch = self._redact(frames)
            events.extend(batch.events)
            del events[:-64]
            ignored += batch.ignored_frames

        try:
            try:
                acknowledgement = self._transport.request(
                    SET_EQ_DETAIL, payload, RESPONSE_SET_EQ_DETAIL,
                    on_sent=lambda: timer.elapsed("command_sent_elapsed"), on_frames=collect,
                )
            except TimeoutError:
                acknowledgement = None
            timer.mark("set_response")
            verified = None
            deadline = monotonic() + 2.0
            for query_count in range(1, 33):
                remaining = deadline - monotonic()
                if remaining <= 0:
                    break
                frame = self._transport.request(
                    QUERY_EQ_ALL, EQ_ALL_QUERY_PAYLOAD, RESPONSE_EQ_ALL,
                    on_frames=collect, timeout=remaining,
                )
                entries = parse_eq_entries(frame)
                verified = next((item for item in entries or () if item.eq_id == entry_id), None)
                if verified is not None and tuple(band.gain_db for band in verified.bands) == gains_db:
                    break
            timer.mark("verify_query")
            if verified is None or tuple(band.gain_db for band in verified.bands) != gains_db:
                raise RuntimeError("custom EQ verification failed: fresh curve did not match request")
            current = self._transport.request(QUERY_EQ, b"", RESPONSE_EQ, on_frames=collect)
            current_id = parse_eq_id(current)
            if current_id != entry_id:
                raise RuntimeError("custom EQ verification failed: updated entry is not selected")
            timer.elapsed("verified_elapsed")
            return EqControlResult(
                self.device.name, self.profile.product_id, entry_id, verified.name,
                before.current_id, before.current_name,
                parse_set_eq_status(acknowledgement) if acknowledgement else None,
                True, timer.finish("session_total"), query_count,
            ), EventBatch(tuple(events), ignored)
        except (OSError, RuntimeError) as error:
            raise RuntimeError("custom EQ session request failed: " + str(error)) from error

    def _require_eq_session(self, *, write: bool) -> None:
        self._require_connected()
        if not self._authenticated:
            raise RuntimeError("session authentication has not completed")
        if self.profile.eq is None:
            raise ValueError("native EQ is not supported by this device profile")
        if write and (not self.profile.verified or not self.profile.eq.write_verified):
            raise ValueError("native EQ writes are not hardware-verified for this device profile")

    def _eq_result(self, current_id: int, entries: tuple[EqEntry, ...]) -> EqStatusResult:
        eq = self.profile.eq
        if eq is None:
            raise ValueError("native EQ is not supported by this device profile")
        preset = next((item for item in eq.presets if item.eq_id == current_id), None)
        custom = next((item for item in entries if item.eq_id == current_id), None)
        if preset is not None:
            current_name, current_kind = preset.name, "factory"
        elif custom is not None:
            current_name, current_kind = custom.name, "custom"
        else:
            current_name, current_kind = f"Unknown ({current_id})", "unknown"
        presets = tuple({"id": item.eq_id, "key": item.key, "name": item.name}
                        for item in eq.presets)
        return EqStatusResult(
            self.device.name, self.profile.product_id, self.profile.name,
            current_id, current_name, current_kind, presets, entries,
            1 if entries else None,
        )

    def _resolve_eq_target(self, value: str, status: EqStatusResult) -> tuple[int, str]:
        eq = self.profile.eq
        if eq is None:
            raise ValueError("native EQ is not supported by this device profile")
        preset = eq.preset_for(value)
        if preset is not None:
            return preset.eq_id, preset.name
        normalized = value.strip().lower()
        for entry in status.custom_entries:
            if normalized in (f"custom:{entry.eq_id}", entry.name.lower()):
                return entry.eq_id, entry.name
        raise ValueError("EQ target is not a verified preset or device-declared custom entry")

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
        if (eq_id := parse_eq_id(frame)) is not None:
            return SafeEvent("eq_changed", {"id": eq_id})
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
