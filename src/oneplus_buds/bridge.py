from __future__ import annotations

import re

from collections.abc import Callable, Mapping
from collections import deque
from threading import Event
from typing import TypeAlias

from .availability import Availability
from .controller import BudsController
from .case_battery import CaseBatteryCache, default_cache_directory
from .timing import AncRequestError
from .models import ControllerSnapshot, ControlResult, EqControlResult
from .profiles import compatibility_for_product, feature_capabilities, profile_for_product
from .report import build_snapshot_report, write_report
from .service import BudsServiceRunner, ServiceState
from .protocol import FEATURE_SWITCH_NAMES
from .touch import serialize_touch_controls, serialize_hold_cycle

JsonObject: TypeAlias = dict[str, object]
Dispatch: TypeAlias = Callable[[Callable[[], None]], None]

SCHEMA_VERSION = 1

# Reverse lookup for the feature switch names exposed to frontends.
FEATURE_SWITCH_IDS = {name: feature_id for feature_id, name in FEATURE_SWITCH_NAMES.items()}


def serialize_snapshot(snapshot: ControllerSnapshot) -> JsonObject:
    """Return the stable, address-free snapshot exposed to frontends."""
    profile = profile_for_product(snapshot.status.product_id) if snapshot.status else None
    capabilities = set(profile.capabilities) if profile else set()
    capabilities.update(feature_capabilities(profile, snapshot.feature_switches))
    return {
        "status": snapshot.status.to_dict() if snapshot.status is not None else None,
        "compatibility": compatibility_for_product(
            snapshot.status.product_id if snapshot.status else None
        ),
        "capabilities": sorted(capabilities),
        "anc_modes": sorted(profile.anc.write_indices)
        if profile and profile.can_write("anc") else [],
        "anc_labels": dict(profile.anc.level_labels) if profile else {},
        "eq": snapshot.eq_status.to_dict() if snapshot.eq_status else None,
        "eq_write_verified": bool(
            profile and profile.can_write("eq_preset")
            and profile.eq and profile.eq.write_verified
        ),
        "custom_eq_write_verified": bool(
            profile and profile.can_write("custom_eq")
            and profile.eq and profile.eq.custom_write_verified
        ),
        "custom_eq_max": profile.eq.custom_max if profile and profile.eq else None,
        "custom_eq_slots": len(snapshot.eq_status.custom_entries)
        if snapshot.eq_status else 0,
        "writable_features": sorted(profile.writable_features) if profile else [],
        "feature_labels": dict(profile.feature_labels)
        if profile and profile.feature_labels is not None else None,
        "feature_switches": dict(snapshot.feature_switches),
        "session_connected": snapshot.session_connected,
        "advertised_event_codes": list(snapshot.advertised_event_codes),
        "notification_event_codes": list(snapshot.notification_event_codes),
        "ignored_frames": snapshot.ignored_frames,
        "reconnect_count": snapshot.reconnect_count,
        "generation": snapshot.generation,
        "bass_level": snapshot.bass_level,
        "find_state": snapshot.find_state,
        "find_device_id": snapshot.find_device_id,
        "touch_controls": serialize_touch_controls(
            snapshot.touch_bindings, profile.touch_functions if profile else {},
            bool(profile and profile.can_write("touch") and snapshot.session_connected)),
        "hold_cycle": serialize_hold_cycle(
            snapshot.hold_cycle_mask if profile and profile.hold_cycle_supported else None,
            bool(profile and profile.can_write("hold_cycle") and snapshot.session_connected)),
    }


