from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from threading import RLock
from time import monotonic
from typing import cast

from .lifecycle_trace import mark
from .api import BudsBackend
from .case_battery import CaseBatteryCache
from .models import ControllerSnapshot, ControlResult, EqControlResult, EqStatusResult, EventBatch, StatusResult
from .profiles import profile_for_product
from .protocol import FEATURE_SWITCH_NAMES, VersionRecord
from .session import OpoSession, UnsupportedProductError
from .timing import AncRequestError, PhaseTimer
from .touch import TouchBinding, hold_cycle_mask


@dataclass(frozen=True)
class _FindState:
    state: str = "stopped"
    deadline: float | None = None


class BudsController:
    """Serialized state/session owner for a future service or frontend."""

    def __init__(self, backend: BudsBackend | None = None, address: str | None = None,
                 *, reuse_session: bool = True,
                 case_battery_cache: CaseBatteryCache | None = None) -> None:
        self.backend = backend or BudsBackend()
        self._selected_address = address
        self.address = address
        self.reuse_session = reuse_session
        self._lock = RLock()
        self._running = False
        self._session: OpoSession | None = None
        self._status: StatusResult | None = None
        self._feature_switches: dict[str, bool] = {}
        self._advertised_event_codes: tuple[int, ...] = ()
        self._notification_event_codes: tuple[int, ...] = ()
        self._ignored_frames = 0
        self._reconnect_count = 0
        self._generation = 0
        self._eq_status: EqStatusResult | None = None
        self._case_battery_cache = case_battery_cache or CaseBatteryCache()
        self._bass_level: int | None = None
        self._touch_bindings: tuple[TouchBinding, ...] = ()
        self._hold_cycle_mask: int | None = None
        self._find_states: dict[tuple[str, str | None], _FindState] = {}
        self._last_state_refresh: float = 0.0

    def start(self) -> ControllerSnapshot:
        with self._lock:
            if self._running:
                return self.snapshot()
            mark("controller_start")
            self.shutdown()
            try:
                self._session, self._status, batch = self.backend.start_session(self._selected_address)
                self.address = self._status.device.address
                self._update_battery(self._status.battery)
                self._advertised_event_codes = self._session.advertised_event_codes
                self._apply_batch(batch)
                self._running = True
                mark("controller_usable")
            except UnsupportedProductError as error:
                self._status = StatusResult(
                    device=error.device,
                    product_id=error.product_id,
                    model=None,
                    remote_version=(),
                    firmware_version=None,
                    battery=None,
                    anc=None,
                    anc_level=None,
                )
                self.address = error.device.address
                self._running = True
                self._generation += 1
                return self.snapshot()
            except Exception:
                self.shutdown()
                raise
            return self.snapshot()

    def refresh(self) -> ControllerSnapshot:
        with self._lock:
            self.shutdown()
            return self.start()

    def set_anc(self, mode: str) -> ControlResult:
        timer = PhaseTimer()
        timings: dict[str, float] = {}
        with self._lock:
            timer.mark("controller_lock_wait")
            if self.reuse_session and self._running:
                return self._set_session_anc(mode, timer)
            try:
                self._close_session()
                timer.mark("monitor_close")
                try:
                    result = self.backend.set_anc(mode, self.address)
                    timings.update(result.timings_ms)
                    timer.mark("backend_request")
                    if self._status is not None:
                        self._status = replace(
                            self._status,
                            anc=result.anc,
                            anc_level=result.anc_level,
                        )
                    self._generation += 1
                except Exception as error:
                    if isinstance(error, AncRequestError):
                        timings.update(error.timings_ms)
                    timer.mark("backend_request")
                    if self._running and self._status is not None:
                        try:
                            self._connect_session()
                        except Exception:
                            pass
                    timer.mark("monitor_recovery")
                    raise
                if self._running:
                    self._connect_session()
                timer.mark("monitor_resume")
            except (OSError, RuntimeError) as error:
                timer.mark("failed_controller_phase")
                raise AncRequestError(
                    str(error), {**timings, **timer.finish("controller_total")}
                ) from error
            return replace(
                result, timings_ms={**timings, **timer.finish("controller_total")}
            )

    def _set_session_anc(self, mode: str, timer: PhaseTimer) -> ControlResult:
        try:
            if self._session is None:
                self._connect_session()
            timer.mark("session_ready")
            result, batch = cast(OpoSession, self._session).set_anc(mode)
            self._apply_batch(batch)
            if self._status is not None:
                self._status = replace(self._status, anc=result.anc, anc_level=result.anc_level)
            self._generation += 1
            # No socket teardown, reauthentication, or subscription restoration.
            return replace(result, timings_ms={
                **result.timings_ms, **timer.finish("controller_total"),
            })
        except ValueError:
            # Profile/parameter rejection happens before transport I/O.
            raise
        except (OSError, RuntimeError) as error:
            # Never replay an uncertain write. Poll/service recovery can reopen
            # later, without delaying this failed command's response.
            self._close_session()
            if self._status is not None:
                self._status = replace(self._status, anc=None, anc_level=None)
            self._generation += 1
            timings = error.timings_ms if isinstance(error, AncRequestError) else {}
            raise AncRequestError(str(error), {
                **timings, **timer.finish("controller_total"),
            }) from error

    def set_anc_with_snapshot(self, mode: str) -> tuple[ControlResult, ControllerSnapshot]:
        """Capture verified state before a poll can start monitoring recovery."""
        timer = PhaseTimer()
        with self._lock:
            timer.mark("controller_lock_wait")
            result = self.set_anc(mode)
            snapshot = self.snapshot()
            return replace(result, timings_ms={
                **result.timings_ms, **timer.finish("controller_total"),
            }), snapshot

    def eq_status(self) -> EqStatusResult:
        with self._lock:
            self._require_running()
            if self._session is None:
                self.refresh()
            result, batch = cast(OpoSession, self._session).eq_status()
            self._apply_batch(batch)
            self._eq_status = result
            self._generation += 1
            return result

    def set_eq(self, preset: str) -> EqControlResult:
        with self._lock:
            self._require_running()
            if self._session is None:
                self.refresh()
            try:
                result, batch = cast(OpoSession, self._session).set_eq(preset)
            except ValueError:
                raise
            except (OSError, RuntimeError):
                self._close_session()
                self._eq_status = None
                self._generation += 1
                raise
            self._apply_batch(batch)
            self._eq_status = None
            self._generation += 1
            return result

    def set_custom_eq(self, entry_id: int, gains_db: tuple[int, ...], *,
                      device_id: str | None = None) -> EqControlResult:
        with self._lock:
            self._require_running()
            intended_key = self._find_key()
            if device_id is not None and device_id != self._find_device_id():
                raise ValueError("Selected earbuds changed; EQ command was not sent")
            if self._session is None:
                self.refresh()
            if intended_key is not None and intended_key != self._find_key():
                raise ValueError("Selected earbuds changed; EQ command was not sent")
            try:
                result, batch = cast(OpoSession, self._session).set_custom_eq(entry_id, gains_db)
            except ValueError:
                raise
            except (OSError, RuntimeError):
                self._close_session()
                self._eq_status = None
                self._generation += 1
                raise
            self._apply_batch(batch)
            self._eq_status = None
            self._generation += 1
            return result

    def create_custom_eq(self, name: str, *, device_id: str | None = None) -> EqControlResult:
        with self._lock:
            self._require_running()
            intended_key = self._find_key()
            if device_id is not None and device_id != self._find_device_id():
                raise ValueError("Selected earbuds changed; EQ command was not sent")
            if self._session is None:
                self.refresh()
            if intended_key is not None and intended_key != self._find_key():
                raise ValueError("Selected earbuds changed; EQ command was not sent")
            try:
                result, batch = cast(OpoSession, self._session).create_custom_eq(name)
            except ValueError:
                raise
            except (OSError, RuntimeError):
                self._close_session()
                self._eq_status = None
                self._generation += 1
                raise
            self._apply_batch(batch)
            self._eq_status = None
            self._generation += 1
            return result

    def rename_custom_eq(self, entry_id: int, name: str, *,
                         device_id: str | None = None) -> EqControlResult:
        with self._lock:
            self._require_running()
            intended_key = self._find_key()
            if device_id is not None and device_id != self._find_device_id():
                raise ValueError("Selected earbuds changed; EQ command was not sent")
            if self._session is None:
                self.refresh()
            if intended_key is not None and intended_key != self._find_key():
                raise ValueError("Selected earbuds changed; EQ command was not sent")
            try:
                result, batch = cast(OpoSession, self._session).rename_custom_eq(entry_id, name)
            except ValueError:
                raise
            except (OSError, RuntimeError):
                self._close_session()
                self._eq_status = None
                self._generation += 1
                raise
            self._apply_batch(batch)
            self._eq_status = None
            self._generation += 1
            return result

    def delete_custom_eq(self, entry_id: int, *, device_id: str | None = None) -> EqControlResult:
        with self._lock:
            self._require_running()
            intended_key = self._find_key()
            if device_id is not None and device_id != self._find_device_id():
                raise ValueError("Selected earbuds changed; EQ command was not sent")
            if self._session is None:
                self.refresh()
            if intended_key is not None and intended_key != self._find_key():
                raise ValueError("Selected earbuds changed; EQ command was not sent")
            try:
                result, batch = cast(OpoSession, self._session).delete_custom_eq(entry_id)
            except ValueError:
                raise
            except (OSError, RuntimeError):
                self._close_session()
                self._eq_status = None
                self._generation += 1
                raise
            self._apply_batch(batch)
            self._eq_status = None
            self._generation += 1
            return result

    def touch_controls(self) -> None:
        with self._lock:
            self._require_running()
            if self._session is None:
                self.refresh()
            try:
                self._touch_bindings = cast(OpoSession, self._session).touch_bindings()
                profile = profile_for_product(self._status.product_id) if self._status else None
                self._hold_cycle_mask = cast(OpoSession, self._session).read_hold_cycle() if (
                    profile and profile.hold_cycle_supported) else None
            except (OSError, RuntimeError):
                self._close_session()
                self._generation += 1
                raise
            self._generation += 1

    def set_hold_cycle(self, modes: tuple[str, ...]) -> dict[str, object]:
        target = hold_cycle_mask(modes)
        with self._lock:
            self._require_running()
            if self._session is None:
                self.refresh()
            try:
                status, actual = cast(OpoSession, self._session).set_hold_cycle(modes)
            except (OSError, RuntimeError):
                self._close_session()
                self._generation += 1
                raise
            self._hold_cycle_mask = actual
            self._generation += 1
            return {"set_status": status, "verified": status in (None, 0) and actual == target}

    def set_touch_control(self, side: int, action: int, function: int) -> dict[str, object]:
        with self._lock:
            self._require_running()
            if self._session is None:
                self.refresh()
            target = TouchBinding(side, 1, action, function)
            try:
                status, bindings = cast(OpoSession, self._session).set_touch_binding(target)
            except (OSError, RuntimeError):
                # The device may already have applied the change. Never retry
                # a write or keep presenting stale assignments as confirmed.
                self._close_session()
                self._generation += 1
                raise
            self._touch_bindings = bindings
            self._generation += 1
            return {"side": side, "action": action, "function": function,
                    "set_status": status, "verified": status in (None, 0) and target in bindings}

    def feature_switches(self) -> dict[str, bool]:
        with self._lock:
            self._require_running()
            if self._session is None:
                self.refresh()
            switches = cast(OpoSession, self._session).feature_switches(tuple(FEATURE_SWITCH_NAMES))
            named = {name: switches[feature_id]
                     for feature_id, name in FEATURE_SWITCH_NAMES.items()
                     if feature_id in switches}
            self._feature_switches.update(named)
            self._generation += 1
            return named

    def set_feature_switch(self, feature_id: int, enabled: bool) -> dict[str, object]:
        with self._lock:
            self._require_running()
            if self._session is None:
                self.refresh()
            name = FEATURE_SWITCH_NAMES.get(feature_id, f"feature_{feature_id:02x}")
            profile = profile_for_product(self._status.product_id) if self._status else None
            if profile is None or name not in profile.writable_features:
                raise ValueError(f"the {name} switch is read-only for this device model")
            intended_address = self._status.device.address
            intended_product = self._status.product_id
            connection_changing = name in ("multipoint", "high_quality_audio")
            recover = False
            try:
                status, verified = cast(OpoSession, self._session).set_feature_switch(feature_id, enabled)
                recover = connection_changing and status is None
            except (OSError, RuntimeError):
                if not connection_changing:
                    raise
                status, verified, recover = None, False, True
            if recover:
                verified = self._recover_feature_switch(
                    feature_id, enabled, name, intended_address, intended_product)
            if verified:
                self._feature_switches[name] = enabled
            self._generation += 1
            return {"feature": name, "feature_id": feature_id, "enabled": enabled,
                    "verified": verified, "set_status": status}

    def _recover_feature_switch(self, feature_id: int, enabled: bool, name: str,
                                address: str, product_id: str | None) -> bool:
        """Read a connection-changing setting once on the same pair; never resend it."""
        self._close_session()
        self._feature_switches.pop(name, None)
        self._reconnect_count += 1
        try:
            session, status, batch = self.backend.start_session(address)
            if (status.device.address.upper() != address.upper()
                    or status.product_id != product_id):
                session.__exit__(None, None, None)
                return False
            self._session, self._status = session, status
            self.address = status.device.address
            self._update_battery(status.battery)
            self._advertised_event_codes = session.advertised_event_codes
            self._apply_batch(batch)
            observed = session.feature_switches((feature_id,)).get(feature_id)
            if isinstance(observed, bool):
                self._feature_switches[name] = observed
            return observed is enabled
        except (OSError, RuntimeError, ValueError):
            self._close_session()
            return False

    def find_earbuds(self, ringing: bool = True, *, device_id: str | None = None) -> dict[str, object]:
        """Track confirmed/uncertain sound state for the selected physical pair."""
        with self._lock:
            self._require_running()
            intended_key = self._find_key()
            if device_id is not None and device_id != self._find_device_id():
                raise ValueError("Selected earbuds changed; search command was not sent")
            if self._session is None:
                self.refresh()
            key = self._find_key()
            if ((intended_key is not None and key != intended_key)
                    or (device_id is not None and device_id != self._find_device_id())):
                raise ValueError("Selected earbuds changed; search command was not sent")
            if key is None:
                raise RuntimeError("no device selected")
            previous = self._find_state()
            started = monotonic()
            try:
                status, sent = cast(OpoSession, self._session).find_earbuds(ringing)
            except (OSError, RuntimeError):
                # The write may already have applied. Never replay a start.
                self._close_session()
                status, sent = None, True
            if status == 0:
                current = _FindState("ringing", started + 50.0) if ringing else _FindState()
            elif status is None or not ringing:
                current = _FindState("unknown", started + 50.0 if ringing else previous.deadline)
            else:
                # A rejected start does not turn an idle search into ringing.
                current = previous
            if current.state == "stopped":
                self._find_states.pop(key, None)
            else:
                self._find_states[key] = current
            self._generation += 1
            return {"ringing": ringing, "sent": sent, "set_status": status,
                    "acknowledged": status == 0, "state": current.state}

    def _find_key(self) -> tuple[str, str | None] | None:
        if self._status is None:
            return None
        return self._status.device.address.upper(), self._status.product_id

    def _find_state(self) -> _FindState:
        key = self._find_key()
        return self._find_states.get(key, _FindState()) if key is not None else _FindState()

    def _find_device_id(self) -> str | None:
        key = self._find_key()
        return sha256(f"{key[0]}:{key[1]}".encode()).hexdigest() if key is not None else None

    def _expire_find(self) -> None:
        current = self._find_state()
        if current.deadline is not None and monotonic() >= current.deadline:
            key = self._find_key()
            if key is not None:
                # Consume the deadline before I/O; failure must not repeat it.
                self._find_states[key] = replace(current, deadline=None)
                self.find_earbuds(False)

    def set_bass_level(self, level: int) -> dict[str, object]:
        with self._lock:
            self._require_running()
            if self._session is None:
                self.refresh()
            status, sent = cast(OpoSession, self._session).set_bass_level(level)
            self._bass_level = level
            self._generation += 1
            return {"level": level, "sent": sent, "set_status": status}

    def bass_engine_status(self) -> dict[str, object]:
        with self._lock:
            self._require_running()
            if self._session is None:
                self.refresh()
            minimum, maximum, current = cast(OpoSession, self._session).bass_engine_status()
            self._bass_level = current
            self._generation += 1
            return {"min": minimum, "max": maximum, "level": current}

    def poll(self, wait: float = 0.2) -> ControllerSnapshot:
        with self._lock:
            self._require_running()
            if self._session is None:
                if self._status is not None and profile_for_product(
                    self._status.product_id
                ) is None:
                    return self.snapshot()
                return self.refresh()
            try:
                batch = cast(OpoSession, self._session).poll(wait)
            except OSError:
                self._reconnect_count += 1
                return self.refresh()
            else:
                self._apply_batch(batch)
                self._expire_find()
                self._refresh_phone_app_state()
            return self.snapshot()


    def _refresh_phone_app_state(self) -> None:
        """Re-read the state the phone app owns (feature switches, bass level).

        The device pushes most changes, but a change made while the earbuds
        sleep may only reach the device later. A slow refresh keeps the panel
        in sync without waiting for the next push.
        """
        if self._session is None:
            return
        now = monotonic()
        if now - self._last_state_refresh < 5.0:
            return
        self._last_state_refresh = now
        profile = profile_for_product(self._status.product_id) if self._status else None
        if profile is None:
            return
        try:
            if "feature_switches" in profile.capabilities:
                switches = cast(OpoSession, self._session).feature_switches(
                    tuple(FEATURE_SWITCH_NAMES))
                self._feature_switches.update({
                    name: switches[feature_id]
                    for feature_id, name in FEATURE_SWITCH_NAMES.items()
                    if feature_id in switches
                })
            if "bass_engine" in profile.capabilities:
                _minimum, _maximum, current = cast(OpoSession, self._session).bass_engine_status()
                self._bass_level = current
        except (OSError, RuntimeError):
            # The next poll or reconnect recovers; a failed refresh must not
            # break the session.
            return
        self._generation += 1

    def shutdown(self) -> ControllerSnapshot:
        with self._lock:
            if self._running and self._session is not None and self._find_state().state != "stopped":
                self.find_earbuds(False)
            self._running = False
            self._close_session()
            self.address = self._selected_address
            self._status = None
            self._feature_switches.clear()
            self._advertised_event_codes = ()
            self._notification_event_codes = ()
            self._ignored_frames = 0
            self._eq_status = None
            self._bass_level = None
            self._touch_bindings = ()
            self._hold_cycle_mask = None
            self._generation += 1
            return self.snapshot()

    def snapshot(self) -> ControllerSnapshot:
        with self._lock:
            return ControllerSnapshot(
                status=self._status,
                feature_switches=dict(self._feature_switches),
                session_connected=self._session is not None,
                advertised_event_codes=self._advertised_event_codes,
                notification_event_codes=self._notification_event_codes,
                ignored_frames=self._ignored_frames,
                reconnect_count=self._reconnect_count,
                generation=self._generation,
                eq_status=self._eq_status,
                bass_level=self._bass_level,
                touch_bindings=self._touch_bindings,
                hold_cycle_mask=self._hold_cycle_mask,
                find_state=self._find_state().state,
                find_device_id=self._find_device_id(),
            )

    def _connect_session(self) -> None:
        if self._status is None:
            raise RuntimeError("controller has no device status")
        session = self.backend.open_session(self.address, status=self._status)
        session.__enter__()
        try:
            batch = session.authenticate_and_subscribe()
        except Exception:
            session.__exit__(None, None, None)
            raise
        self._session = session
        self._advertised_event_codes = session.advertised_event_codes
        self._apply_batch(batch)

    def _close_session(self) -> None:
        key = self._find_key()
        current = self._find_state()
        if key is not None and current.state == "ringing":
            self._find_states[key] = replace(current, state="unknown")
        self._touch_bindings = ()
        self._hold_cycle_mask = None
        if self._session is not None:
            self._session.__exit__(None, None, None)
            self._session = None

    def _apply_batch(self, batch: EventBatch) -> None:
        self._ignored_frames += batch.ignored_frames
        for event in batch.events:
            if event.kind == "battery" and self._status is not None:
                self._update_battery(cast(dict[str, dict[str, int | bool]], event.data))
            elif event.kind == "anc" and self._status is not None:
                self._status = replace(
                    self._status,
                    anc=cast(str | None, event.data.get("mode")),
                    anc_level=cast(str | None, event.data.get("level")),
                )
            elif event.kind == "firmware" and self._status is not None:
                self._status = replace(self._status,
                    firmware_version=cast(str | None, event.data["version"]),
                    remote_version=tuple(VersionRecord(**record) for record in event.data["records"]))
            elif event.kind == "feature_switches":
                self._feature_switches.update(
                    {key: value for key, value in event.data.items() if isinstance(value, bool)}
                )
            elif event.kind == "notification":
                code = event.data.get("event_code")
                if isinstance(code, int):
                    self._notification_event_codes = (
                        self._notification_event_codes + (code,)
                    )[-32:]
            elif event.kind == "bass_level":
                level = event.data.get("level")
                if isinstance(level, int):
                    self._bass_level = level
            elif event.kind == "eq_changed":
                self._apply_eq_change(event.data.get("id"))
        if batch.events:
            self._generation += 1

    def _apply_eq_change(self, eq_id: object) -> None:
        """Follow an equalizer change that the phone app made on the device."""
        if not isinstance(eq_id, int) or self._eq_status is None:
            return
        profile = profile_for_product(self._eq_status.product_id)
        preset = None
        if profile is not None and profile.eq is not None:
            preset = next((item for item in profile.eq.presets
                           if item.eq_id == eq_id), None)
        custom = next((entry for entry in self._eq_status.custom_entries
                       if entry.eq_id == eq_id), None)
        if preset is not None:
            name, kind = preset.name, "factory"
        elif custom is not None:
            name, kind = custom.name, "custom"
        else:
            name, kind = f"Unknown ({eq_id})", "unknown"
        self._eq_status = replace(
            self._eq_status, current_id=eq_id, current_name=name, current_kind=kind)

    def _update_battery(self, battery: dict[str, dict[str, int | bool]] | None) -> None:
        if self._status is None:
            return
        profile = profile_for_product(self._status.product_id)
        if profile and "case_battery" in profile.capabilities:
            battery = self._case_battery_cache.merge(self._status, battery)
        elif battery is not None:
            battery = {name: value for name, value in battery.items() if name != "case"}
        self._status = replace(self._status, battery=battery)

    def _require_running(self) -> None:
        if not self._running:
            raise RuntimeError("controller is not running")
