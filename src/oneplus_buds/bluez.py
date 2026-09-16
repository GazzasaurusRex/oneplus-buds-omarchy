from __future__ import annotations

from .lifecycle_trace import span

from dataclasses import dataclass
from typing import Any

BLUEZ_SERVICE = "org.bluez"
BLUEZ_ROOT = "/"
OBJECT_MANAGER = "org.freedesktop.DBus.ObjectManager"
DEVICE_INTERFACE = "org.bluez.Device1"
BATTERY_INTERFACE = "org.bluez.Battery1"

OPO_UUIDS = {
    "00001107-d102-11e1-9b23-00025b00a5a5",
    "0000079a-d102-11e1-9b23-00025b00a5a5",
}


@dataclass(frozen=True)
class Device:
    address: str
    name: str
    connected: bool
    uuids: tuple[str, ...]
    battery: int | None
    modalias: str | None = None
    services_resolved: bool = False

    @property
    def looks_compatible(self) -> bool:
        brand = self.name.lower()
        return ("oneplus" in brand or "oppo" in brand) and bool(
            OPO_UUIDS.intersection(self.uuids)
        )


def _managed_objects() -> dict[Any, dict[Any, dict[Any, Any]]]:
    try:
        import dbus
    except ImportError as error:
        raise RuntimeError(
            "direct BlueZ discovery requires the system dbus-python binding"
        ) from error

    bus = dbus.SystemBus()
    manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE, BLUEZ_ROOT), OBJECT_MANAGER)
    with span("bluez_discovery"):
        return manager.GetManagedObjects()


def connected_devices() -> list[Device]:
    devices: list[Device] = []
    for interfaces in _managed_objects().values():
        properties = interfaces.get(DEVICE_INTERFACE)
        if properties is None or not bool(properties.get("Connected", False)):
            continue
        battery_properties = interfaces.get(BATTERY_INTERFACE, {})
        percentage = battery_properties.get("Percentage")
        devices.append(
            Device(
                address=str(properties.get("Address", "")),
                name=str(properties.get("Name") or properties.get("Alias") or "Unknown device"),
                connected=True,
                uuids=tuple(str(uuid).lower() for uuid in properties.get("UUIDs", ())),
                battery=int(percentage) if percentage is not None else None,
                modalias=str(properties["Modalias"]) if "Modalias" in properties else None,
                services_resolved=bool(properties.get("ServicesResolved", False)),
            )
        )
    return devices


def select_device(address: str | None = None) -> Device:
    matches = [device for device in connected_devices() if device.looks_compatible]
    if address is not None:
        normalized = address.upper()
        selected = next((device for device in matches if device.address.upper() == normalized), None)
        if selected is None:
            raise RuntimeError(
                f"selected device {address} is not a connected compatible OnePlus/OPPO device"
            )
        return selected
    if not matches:
        raise RuntimeError("no connected OPO-compatible OnePlus/OPPO earbuds found")
    if len(matches) > 1:
        raise RuntimeError("multiple compatible devices connected; select one with --device ADDRESS")
    return matches[0]
