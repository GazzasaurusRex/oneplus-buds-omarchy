from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Event
from typing import Literal

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
        self._publish_state(ServiceState("connecting"))
        try:
            while not cancelled.is_set():
                if not connected:
                    try:
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
                    snapshot = self.controller.poll(self.poll_interval)
                except (OSError, RuntimeError) as error:
                    connected = False
                    attempt, retry_delay = self._back_off(
                        cancelled, error, attempt, retry_delay
                    )
                    if cancelled.is_set():
                        break
                    continue
                self._publish_snapshot(snapshot)
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
        self.controller.shutdown()
        attempt += 1
        self._publish_state(
            ServiceState(
                "disconnected",
                attempt=attempt,
                retry_delay=retry_delay,
                error=str(error),
            )
        )
        if not cancelled.wait(retry_delay):
            retry_delay = min(retry_delay * 2, self.maximum_retry_delay)
            self._publish_state(ServiceState("reconnecting", attempt=attempt))
        return attempt, retry_delay

    def _publish_state(self, state: ServiceState) -> None:
        if self.on_state is not None:
            self.on_state(state)

    def _publish_snapshot(self, snapshot: ControllerSnapshot) -> None:
        if self.on_snapshot is not None:
            self.on_snapshot(snapshot)
