from __future__ import annotations

import argparse
import json

from .bluez import connected_devices, select_device
from .protocol import ANC_MODES, QUERY_ANC, QUERY_BATTERY, QUERY_BROADCAST_CODES, QUERY_CAPABILITIES, QUERY_PRODUCT_ID, QUERY_STATUS, SET_ANC, STATUS_QUERY_PAYLOAD, SUBSCRIBE_BROADCAST, parse_anc, parse_battery, parse_broadcast_codes, parse_product_id
from .transport import RfcommTransport


def _device_dict(device: object) -> dict[str, object]:
    return {
        "name": device.name,
        "connected": device.connected,
        "compatible": device.looks_compatible,
        "bluez_battery": device.battery,
        "transport": "RFCOMM channel 15" if device.looks_compatible else None,
    }


def protocol_status() -> dict[str, object]:
    device = select_device()
    result = _device_dict(device)
    with RfcommTransport(device.address) as transport:
        transport.query(QUERY_CAPABILITIES)
        product_frames = transport.query(QUERY_PRODUCT_ID)
        battery_frames = transport.query(QUERY_BATTERY)
        anc_frames = transport.query(QUERY_ANC, b"\x01\x01")
    result["product_id"] = next((value for frame in product_frames if (value := parse_product_id(frame))), None)
    result["battery"] = next((value for frame in battery_frames if (value := parse_battery(frame)) is not None), None)
    result["anc"] = next((value for frame in anc_frames if (value := parse_anc(frame))), None)
    return result


def set_anc(mode: str) -> dict[str, object]:
    device = select_device()
    with RfcommTransport(device.address) as transport:
        transport.query(QUERY_CAPABILITIES)
        product_frames = transport.query(QUERY_PRODUCT_ID)
        product_id = next((value for frame in product_frames if (value := parse_product_id(frame))), None)
        if product_id != "060C14":
            raise RuntimeError(f"refusing ANC write: expected verified Buds Pro product 060C14, got {product_id or 'no ID'}")
        broadcast_frames = transport.query(QUERY_BROADCAST_CODES)
        broadcast_codes = next(
            (value for frame in broadcast_frames if (value := parse_broadcast_codes(frame)) is not None),
            None,
        )
        if broadcast_codes is None:
            raise RuntimeError("refusing ANC write: device did not return notification capabilities")
        transport.query(SUBSCRIBE_BROADCAST, bytes((len(broadcast_codes),)) + broadcast_codes)
        transport.query(QUERY_STATUS, STATUS_QUERY_PAYLOAD, sequence=0, wait=0.3)
        transport.query(SET_ANC, bytes((1, 1, ANC_MODES[mode])), wait=0.3)
        state_frames = transport.query(QUERY_ANC, b"\x01\x01", wait=0.3)
    observed = next((value for frame in state_frames if (value := parse_anc(frame))), None)
    if observed != mode:
        raise RuntimeError(f"ANC verification failed: requested {mode}, device reported {observed or 'no state'}")
    return {"name": device.name, "product_id": product_id, "anc": observed, "verified": True}


def main() -> None:
    parser = argparse.ArgumentParser(prog="oneplus-buds")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("devices", help="list connected candidate devices")
    subparsers.add_parser("status", help="query product, battery and ANC state")
    anc_parser = subparsers.add_parser("anc", help="query or safely set ANC state")
    anc_parser.add_argument("mode", choices=("status", "on", "off", "transparency"))
    args = parser.parse_args()
    try:
        if args.command == "devices":
            output = [_device_dict(device) for device in connected_devices()]
        elif args.command == "status":
            output = protocol_status()
        elif args.mode == "status":
            output = {"anc": protocol_status()["anc"]}
        else:
            output = set_anc(args.mode)
        print(json.dumps(output, indent=2))
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"oneplus-buds: {error}\n")


if __name__ == "__main__":
    main()