class BudsFrontendBridge:
    """Versioned frontend contract over one serialized controller."""

    def __init__(
        self,
        emit: Callable[[JsonObject], None],
        *,
        controller: BudsController | None = None,
        dispatch: Dispatch | None = None,
        availability: Availability | None = None,
        poll_interval: float = 0.5,
    ) -> None:
        self.controller = controller or BudsController(
            case_battery_cache=CaseBatteryCache(default_cache_directory()))
        self.emit = emit
        self.dispatch = dispatch or (lambda callback: callback())
        self._recent_errors: deque[str] = deque(maxlen=12)
        self.runner = BudsServiceRunner(
            self.controller,
            availability=availability,
            poll_interval=poll_interval,
            on_state=self._on_state,
            on_snapshot=self._on_snapshot,
        )

    def run(self, cancelled: Event) -> ControllerSnapshot:
        """Run the service lifecycle until the caller signals cancellation."""
        return self.runner.run(cancelled)

    def execute(
        self,
        command: str,
        parameters: Mapping[str, object] | None = None,
        *,
        request_id: str | int | None = None,
    ) -> JsonObject:
        """Execute one validated command and return a JSON-compatible response."""
        if parameters is not None and not isinstance(parameters, Mapping):
            return self._response(
                command,
                request_id,
                ok=False,
                error={"code": "invalid_parameters", "message": "parameters must be an object"},
            )
        params = dict(parameters or {})
        try:
            if command == "snapshot":
                self._require_parameters(command, params, set())
                result: object = serialize_snapshot(self.controller.snapshot())
            elif command == "refresh":
                self._require_parameters(command, params, set())
                snapshot = self.controller.refresh()
                result = serialize_snapshot(snapshot)
                self._on_snapshot(snapshot)
            elif command == "set_anc":
                self._require_parameters(command, params, {"mode"})
                mode = params["mode"]
                if not isinstance(mode, str) or not mode:
                    raise ValueError("set_anc parameter 'mode' must be a non-empty string")
                control, snapshot = self.controller.set_anc_with_snapshot(mode)
                result = self._serialize_control(control)
                self._on_snapshot(snapshot)
            elif command == "eq_status":
                self._require_parameters(command, params, set())
                result = self.controller.eq_status().to_dict()
                self._on_snapshot(self.controller.snapshot())
            elif command == "set_eq":
                self._require_parameters(command, params, {"preset"})
                preset = params["preset"]
                if not isinstance(preset, str) or not preset:
                    raise ValueError("set_eq parameter 'preset' must be a non-empty string")
                control = self.controller.set_eq(preset)
                self.controller.eq_status()
                result = self._serialize_eq_control(control)
                self._on_snapshot(self.controller.snapshot())
            elif command == "set_custom_eq":
                self._require_parameters(command, params,
                    {"entry_id", "gains_db", "device_id"} if "device_id" in params
                    else {"entry_id", "gains_db"})
                entry_id, gains = params["entry_id"], params["gains_db"]
                if not isinstance(entry_id, int) or isinstance(entry_id, bool):
                    raise ValueError("set_custom_eq parameter 'entry_id' must be an integer")
                if not isinstance(gains, list) or any(
                    not isinstance(value, int) or isinstance(value, bool) for value in gains
                ):
                    raise ValueError("set_custom_eq parameter 'gains_db' must be an integer array")
                device_id = params.get("device_id")
                if "device_id" in params and (not isinstance(device_id, str)
                        or re.fullmatch(r"[0-9a-f]{64}", device_id) is None):
                    raise ValueError("set_custom_eq device_id must be a snapshot device token")
                control = self.controller.set_custom_eq(entry_id, tuple(gains),
                    **({"device_id": device_id} if device_id is not None else {}))
                self.controller.eq_status()
                result = self._serialize_eq_control(control)
                self._on_snapshot(self.controller.snapshot())
            elif command == "create_custom_eq":
                self._require_parameters(command, params,
                    {"name", "device_id"} if "device_id" in params else {"name"})
                name = params["name"]
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("create_custom_eq parameter 'name' must be a non-empty string")
                device_id = params.get("device_id")
                if "device_id" in params and (not isinstance(device_id, str)
                        or re.fullmatch(r"[0-9a-f]{64}", device_id) is None):
                    raise ValueError("create_custom_eq device_id must be a snapshot device token")
                control = self.controller.create_custom_eq(
                    name, **({"device_id": device_id} if device_id is not None else {}))
                self.controller.eq_status()
                result = self._serialize_eq_control(control)
                self._on_snapshot(self.controller.snapshot())
            elif command == "rename_custom_eq":
                self._require_parameters(command, params,
                    {"entry_id", "name", "device_id"} if "device_id" in params
                    else {"entry_id", "name"})
                entry_id, name = params["entry_id"], params["name"]
                if not isinstance(entry_id, int) or isinstance(entry_id, bool):
                    raise ValueError("rename_custom_eq parameter 'entry_id' must be an integer")
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("rename_custom_eq parameter 'name' must be a non-empty string")
                device_id = params.get("device_id")
                if "device_id" in params and (not isinstance(device_id, str)
                        or re.fullmatch(r"[0-9a-f]{64}", device_id) is None):
                    raise ValueError("rename_custom_eq device_id must be a snapshot device token")
                control = self.controller.rename_custom_eq(
                    entry_id, name, **({"device_id": device_id} if device_id is not None else {}))
                self.controller.eq_status()
                result = self._serialize_eq_control(control)
                self._on_snapshot(self.controller.snapshot())
            elif command == "delete_custom_eq":
                self._require_parameters(command, params,
                    {"entry_id", "device_id"} if "device_id" in params else {"entry_id"})
                entry_id = params["entry_id"]
                if not isinstance(entry_id, int) or isinstance(entry_id, bool):
                    raise ValueError("delete_custom_eq parameter 'entry_id' must be an integer")
                device_id = params.get("device_id")
                if "device_id" in params and (not isinstance(device_id, str)
                        or re.fullmatch(r"[0-9a-f]{64}", device_id) is None):
                    raise ValueError("delete_custom_eq device_id must be a snapshot device token")
                control = self.controller.delete_custom_eq(
                    entry_id, **({"device_id": device_id} if device_id is not None else {}))
                self.controller.eq_status()
                result = self._serialize_eq_control(control)
                self._on_snapshot(self.controller.snapshot())
            elif command == "touch_controls":
                self._require_parameters(command, params, set())
                self.controller.touch_controls()
                snapshot = self.controller.snapshot()
                result = {"touch_controls": serialize_snapshot(snapshot)["touch_controls"]}
                self._on_snapshot(snapshot)
            elif command == "set_hold_cycle":
                self._require_parameters(command, params, {"modes"})
                modes = params["modes"]
                if not isinstance(modes, list) or any(not isinstance(value, str) for value in modes):
                    raise ValueError("set_hold_cycle parameter 'modes' must be a string array")
                result = self.controller.set_hold_cycle(tuple(modes))
                self._on_snapshot(self.controller.snapshot())
            elif command == "set_touch_control":
                self._require_parameters(command, params, {"side", "action", "function"})
                for key in ("side", "action", "function"):
                    if type(params[key]) is not int:
                        raise ValueError(f"set_touch_control parameter '{key}' must be an integer")
                result = self.controller.set_touch_control(params["side"], params["action"], params["function"])
                self._on_snapshot(self.controller.snapshot())
            elif command == "feature_switches":
                result = {"feature_switches": self.controller.feature_switches()}
            elif command == "set_feature_switch":
                self._require_parameters(command, params, {"feature", "enabled"})
                feature = params["feature"]
                enabled = params["enabled"]
                if isinstance(feature, str):
                    feature = FEATURE_SWITCH_IDS.get(feature)
                if not isinstance(feature, int) or isinstance(feature, bool):
                    raise ValueError("set_feature_switch parameter 'feature' must be a known feature")
                if not isinstance(enabled, bool):
                    raise ValueError("set_feature_switch parameter 'enabled' must be a boolean")
                result = self.controller.set_feature_switch(feature, enabled)
                self._on_snapshot(self.controller.snapshot())
            elif command == "find_earbuds":
                self._require_parameters(command, params,
                    {"ringing", "device_id"} if "device_id" in params else {"ringing"})
                ringing = params["ringing"]
                if not isinstance(ringing, bool):
                    raise ValueError("find_earbuds parameter 'ringing' must be a boolean")
                device_id = params.get("device_id")
                if device_id is not None and (not isinstance(device_id, str)
                        or re.fullmatch(r"[0-9a-f]{64}", device_id) is None):
                    raise ValueError("find_earbuds device_id must be a snapshot device token")
                result = self.controller.find_earbuds(ringing, device_id=device_id)
                self._on_snapshot(self.controller.snapshot())
            elif command == "set_bass_level":
                self._require_parameters(command, params, {"level"})
                level = params["level"]
                if not isinstance(level, int) or isinstance(level, bool):
                    raise ValueError("set_bass_level parameter 'level' must be an integer")
                result = self.controller.set_bass_level(level)
            elif command == "bass_status":
                self._require_parameters(command, params, set())
                result = self.controller.bass_engine_status()
            elif command == "save_diagnostic_report":
                self._require_parameters(command, params, {"path"})
                path = params["path"]
                if not isinstance(path, str) or not path:
                    raise ValueError(
                        "save_diagnostic_report parameter 'path' must be a non-empty string"
                    )
                report = build_snapshot_report(
                    self.controller.snapshot(), recent_errors=tuple(self._recent_errors)
                )
                filename = write_report(report, path)
                result = {"saved": True, "filename": filename}
            else:
                return self._response(
                    command,
                    request_id,
                    ok=False,
                    error={"code": "unknown_command", "message": f"unknown command: {command}"},
                )
        except ValueError as error:
            self._remember_error(error)
            return self._response(
                command,
                request_id,
                ok=False,
                error={"code": "invalid_parameters", "message": self._safe_error(error)},
            )
        except (OSError, RuntimeError) as error:
            if command in ("touch_controls", "set_touch_control", "set_hold_cycle"):
                self._on_snapshot(self.controller.snapshot())
            self._remember_error(error)
            return self._response(
                command,
                request_id,
                ok=False,
                error={
                    "code": "command_failed",
                    "message": self._safe_error(error),
                    **({"timings_ms": dict(error.timings_ms)}
                       if isinstance(error, AncRequestError) else {}),
                },
            )
        return self._response(command, request_id, ok=True, result=result)

    def _on_state(self, state: ServiceState) -> None:
        if state.error:
            self._remember_error(RuntimeError(state.error))
        event: JsonObject = {
            "schema_version": SCHEMA_VERSION,
            "type": "connection",
            "connection": state.connection,
            "attempt": state.attempt,
            "retry_delay": state.retry_delay,
            "error": state.error,
        }
        self._dispatch_event(event)

    def _on_snapshot(self, snapshot: ControllerSnapshot) -> None:
        event: JsonObject = {
            "schema_version": SCHEMA_VERSION,
            "type": "snapshot",
            "snapshot": serialize_snapshot(snapshot),
        }
        self._dispatch_event(event)

    def _dispatch_event(self, event: JsonObject) -> None:
        self.dispatch(lambda: self.emit(event))

    def _response(
        self,
        command: str,
        request_id: str | int | None,
        *,
        ok: bool,
        result: object | None = None,
        error: JsonObject | None = None,
    ) -> JsonObject:
        return {
            "schema_version": SCHEMA_VERSION,
            "type": "command_response",
            "request_id": request_id,
            "command": command,
            "ok": ok,
            "result": result,
            "error": error,
        }

    def _require_parameters(
        self,
        command: str,
        parameters: Mapping[str, object],
        expected: set[str],
    ) -> None:
        supplied = set(parameters)
        if supplied != expected:
            raise ValueError(
                f"{command} requires parameters {sorted(expected)}; received {sorted(supplied)}"
            )

    def _safe_error(self, error: Exception) -> str:
        return re.sub(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", "[device]", str(error))

    def _remember_error(self, error: Exception) -> None:
        self._recent_errors.append(self._safe_error(error))

    @staticmethod
    def _serialize_control(result: ControlResult) -> JsonObject:
        return result.to_dict()

    @staticmethod
    def _serialize_eq_control(result: EqControlResult) -> JsonObject:
        return result.to_dict()
