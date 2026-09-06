"""Elapsed ANC phases only: no wall-clock times, identifiers, or packet data."""

from time import monotonic


class AncRequestError(RuntimeError):
    def __init__(self, message: str, timings_ms: dict[str, float]) -> None:
        super().__init__(message)
        self.timings_ms = dict(timings_ms)


class PhaseTimer:
    def __init__(self) -> None:
        self.started = self.previous = monotonic()
        self.phases: dict[str, float] = {}

    def mark(self, phase: str) -> None:
        now = monotonic()
        self.phases[phase] = round((now - self.previous) * 1000, 3)
        self.previous = now

    def finish(self, total: str) -> dict[str, float]:
        return {**self.phases, total: round((monotonic() - self.started) * 1000, 3)}

    def elapsed(self, milestone: str) -> None:
        self.phases[milestone] = round((monotonic() - self.started) * 1000, 3)
