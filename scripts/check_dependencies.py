#!/usr/bin/env python3
"""Read-only runtime preflight; does not connect to D-Bus or Bluetooth."""
from __future__ import annotations

import importlib.util
import shutil
import socket
import sys


def main() -> int:
    checks = [
        ("Python 3.11 or newer", sys.version_info >= (3, 11)),
        ("Linux Bluetooth RFCOMM sockets", sys.platform == "linux"
         and hasattr(socket, "AF_BLUETOOTH") and hasattr(socket, "BTPROTO_RFCOMM")),
        ("system dbus-python binding (Arch: python-dbus)", importlib.util.find_spec("dbus") is not None),
        ("Omarchy command", shutil.which("omarchy") is not None),
        ("Quickshell command", shutil.which("qs") is not None),
        ("BlueZ bluetoothctl command (Arch: bluez-utils)", shutil.which("bluetoothctl") is not None),
    ]
    for label, passed in checks:
        print(f"{'OK' if passed else 'MISSING'}: {label}")
    print("This checks local prerequisites only, not daemon state, shell API compatibility, or hardware support.")
    return 0 if all(passed for _, passed in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
