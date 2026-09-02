from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

DEVICE_RE = re.compile(r"^Device ([0-9A-F:]{17}) (.+)$", re.MULTILINE)
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

    @property
    def looks_compatible(self) -> bool:
        return "oneplus" in self.name.lower() and bool(OPO_UUIDS.intersection(self.uuids))


def _bluetoothctl(*arguments: str) -> str:
    completed = subprocess.run(
        ("bluetoothctl", *arguments),
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout


def connected_devices() -> list[Device]:
    listed = _bluetoothctl("devices", "Connected")
    devices: list[Device] = []
    for address, listed_name in DEVICE_RE.findall(listed):
        info = _bluetoothctl("info", address)
        values: dict[str, list[str]] = {}
        for line in info.splitlines():
            if ":" not in line:
                continue
            key, value = line.strip().split(":", 1)
            values.setdefault(key, []).append(value.strip())
        name = values.get("Name", [listed_name])[0]
        uuids = tuple(
            match.group(1).lower()
            for value in values.get("UUID", [])
            if (match := re.search(r"\(([0-9a-fA-F-]{36})\)$", value))
        )
        battery_match = re.match(r"0x[0-9a-f]+ \((\d+)\)", values.get("Battery Percentage", [""])[0])
        devices.append(
            Device(
                address=address,
                name=name,
                connected=values.get("Connected", ["no"])[0] == "yes",
                uuids=uuids,
                battery=int(battery_match.group(1)) if battery_match else None,
            )
        )
    return devices


def select_device() -> Device:
    matches = [device for device in connected_devices() if device.looks_compatible]
    if not matches:
        raise RuntimeError("no connected OPO-compatible OnePlus earbuds found")
    if len(matches) > 1:
        raise RuntimeError("multiple compatible devices connected; explicit selection is not implemented yet")
    return matches[0]

