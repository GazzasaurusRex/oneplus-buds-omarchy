from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from time import monotonic

from .bluez import Device
from .lifecycle_trace import mark, span
from .models import ControlResult, EqControlResult, EqStatusResult, EventBatch, SafeEvent, StatusResult
from .timing import AncRequestError, PhaseTimer
from .profiles import DeviceProfile, WriteOperation, profile_for_product
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
    AncState,
    FEATURE_SWITCH_NAMES,
    EQ_ALL_QUERY_PAYLOAD,
    EqBand,
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
from .protocol import (
    QUERY_TOUCH, RESPONSE_TOUCH, SET_TOUCH, RESPONSE_SET_TOUCH,
    QUERY_STATUS, SET_FEATURE_SWITCH, RESPONSE_SET_FEATURE_SWITCH,
    SET_FIND_MODE, RESPONSE_SET_FIND_MODE,
    QUERY_BASS_ENGINE, RESPONSE_BASS_ENGINE, SET_BASS_ENGINE, RESPONSE_SET_BASS_ENGINE,
    EQ_ACTION_CREATE, EQ_ACTION_UPDATE, EQ_ACTION_DELETE,
)
from .touch import (
    TouchBinding, parse_touch_bindings, HOLD_CYCLE_QUERY, hold_cycle_mask, parse_hold_cycle,
)


class UnsupportedProductError(RuntimeError):
    def __init__(self, device: Device, product_id: str | None) -> None:
        super().__init__(f"product {product_id or 'unknown'} has no tested device profile")
        self.device = device
        self.product_id = product_id


