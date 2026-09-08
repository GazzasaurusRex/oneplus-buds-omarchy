from __future__ import annotations

import re

from collections.abc import Callable, Mapping
from threading import Event
from typing import TypeAlias

from .availability import Availability
from .controller import BudsController
from .timing import AncRequestError
from .models import ControllerSnapshot, ControlResult, EqControlResult
from .profiles import profile_for_product
from .service import BudsServiceRunner, ServiceState

JsonObject: TypeAlias = dict[str, object]
Dispatch: TypeAlias = Callable[[Callable[[], None]], None]

SCHEMA_VERSION = 1


def serialize_snapshot(snapshot: ControllerSnapshot) -> JsonObject:
    """Return the stable, address-free snapshot exposed to frontends."""
    profile = profile_for_product(snapshot.status.product_id) if snapshot.status else None
    capabilities = set(profile.capabilities) if profile else set()
    capabilities.update(snapshot.feature_switches)
    return {
        "status": snapshot.status.to_dict() if snapshot.status is not None else None,
        "compatibility": "verified" if profile and profile.verified else "experimental",
        "capabilities": sorted(capabilities),
        "anc_modes": sorted(profile.anc.write_indices) if profile else [],
        "eq": snapshot.eq_status.to_dict() if snapshot.eq_status else None,
        "eq_write_verified": bool(profile and profile.eq and profile.eq.write_verified),
        "custom_eq_write_verified": bool(
            profile and profile.eq and profile.eq.custom_write_verified
        ),
        "feature_switches": dict(snapshot.feature_switches),
        "session_connected": snapshot.session_connected,
        "advertised_event_codes": list(snapshot.advertised_event_codes),
        "notification_event_codes": list(snapshot.notification_event_codes),
        "ignored_frames": snapshot.ignored_frames,
        "reconnect_count": snapshot.reconnect_count,
        "generation": snapshot.generation,
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
        self.controller = controller or BudsController()
        self.emit = emit
        self.dispatch = dispatch or (lambda callback: callback())
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
                self._require_parameters(command, params, {"entry_id", "gains_db"})
                entry_id, gains = params["entry_id"], params["gains_db"]
                if not isinstance(entry_id, int) or isinstance(entry_id, bool):
                    raise ValueError("set_custom_eq parameter 'entry_id' must be an integer")
                if not isinstance(gains, list) or any(
                    not isinstance(value, int) or isinstance(value, bool) for value in gains
                ):
                    raise ValueError("set_custom_eq parameter 'gains_db' must be an integer array")
                control = self.controller.set_custom_eq(entry_id, tuple(gains))
                self.controller.eq_status()
                result = self._serialize_eq_control(control)
                self._on_snapshot(self.controller.snapshot())
            else:
                return self._response(
                    command,
                    request_id,
                    ok=False,
                    error={"code": "unknown_command", "message": f"unknown command: {command}"},
                )
        except ValueError as error:
            return self._response(
                command,
                request_id,
                ok=False,
                error={"code": "invalid_parameters", "message": self._safe_error(error)},
            )
        except (OSError, RuntimeError) as error:
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

    @staticmethod
    def _serialize_control(result: ControlResult) -> JsonObject:
        return result.to_dict()

    @staticmethod
    def _serialize_eq_control(result: EqControlResult) -> JsonObject:
        return result.to_dict()
