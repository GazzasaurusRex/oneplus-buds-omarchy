from __future__ import annotations

import re

from collections.abc import Callable
from dataclasses import dataclass
from threading import Event
from typing import Literal

from .availability import Availability
from .lifecycle_trace import mark
from .controller import BudsController
from .models import ControllerSnapshot

ConnectionState = Literal["connecting", "connected", "reconnecting", "disconnected", "stopped"]


@dataclass(frozen=True)
class ServiceState:
    connection: ConnectionState
    attempt: int = 0
    retry_delay: float | None = None
    error: str | None = None


class BudsServiceRunner:
    """Blocking, cancellation-aware lifecycle policy around ``BudsController``."""

    def __init__(
        self,
        controller: BudsController | None = None,
        *,
        availability: Availability | None = None,
        poll_interval: float = 0.5,
        initial_retry_delay: float = 1.0,
        maximum_retry_delay: float = 30.0,
        on_state: Callable[[ServiceState], None] | None = None,
        on_snapshot: Callable[[ControllerSnapshot], None] | None = None,
    ) -> None:
        if poll_interval < 0:
            raise ValueError("poll_interval must not be negative")
        if initial_retry_delay <= 0:
            raise ValueError("initial_retry_delay must be positive")
        if maximum_retry_delay < initial_retry_delay:
            raise ValueError("maximum_retry_delay must be at least initial_retry_delay")
        self.controller = controller or BudsController()
        self.availability = availability
        self._attempt_token = 0
        self.poll_interval = poll_interval
        self.initial_retry_delay = initial_retry_delay
        self.maximum_retry_delay = maximum_retry_delay
        self.on_state = on_state
        self.on_snapshot = on_snapshot

    def run(self, cancelled: Event) -> ControllerSnapshot:
        """Run until cancellation, retrying expected connection failures."""
        attempt = 0
        retry_delay = self.initial_retry_delay
        connected = False
        mark("service_start")
        self._publish_state(ServiceState("connecting"))
        try:
            while not cancelled.is_set():
                self._attempt_token = self.availability.token() if self.availability else 0
                if not connected:
                    try:
                        mark("service_discovery_attempt")
                        snapshot = self.controller.start()
                    except (OSError, RuntimeError) as error:
                        attempt, retry_delay = self._back_off(
                            cancelled, error, attempt, retry_delay
                        )
                        if cancelled.is_set():
                            break
                        continue
                    connected = True
                    attempt = 0
                    retry_delay = self.initial_retry_delay
                    self._publish_state(ServiceState("connected"))
                    self._publish_snapshot(snapshot)
                try:
                    snapshot = self.controller.poll(0.0)
                except (OSError, RuntimeError) as error:
                    connected = False
                    attempt, retry_delay = self._back_off(
                        cancelled, error, attempt, retry_delay
                    )
                    if cancelled.is_set():
                        break
                    continue
                self._publish_snapshot(snapshot)
                cancelled.wait(self.poll_interval)
        finally:
            snapshot = self.controller.shutdown()
            self._publish_state(ServiceState("stopped"))
            self._publish_snapshot(snapshot)
        return snapshot

    def _back_off(
        self,
        cancelled: Event,
        error: Exception,
        attempt: int,
        retry_delay: float,
    ) -> tuple[int, float]:
        safe_error = self._safe_error(error)
        snapshot = self.controller.shutdown()
        self._publish_snapshot(snapshot)
        attempt += 1
        self._publish_state(
            ServiceState(
                "disconnected",
                attempt=attempt,
                retry_delay=retry_delay,
                error=safe_error,
            )
        )
        mark("service_retry_wait", delay_ms=int(retry_delay * 1000))
        was_cancelled = (self.availability.wait(cancelled, retry_delay, self._attempt_token)
                         if self.availability else cancelled.wait(retry_delay))
        if not was_cancelled:
            retry_delay = min(retry_delay * 2, self.maximum_retry_delay)
            self._publish_state(ServiceState("reconnecting", attempt=attempt))
        return attempt, retry_delay

    def _safe_error(self, error: Exception) -> str:
        return re.sub(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", "[device]", str(error))

    def _publish_state(self, state: ServiceState) -> None:
        if self.on_state is not None:
            self.on_state(state)

    def _publish_snapshot(self, snapshot: ControllerSnapshot) -> None:
        if self.on_snapshot is not None:
            self.on_snapshot(snapshot)