def validate_eq_profile_name(name: str) -> str:
    """Return a trimmed profile name that the protocol can carry."""
    label = str(name or "").strip()
    if not label:
        raise ValueError("the EQ profile name must not be empty")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in label):
        raise ValueError("the EQ profile name must not contain control characters")
    if len(label.encode("utf-8")) > 0xFF:
        raise ValueError("the EQ profile name is too long")
    return label


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
        self._last_battery_refresh = monotonic()
        self._deferred_frames: list[Frame] = []
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
                raise UnsupportedProductError(device, product)
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

        SET status alone is never proof of the new state. Auto can be
        confirmed by the selected-mode notification when the query reports
        the concrete intensity chosen by the adaptive mode.
        The caller discards a failed transaction's session before recovery.
        """
        self._require_connected()
        if not self._authenticated:
            raise RuntimeError("session authentication has not completed")
        if not self.profile.can_write("anc") or mode not in self.profile.anc.write_indices:
            raise ValueError("ANC mode is not authorized for this device profile")
        timer = PhaseTimer()
        events: list[SafeEvent] = []
        ignored = 0
        selected_notification: AncState | None = None

        def collect(frames: list[Frame]) -> None:
            nonlocal ignored, selected_notification
            for frame in frames:
                if frame.command == NOTIFY_STATE and frame.payload[:3] == b"\x03\x01\x01":
                    selected_notification = parse_anc_state(frame, self.profile.anc)
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
            expected_mode, expected_level = self.profile.anc.expected_state(mode)

            def confirmed_auto() -> AncState | None:
                if (self.profile.product_id == "064414" and mode == "auto"
                        and selected_notification is not None
                        and selected_notification.mode == "on"
                        and selected_notification.level == "auto"):
                    return selected_notification
                return None

            # SET acknowledgement can precede physical application. A first
            # fresh query may legitimately return the previous mode. Re-query
            # on each response, bounded by both time and count; never replay SET.
            observed = None
            deadline = monotonic() + 2.0
            for query_count in range(1, 33):
                remaining = deadline - monotonic()
                if remaining <= 0:
                    break
                try:
                    state = self._transport.request(
                        QUERY_ANC, b"\x01\x01", RESPONSE_ANC, on_frames=collect,
                        timeout=remaining,
                    )
                except TimeoutError:
                    observed = confirmed_auto()
                    if observed is None:
                        raise
                    break
                observed = parse_anc_state(state, self.profile.anc) if state.payload[:1] == b"\x00" else None
                if observed is not None and observed.mode == expected_mode and (
                    expected_level is None or observed.level == expected_level
                ):
                    break
                adaptive = confirmed_auto()
                if adaptive is not None:
                    observed = adaptive
                    break
            else:
                observed = None
            timer.mark("verify_query")
            if observed is None or observed.mode != expected_mode or (
                expected_level is not None and observed.level != expected_level
            ):
                observed = confirmed_auto()
                if observed is None:
                    raise RuntimeError(
                        "ANC verification failed: fresh state did not match request")
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
        self._require_eq_session()
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
        self._require_eq_session()
        eq = self.profile.eq
        if eq is not None and eq.preset_for(preset) is not None:
            # Factory targets can be classified and rejected before any I/O.
            self._require_eq_session(write="eq_preset")
        timer = PhaseTimer()
        before, initial = self.eq_status()
        timer.mark("preserve_read")
        target_id, target_name, write_operation = self._resolve_eq_target(preset, before)
        self._require_eq_session(write=write_operation)
        if (write_operation == "eq_preset" and eq.writable_preset_ids is not None
                and target_id not in eq.writable_preset_ids):
            raise ValueError("factory EQ target has not been write-tested")
        # Some device families select a custom curve by writing it, not with
        # the plain preset command: writing the unchanged curve back selects
        # the custom entry without altering the sound.
        custom = next((item for item in before.custom_entries
                       if item.eq_id == target_id), None)
        if custom is not None and eq is not None and eq.custom_select_via_write:
            return self.set_custom_eq(
                custom.eq_id, tuple(band.gain_db for band in custom.bands))
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
        self._require_eq_session(write="custom_eq")
        eq = self.profile.eq
        if eq.writable_custom_ids is not None and entry_id not in eq.writable_custom_ids:
            raise ValueError("custom EQ slot has not been write-tested")
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

    def create_custom_eq(self, name: str) -> tuple[EqControlResult, EventBatch]:
        """Create one new custom curve in the next free slot of the earbuds."""
        self._require_eq_session(write="custom_eq")
        if self.profile.eq is None or not self.profile.eq.custom_manage_verified:
            raise ValueError("custom EQ management is not tested for this device profile")
        label = validate_eq_profile_name(name)
        timer = PhaseTimer()
        before, initial = self.eq_status()
        timer.mark("preserve_read")
        template = before.custom_entries[0] if before.custom_entries else None
        used = {item.eq_id for item in before.custom_entries}
        if template is None:
            layout = self.profile.eq.empty_create_layout
            if layout is None:
                raise RuntimeError("the earbuds did not declare a custom EQ layout")
            slot = layout.slot_id
            entry = EqEntry(slot, label, False, layout.min_gain_db, layout.max_gain_db,
                            tuple(EqBand(frequency, 0) for frequency in layout.frequencies_hz))
        else:
            slot = self._next_custom_slot(used)
            entry = EqEntry(slot, label, False, template.min_gain_db, template.max_gain_db,
                            template.bands)
        gains = tuple(0 for _ in entry.bands)

        def expect(entries: tuple[EqEntry, ...]) -> bool:
            if template is None:
                return any(item.eq_id == slot and item.name == label
                           and item.bands == entry.bands
                           and item.min_gain_db == entry.min_gain_db
                           and item.max_gain_db == entry.max_gain_db for item in entries)
            return any(item.eq_id not in used for item in entries)

        acknowledgement, entries, _current_id, query_count, events, ignored = (
            self._write_eq_entry(entry, gains, action=EQ_ACTION_CREATE, expect=expect)
        )
        created = None
        if entries is not None:
            fresh = [item for item in entries if item.eq_id not in used]
            if len(fresh) == 1:
                created = fresh[0]
        if created is None or (template is None and not expect(entries or ())):
            raise RuntimeError(
                "custom EQ verification failed: the earbuds did not store the new profile")
        events = list(initial.events) + list(events)
        ignored += initial.ignored_frames
        self._restore_eq_selection(before)
        return EqControlResult(
            self.device.name, self.profile.product_id, created.eq_id, created.name,
            before.current_id, before.current_name,
            acknowledgement, True, timer.finish("session_total"), query_count,
        ), EventBatch(tuple(events), ignored)

    def rename_custom_eq(self, entry_id: int, name: str) -> tuple[EqControlResult, EventBatch]:
        """Rename one existing device-declared custom curve; the curve stays unchanged."""
        self._require_eq_session(write="custom_eq")
        if self.profile.eq is None or not self.profile.eq.custom_manage_verified:
            raise ValueError("custom EQ management is not tested for this device profile")
        if (self.profile.eq.managed_custom_ids is not None
                and entry_id not in self.profile.eq.managed_custom_ids):
            raise ValueError("custom EQ slot has not been rename-tested")
        label = validate_eq_profile_name(name)
        timer = PhaseTimer()
        before, initial = self.eq_status()
        timer.mark("preserve_read")
        entry = next((item for item in before.custom_entries if item.eq_id == entry_id), None)
        if entry is None:
            raise ValueError("custom EQ id was not declared by the connected earbuds")
        gains = tuple(band.gain_db for band in entry.bands)

        def expect(entries: tuple[EqEntry, ...]) -> bool:
            item = next((value for value in entries if value.eq_id == entry_id), None)
            return item is not None and item.name == label

        acknowledgement, entries, _current_id, query_count, events, ignored = (
            self._write_eq_entry(entry, gains, action=EQ_ACTION_UPDATE, name=label, expect=expect)
        )
        renamed = next((item for item in entries or () if item.eq_id == entry_id), None)
        if renamed is None or renamed.name != label:
            raise RuntimeError(
                "custom EQ verification failed: the earbuds did not store the new name")
        events = list(initial.events) + list(events)
        ignored += initial.ignored_frames
        self._restore_eq_selection(before)
        return EqControlResult(
            self.device.name, self.profile.product_id, entry_id, renamed.name,
            before.current_id, before.current_name,
            acknowledgement, True, timer.finish("session_total"), query_count,
        ), EventBatch(tuple(events), ignored)

    def delete_custom_eq(self, entry_id: int) -> tuple[EqControlResult, EventBatch]:
        """Delete one existing device-declared custom curve."""
        self._require_eq_session(write="custom_eq")
        if self.profile.eq is None or not self.profile.eq.custom_manage_verified:
            raise ValueError("custom EQ management is not tested for this device profile")
        if (self.profile.eq.managed_custom_ids is not None
                and entry_id not in self.profile.eq.managed_custom_ids):
            raise ValueError("custom EQ slot has not been delete-tested")
        timer = PhaseTimer()
        before, initial = self.eq_status()
        timer.mark("preserve_read")
        entry = next((item for item in before.custom_entries if item.eq_id == entry_id), None)
        if entry is None:
            raise ValueError("custom EQ id was not declared by the connected earbuds")
        if self.profile.eq.custom_keep_last and len(before.custom_entries) == 1:
            raise ValueError("Keep one custom EQ profile on these earbuds. You can rename it.")
        gains = tuple(band.gain_db for band in entry.bands)

        def expect(entries: tuple[EqEntry, ...]) -> bool:
            return all(item.eq_id != entry_id for item in entries)

        acknowledgement, entries, _current_id, query_count, events, ignored = (
            self._write_eq_entry(entry, gains, action=EQ_ACTION_DELETE, expect=expect)
        )
        if entries is None or any(item.eq_id == entry_id for item in entries):
            raise RuntimeError(
                "custom EQ verification failed: the earbuds still list the profile")
        events = list(initial.events) + list(events)
        ignored += initial.ignored_frames
        return EqControlResult(
            self.device.name, self.profile.product_id, entry_id, entry.name,
            before.current_id, before.current_name,
            acknowledgement, True, timer.finish("session_total"), query_count,
        ), EventBatch(tuple(events), ignored)

    def _next_custom_slot(self, used: set[int]) -> int:
        """Return the next free custom profile id of the connected earbuds."""
        eq = self.profile.eq
        if eq is not None and eq.managed_custom_ids is not None:
            for slot in eq.managed_custom_ids:
                if slot not in used:
                    return slot
            raise RuntimeError("no tested custom EQ slot is free")
        base = eq.custom_base if eq is not None else None
        maximum = eq.custom_max if eq is not None else None
        if base is not None and maximum:
            free = [base + offset for offset in range(maximum)
                    if base + offset not in used]
            if not free:
                raise RuntimeError(
                    f"the earbuds already hold {maximum} custom profiles; "
                    "delete one before adding another")
            return free[0]
        if used:
            candidate = max(used) + 1
            if candidate <= 0xFF:
                return candidate
        raise RuntimeError("no free custom EQ slot is left")

    def _write_eq_entry(self, entry: EqEntry, gains_db: tuple[int, ...], *,
                        action: int, name: str | None = None,
                        expect: Callable[[tuple[EqEntry, ...]], bool] | None = None
                        ) -> tuple[int | None, tuple[EqEntry, ...] | None, int | None,
                                   int, list[SafeEvent], int]:
        """Send one custom EQ entry operation once and read the catalogue back."""
        timer = PhaseTimer()
        payload = encode_eq_detail_payload(entry, gains_db, action=action, name=name)
        events: list[SafeEvent] = []
        ignored = 0

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
            entries: tuple[EqEntry, ...] | None = None
            deadline = monotonic() + 2.0
            query_count = 0
            for query_count in range(1, 33):
                remaining = deadline - monotonic()
                if remaining <= 0:
                    break
                frame = self._transport.request(
                    QUERY_EQ_ALL, EQ_ALL_QUERY_PAYLOAD, RESPONSE_EQ_ALL,
                    on_frames=collect, timeout=remaining,
                )
                entries = parse_eq_entries(frame)
                if entries is not None and (expect is None or expect(entries)):
                    break
            timer.mark("verify_query")
            current = self._transport.request(QUERY_EQ, b"", RESPONSE_EQ, on_frames=collect)
            current_id = parse_eq_id(current)
            timer.elapsed("verified_elapsed")
            return (parse_set_eq_status(acknowledgement) if acknowledgement else None,
                    entries, current_id, query_count, events, ignored)
        except (OSError, RuntimeError) as error:
            raise RuntimeError("custom EQ session request failed: " + str(error)) from error

    def _restore_eq_selection(self, before: EqStatusResult) -> None:
        """Re-select the profile that was active before an entry write.

        The entry write already succeeded and verified; restoring the previous
        selection is best-effort and must never turn a stored create/rename into
        an error. An id that is neither a preset nor a custom entry (the Nord
        accepts other factory ids) is selected with a plain preset command.
        """
        try:
            current, _batch = self.eq_status()
            if current.current_id == before.current_id:
                return
            custom = next((item for item in before.custom_entries
                           if item.eq_id == before.current_id), None)
            if custom is not None:
                self.set_custom_eq(custom.eq_id, tuple(band.gain_db for band in custom.bands))
            else:
                self._transport.request(SET_EQ, bytes((before.current_id,)), RESPONSE_SET_EQ,
                                        on_frames=self._defer_frames)
        except (OSError, RuntimeError, ValueError):
            pass

    def _defer_frames(self, frames: list[Frame]) -> None:
        """Keep unrelated frames arriving during a read for the next poll."""
        self._deferred_frames.extend(frames)
        del self._deferred_frames[:-256]

    def read_hold_cycle(self) -> int:
        self._require_connected()
        if not self.profile.hold_cycle_supported:
            raise ValueError("hold cycle is not supported by this device profile")
        frame = self._transport.request(QUERY_ANC, HOLD_CYCLE_QUERY, RESPONSE_ANC,
                                        on_frames=self._defer_frames)
        try:
            return parse_hold_cycle(
                frame, allow_trailing_zero=self.profile.product_id == "062014"
            )
        except ValueError as error:
            raise RuntimeError(
                f"{error}; response=0x{frame.command:04x}:{frame.payload.hex()}"
            ) from error

    def set_hold_cycle(self, modes: tuple[str, ...]) -> tuple[int | None, int]:
        self._require_connected()
        if not self._authenticated:
            raise RuntimeError("session authentication has not completed")
        if (not self.profile.can_write("hold_cycle")
                or not self.profile.hold_cycle_supported
                or not self.profile.hold_cycle_write_verified):
            raise ValueError("hold cycle writes are not verified for this device profile")
        mask = hold_cycle_mask(modes)
        self.read_hold_cycle()  # require valid current state before writing
        try:
            ack = self._transport.request(SET_ANC, HOLD_CYCLE_QUERY + bytes((mask,)), RESPONSE_SET_ANC,
                                          on_frames=self._defer_frames)
            if len(ack.payload) != 1:
                raise RuntimeError("device returned malformed hold cycle acknowledgement")
            status = ack.payload[0]
        except TimeoutError:
            status = None
        return status, self.read_hold_cycle()

    def touch_bindings(self) -> tuple[TouchBinding, ...]:
        self._require_connected()
        if not (self.profile.touch_functions or self.profile.touch_binding_functions):
            raise ValueError("touch controls are not supported by this device profile")
        frame = self._transport.request(QUERY_TOUCH, b"", RESPONSE_TOUCH,
                                        on_frames=self._defer_frames)
        try:
            return parse_touch_bindings(frame)
        except ValueError as error:
            raise RuntimeError(str(error)) from error

    def set_touch_binding(self, binding: TouchBinding) -> tuple[int | None, tuple[TouchBinding, ...]]:
        self._require_connected()
        if not self._authenticated:
            raise RuntimeError("session authentication has not completed")
        if (not self.profile.can_write("touch") or binding.device_type not in (1, 2)
                or binding.button != 1
                or binding.function not in self.profile.touch_binding_functions.get(
                    binding.key, self.profile.touch_functions.get(binding.action, ()))):
            raise ValueError("touch assignment is not allowed for this device profile")
        if not any(item.key == binding.key for item in self.touch_bindings()):
            raise ValueError("touch gesture was not reported by this device")
        try:
            ack = self._transport.request(SET_TOUCH, binding.write_payload(), RESPONSE_SET_TOUCH,
                                          on_frames=self._defer_frames)
            if len(ack.payload) != 1:
                raise RuntimeError("device returned malformed touch acknowledgement")
            status = ack.payload[0]
        except TimeoutError:
            status = None
        return status, self.touch_bindings()

    def feature_switches(self, feature_ids: tuple[int, ...]) -> dict[int, bool]:
        """Read the device's feature switches in the phone app's request shape."""
        self._require_connected()
        payload = bytes((len(feature_ids),)) + bytes(feature_ids)
        frame = self._transport.request(QUERY_STATUS, payload, RESPONSE_STATUS,
                                        on_frames=self._defer_frames)
        switches = parse_feature_switches(frame)
        if switches is None:
            raise RuntimeError("device returned malformed feature switch state")
        return switches

    def set_feature_switch(self, feature_id: int, enabled: bool) -> tuple[int | None, bool]:
        """Set one feature switch and verify it with a fresh read."""
        self._require_connected()
        if not self.profile.can_write("feature_switch"):
            raise ValueError("feature switch writes are not authorized for this device profile")
        name = FEATURE_SWITCH_NAMES.get(feature_id)
        if name not in self.profile.writable_features:
            raise ValueError(f"the {name or feature_id} switch is read-only for this device model")
        if not 0 <= feature_id <= 0xFF:
            raise ValueError("feature id must fit in one byte")
        payload = bytes((feature_id, 1 if enabled else 0))
        try:
            ack = self._transport.request(SET_FEATURE_SWITCH, payload, RESPONSE_SET_FEATURE_SWITCH,
                                          on_frames=self._defer_frames)
            status = (ack.payload[0]
                      if ack.command == RESPONSE_SET_FEATURE_SWITCH and ack.payload else None)
        except TimeoutError:
            status = None
        if status is not None and status != 0:
            return status, False
        verified = self.feature_switches((feature_id,)).get(feature_id)
        return status, status == 0 and verified is enabled

    def find_earbuds(self, ringing: bool = True) -> tuple[int | None, bool]:
        """Start or stop the find-my-earbuds tone."""
        self._require_connected()
        if not self._authenticated:
            raise RuntimeError("session authentication has not completed")
        if not self.profile.can_write("find") or "find_earbuds" not in self.profile.capabilities:
            raise ValueError("earbud search is not supported by this device profile")
        payload = bytes((1 if ringing else 0,))
        try:
            ack = self._transport.request(SET_FIND_MODE, payload, RESPONSE_SET_FIND_MODE,
                                          on_frames=self._defer_frames)
            status = (ack.payload[0]
                      if ack.command == RESPONSE_SET_FIND_MODE and ack.payload else None)
        except TimeoutError:
            status = None
        return status, True

    def bass_engine_status(self) -> tuple[int, int, int]:
        """Read the bass engine range and current level ([status, min, max, current])."""
        self._require_connected()
        frame = self._transport.request(QUERY_BASS_ENGINE, b"", RESPONSE_BASS_ENGINE,
                                        on_frames=self._defer_frames)
        if len(frame.payload) < 4 or frame.payload[0] != 0:
            raise RuntimeError("device returned malformed bass engine state")
        minimum = frame.payload[1] - 256 if frame.payload[1] > 127 else frame.payload[1]
        maximum = frame.payload[2] - 256 if frame.payload[2] > 127 else frame.payload[2]
        current = frame.payload[3] - 256 if frame.payload[3] > 127 else frame.payload[3]
        return minimum, maximum, current

    def set_bass_level(self, level: int) -> tuple[int | None, bool]:
        """Set the bass engine level ("BassWave"); the device echoes [min, max, value]."""
        self._require_connected()
        if (not self.profile.can_write("bass_level")
                or "bass_engine" not in self.profile.capabilities
                or self.profile.bass_level_range is None):
            raise ValueError("bass level writes are not supported by this device profile")
        minimum, maximum = self.profile.bass_level_range
        if not minimum <= level <= maximum:
            raise ValueError(f"bass level must be between {minimum} and {maximum}")
        if self.profile.product_id == "067814" and self.bass_engine_status()[:2] != (minimum, maximum):
            raise ValueError("earbuds reported a different BassWave range")
        payload = bytes(value & 0xFF for value in (minimum, maximum, level))
        try:
            ack = self._transport.request(SET_BASS_ENGINE, payload, RESPONSE_SET_BASS_ENGINE,
                                          on_frames=self._defer_frames)
            status = (ack.payload[0]
                      if ack.command == RESPONSE_SET_BASS_ENGINE and ack.payload else None)
        except TimeoutError:
            status = None
        return status, True

    def _require_eq_session(self, *, write: WriteOperation | None = None) -> None:
        self._require_connected()
        if not self._authenticated:
            raise RuntimeError("session authentication has not completed")
        if self.profile.eq is None:
            raise ValueError("native EQ is not supported by this device profile")
        if write and not self.profile.can_write(write):
            raise ValueError(f"{write} writes are not authorized for this device profile")
        if write == "eq_preset" and not self.profile.eq.write_verified:
            raise ValueError("factory EQ writes are not tested for this device profile")
        if write == "custom_eq" and not self.profile.eq.custom_write_verified:
            raise ValueError("custom EQ writes are not tested for this device profile")

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

    def _resolve_eq_target(
        self, value: str, status: EqStatusResult
    ) -> tuple[int, str, WriteOperation]:
        eq = self.profile.eq
        if eq is None:
            raise ValueError("native EQ is not supported by this device profile")
        preset = eq.preset_for(value)
        if preset is not None:
            return preset.eq_id, preset.name, "eq_preset"
        normalized = value.strip().lower()
        for entry in status.custom_entries:
            if normalized in (f"custom:{entry.eq_id}", entry.name.lower()):
                return entry.eq_id, entry.name, "custom_eq"
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
        now = monotonic()
        if self.profile.case_battery_cached and now - self._last_battery_refresh >= 10:
            self._last_battery_refresh = now
            # Read through normal polling without a blocking query while
            # foreground commands wait for the controller.
            self._transport.send_query(QUERY_BATTERY)
        received = self._redact(self._deferred_frames + self._transport.receive(wait))
        self._deferred_frames = []
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
                and feature not in self.profile.unconfirmed_feature_switches
            }
            return SafeEvent("feature_switches", named)
        if frame.command == NOTIFY_STATE and frame.payload:
            # The device pushes the selected noise mode as [event, 01, 01, bitmap].
            # Following it lets the panel track phone-app changes and confirms
            # Auto writes whose query answers with the active intensity instead.
            # Active-intensity pushes ([event, 04, 01, bitmap]) stay diagnostic.
            if frame.payload[:3] == b"\x03\x01\x01":
                state = parse_anc_state(frame, self.profile.anc)
                if state is not None:
                    return SafeEvent("anc", {"mode": state.mode, "level": state.level})
            return SafeEvent("notification", {"event_code": frame.payload[0]})
        return None

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("session is not connected")
