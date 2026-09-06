from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .bluez import Device
from .protocol import VersionRecord


@dataclass(frozen=True)
class StatusResult:
    device: Device
    product_id: str | None
    model: str | None
    remote_version: tuple[VersionRecord, ...]
    firmware_version: str | None
    battery: dict[str, dict[str, int | bool]] | None
    anc: str | None
    anc_level: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.device.name,
            "connected": self.device.connected,
            "compatible": self.device.looks_compatible,
            "bluez_battery": self.device.battery,
            "services_resolved": self.device.services_resolved,
            "transport": "RFCOMM channel 15" if self.device.looks_compatible else None,
            "product_id": self.product_id,
            "model": self.model,
            "remote_version": [asdict(record) for record in self.remote_version],
            "firmware_version": self.firmware_version,
            "battery": self.battery,
            "anc": self.anc,
            "anc_level": self.anc_level,
        }


@dataclass(frozen=True)
class CapabilityResult:
    model: str | None
    product_id: str | None
    compatibility: str
    capabilities: tuple[str, ...]
    anc_modes: tuple[str, ...]
    feature_switches: dict[str, bool]

    def to_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "product_id": self.product_id,
            "compatibility": self.compatibility,
            "capabilities": list(self.capabilities),
            "anc_modes": list(self.anc_modes),
            "feature_switches": self.feature_switches,
        }


@dataclass(frozen=True)
class ControlResult:
    name: str
    product_id: str
    anc: str
    anc_level: str | None
    set_status: int | None
    verified: bool
    timings_ms: dict[str, float] = field(default_factory=dict)
    verification_queries: int = 1

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SafeEvent:
    kind: str
    data: dict[str, object]


@dataclass(frozen=True)
class EventBatch:
    events: tuple[SafeEvent, ...]
    ignored_frames: int


@dataclass(frozen=True)
class ControllerSnapshot:
    status: StatusResult | None
    feature_switches: dict[str, bool]
    session_connected: bool
    advertised_event_codes: tuple[int, ...]
    notification_event_codes: tuple[int, ...]
    ignored_frames: int
    reconnect_count: int
    generation: int
