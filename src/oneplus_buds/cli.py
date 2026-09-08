from __future__ import annotations

import argparse
import json

from .backend import (device_summary, diagnostics_report, query_capabilities, query_eq,
                      query_status, set_anc, set_custom_eq, set_eq)
from .bluez import connected_devices


def main() -> None:
    parser = argparse.ArgumentParser(prog="oneplus-buds")
    parser.add_argument("--device", metavar="ADDRESS", help="select a connected device by Bluetooth address")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("devices", help="list connected candidate devices")
    subparsers.add_parser("status", help="query product, battery and ANC state")
    subparsers.add_parser("capabilities", help="show verified capabilities for the selected device")
    diagnostics = subparsers.add_parser("diagnostics", help="produce a privacy-safe compatibility report")
    diagnostics.add_argument("--report", action="store_true", help="emit a pasteable JSON report")
    anc_parser = subparsers.add_parser("anc", help="query or safely set ANC state")
    anc_parser.add_argument(
        "mode",
        choices=("status", "on", "off", "transparency", "light", "medium", "deep", "smart"),
    )
    eq_parser = subparsers.add_parser("eq", help="query or safely set native earbud EQ")
    eq_commands = eq_parser.add_subparsers(dest="eq_command", required=True)
    eq_commands.add_parser("status", help="read current native EQ and device-declared bands")
    eq_commands.add_parser("list", help="list factory presets and custom entries")
    eq_set = eq_commands.add_parser("set", help="select a factory or device-declared custom EQ")
    eq_set.add_argument("preset", help="preset key, numeric factory id, or custom:<id>")
    eq_custom = eq_commands.add_parser("custom", help="update an existing device-declared custom curve")
    eq_custom.add_argument("entry_id", type=int, help="custom entry id returned by eq status")
    eq_custom.add_argument("gains", nargs="+", type=int, help="one whole-dB gain per reported band")
    args = parser.parse_args()
    try:
        if args.command == "devices":
            output = [
                device_summary(device, include_address=True)
                for device in connected_devices()
                if device.looks_compatible
            ]
        elif args.command == "status":
            output = query_status(args.device)
        elif args.command == "capabilities":
            output = query_capabilities(args.device)
        elif args.command == "diagnostics":
            output = diagnostics_report(args.device)
        elif args.command == "eq":
            if args.eq_command == "status":
                output = query_eq(args.device)
            elif args.eq_command == "list":
                state = query_eq(args.device)
                output = {
                    "current": {key: state[key] for key in ("current_id", "current_name", "current_kind")},
                    "presets": state["presets"],
                    "custom_entries": state["custom_entries"],
                    "gain_step_db": state["gain_step_db"],
                }
            elif args.eq_command == "custom":
                output = set_custom_eq(args.entry_id, tuple(args.gains), args.device)
            else:
                output = set_eq(args.preset, args.device)
        elif args.mode == "status":
            status = query_status(args.device)
            output = {"anc": status["anc"], "anc_level": status["anc_level"]}
        else:
            output = set_anc(args.mode, args.device)
        print(json.dumps(output, indent=2))
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"oneplus-buds: {error}\n")


if __name__ == "__main__":
    main()
