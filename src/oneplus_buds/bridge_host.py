from __future__ import annotations

import json
import signal
import sys
from collections.abc import Callable
from threading import Event, Lock, Thread
from typing import Protocol, TextIO

from .lifecycle_trace import mark
from .bridge import BudsFrontendBridge, JsonObject, SCHEMA_VERSION


class FrontendBridge(Protocol):
    def run(self, cancelled: Event) -> object: ...

    def execute(
        self,
        command: str,
        parameters: object = None,
        *,
        request_id: str | int | None = None,
    ) -> JsonObject: ...


BridgeFactory = Callable[[Callable[[JsonObject], None]], FrontendBridge]


class BridgeProcessHost:
    """Newline-delimited JSON process adapter for ``BudsFrontendBridge``."""

    def __init__(
        self,
        input_stream: TextIO,
        output_stream: TextIO,
        *,
        bridge_factory: BridgeFactory = BudsFrontendBridge,
    ) -> None:
        self.input_stream = input_stream
        self.output_stream = output_stream
        self.cancelled = Event()
        self._write_lock = Lock()
        self.bridge = bridge_factory(self._write)

    def run(self) -> None:
        mark("host_start")
        service_worker = Thread(target=self._run_bridge, daemon=False)
        input_worker = Thread(target=self._read_requests, daemon=True)
        service_worker.start()
        input_worker.start()
        self.cancelled.wait()
        service_worker.join()

    def _run_bridge(self) -> None:
        try:
            self.bridge.run(self.cancelled)
        finally:
            self.cancelled.set()

    def _read_requests(self) -> None:
        try:
            for line in self.input_stream:
                if self.cancelled.is_set():
                    break
                response = self._handle_line(line)
                self._write(response)
        finally:
            self.cancelled.set()

    def stop(self) -> None:
        self.cancelled.set()

    def _handle_line(self, line: str) -> JsonObject:
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            return self._invalid_request(None, "request is not valid JSON")
        if not isinstance(request, dict):
            return self._invalid_request(None, "request must be an object")
        request_id = request.get("request_id")
        if request_id is not None and (
            isinstance(request_id, bool) or not isinstance(request_id, (str, int))
        ):
            return self._invalid_request(None, "request_id must be a string, integer, or null")
        if set(request) - {"request_id", "command", "parameters"}:
            return self._invalid_request(request_id, "request contains unknown fields")
        command = request.get("command")
        if not isinstance(command, str) or not command:
            return self._invalid_request(request_id, "command must be a non-empty string")
        try:
            return self.bridge.execute(
                command,
                request.get("parameters"),
                request_id=request_id,
            )
        except Exception:
            return {
                "schema_version": SCHEMA_VERSION,
                "type": "command_response",
                "request_id": request_id,
                "command": command,
                "ok": False,
                "result": None,
                "error": {"code": "internal_error", "message": "bridge command failed"},
            }

    def _invalid_request(self, request_id: object, message: str) -> JsonObject:
        return {
            "schema_version": SCHEMA_VERSION,
            "type": "command_response",
            "request_id": request_id,
            "command": None,
            "ok": False,
            "result": None,
            "error": {"code": "invalid_request", "message": message},
        }

    def _write(self, payload: JsonObject) -> None:
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        with self._write_lock:
            self.output_stream.write(encoded + "\n")
            self.output_stream.flush()
            if payload.get("type") == "connection":
                mark("frontend_connection_sent", connection=str(payload.get("connection")))
            elif payload.get("type") == "snapshot":
                snapshot = payload.get("snapshot") or {}
                if snapshot.get("session_connected"):
                    mark("frontend_snapshot_sent")


def main() -> None:
    mark("process_start")
    from .availability import BlueZAvailability
    availability = BlueZAvailability()
    availability.start()
    host = BridgeProcessHost(sys.stdin, sys.stdout, bridge_factory=lambda emit:
        BudsFrontendBridge(emit, availability=availability))
    signal.signal(signal.SIGINT, lambda *_args: host.stop())
    signal.signal(signal.SIGTERM, lambda *_args: host.stop())
    try:
        host.run()
    finally:
        availability.close()


if __name__ == "__main__":
    main()
