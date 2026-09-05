from __future__ import annotations

from dataclasses import replace
from threading import RLock
from typing import cast

from .api import BudsBackend
from .models import ControllerSnapshot, ControlResult, EventBatch, StatusResult
from .session import OpoSession


class BudsController:
    """Serialized state/session owner for a future service or frontend."""

    def __init__(self, backend: BudsBackend | None = None, address: str | None = None) -> None:
        self.backend = backend or BudsBackend()
        self.address = address
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

    def start(self) -> ControllerSnapshot:
        with self._lock:
            if self._running:
                return self.snapshot()
            self._status = self.backend.status(self.address)
            self.address = self._status.device.address
            self._running = True
            try:
                self._connect_session()
            except Exception:
                self._running = False
                self._close_session()
                raise
            return self.snapshot()

    def refresh(self) -> ControllerSnapshot:
        with self._lock:
            self._close_session()
            self._status = self.backend.status(self.address)
            self.address = self._status.device.address
            if self._running:
                self._connect_session()
            self._generation += 1
            return self.snapshot()

    def set_anc(self, mode: str) -> ControlResult:
        with self._lock:
            self._close_session()
            try:
                result = self.backend.set_anc(mode, self.address)
                if self._status is not None:
                    self._status = replace(
                        self._status,
                        anc=result.anc,
                        anc_level=result.anc_level,
                    )
                self._generation += 1
            except Exception:
                if self._running and self._status is not None:
                    try:
                        self._connect_session()
                    except Exception:
                        pass
                raise
            if self._running:
                self._connect_session()
            return result

    def poll(self, wait: float = 0.2) -> ControllerSnapshot:
        with self._lock:
            self._require_running()
            if self._session is None:
                self._connect_session()
            try:
                batch = cast(OpoSession, self._session).poll(wait)
            except OSError:
                self._close_session()
                self._reconnect_count += 1
                self._connect_session()
            else:
                self._apply_batch(batch)
            return self.snapshot()

    def shutdown(self) -> ControllerSnapshot:
        with self._lock:
            self._running = False
            self._close_session()
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
        if self._session is not None:
            self._session.__exit__(None, None, None)
            self._session = None

    def _apply_batch(self, batch: EventBatch) -> None:
        self._ignored_frames += batch.ignored_frames
        for event in batch.events:
            if event.kind == "battery" and self._status is not None:
                self._status = replace(
                    self._status,
                    battery=cast(dict[str, dict[str, int | bool]], event.data),
                )
            elif event.kind == "anc" and self._status is not None:
                self._status = replace(
                    self._status,
                    anc=cast(str | None, event.data.get("mode")),
                    anc_level=cast(str | None, event.data.get("level")),
                )
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
        if batch.events:
            self._generation += 1

    def _require_running(self) -> None:
        if not self._running:
            raise RuntimeError("controller is not running")
