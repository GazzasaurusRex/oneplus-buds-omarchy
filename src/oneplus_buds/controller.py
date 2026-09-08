from __future__ import annotations

from dataclasses import replace
from threading import RLock
from typing import cast

from .lifecycle_trace import mark
from .api import BudsBackend
from .models import ControllerSnapshot, ControlResult, EventBatch, StatusResult
from .protocol import VersionRecord
from .session import OpoSession
from .timing import AncRequestError, PhaseTimer


class BudsController:
    """Serialized state/session owner for a future service or frontend."""

    def __init__(self, backend: BudsBackend | None = None, address: str | None = None,
                 *, reuse_session: bool = True) -> None:
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

    def start(self) -> ControllerSnapshot:
        with self._lock:
            if self._running:
                return self.snapshot()
            mark("controller_start")
            self.shutdown()
            try:
                self._session, self._status, batch = self.backend.start_session(self._selected_address)
                self.address = self._status.device.address
                self._advertised_event_codes = self._session.advertised_event_codes
                self._apply_batch(batch)
                self._running = True
                mark("controller_usable")
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
            if self.reuse_session and self._running and mode in ("on", "off", "transparency"):
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

    def poll(self, wait: float = 0.2) -> ControllerSnapshot:
        with self._lock:
            self._require_running()
            if self._session is None:
                return self.refresh()
            try:
                batch = cast(OpoSession, self._session).poll(wait)
            except OSError:
                self._reconnect_count += 1
                return self.refresh()
            else:
                self._apply_batch(batch)
            return self.snapshot()

    def shutdown(self) -> ControllerSnapshot:
        with self._lock:
            self._running = False
            self._close_session()
            self.address = self._selected_address
            self._status = None
            self._feature_switches.clear()
            self._advertised_event_codes = ()
            self._notification_event_codes = ()
            self._ignored_frames = 0
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
        if batch.events:
            self._generation += 1

    def _require_running(self) -> None:
        if not self._running:
            raise RuntimeError("controller is not running")
