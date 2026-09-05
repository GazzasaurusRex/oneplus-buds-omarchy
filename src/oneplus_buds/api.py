from __future__ import annotations

from .backend import read_capabilities, read_status, write_anc
from .bluez import Device, connected_devices, select_device
from .models import CapabilityResult, ControlResult, StatusResult
from .profiles import profile_for_product
from .session import OpoSession


class BudsBackend:
    def discover(self) -> tuple[Device, ...]:
        return tuple(device for device in connected_devices() if device.looks_compatible)

    def status(self, address: str | None = None) -> StatusResult:
        return read_status(address)

    def capabilities(self, address: str | None = None) -> CapabilityResult:
        return read_capabilities(address)

    def set_anc(self, mode: str, address: str | None = None) -> ControlResult:
        return write_anc(mode, address)

    def open_session(
        self,
        address: str | None = None,
        *,
        status: StatusResult | None = None,
    ) -> OpoSession:
        if status is None:
            device = select_device(address)
            status = read_status(device.address)
        else:
            device = status.device
            if address is not None and device.address.upper() != address.upper():
                raise ValueError("provided status belongs to a different Bluetooth address")
        profile = profile_for_product(status.product_id)
        if profile is None:
            raise RuntimeError("cannot open event session for an unknown product")
        return OpoSession(device, profile)
