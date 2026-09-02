from __future__ import annotations

import argparse
import json
import time

from .bluez import connected_devices, select_device
from .profiles import profile_for_product
from .protocol import HELLO, QUERY_ANC, QUERY_BATTERY, QUERY_CAPABILITIES, QUERY_PRODUCT_ID, REGISTER, SET_ANC, parse_anc_state, parse_battery, parse_product_id
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
    product_id = next((value for frame in product_frames if (value := parse_product_id(frame))), None)
    profile = profile_for_product(product_id)
    anc_state = next(
        (value for frame in anc_frames if profile and (value := parse_anc_state(frame, profile.anc))),
        None,
    )
    result["product_id"] = product_id
    result["model"] = profile.name if profile else None
    result["battery"] = next((value for frame in battery_frames if (value := parse_battery(frame)) is not None), None)
    result["anc"] = anc_state.mode if anc_state else None
    result["anc_level"] = anc_state.level if anc_state else None
    return result


def set_anc(mode: str) -> dict[str, object]:
    device = select_device()
    with RfcommTransport(device.address) as transport:
        transport.query(QUERY_CAPABILITIES)
        product_frames = transport.query(QUERY_PRODUCT_ID)
        product_id = next((value for frame in product_frames if (value := parse_product_id(frame))), None)
        profile = profile_for_product(product_id)
        if profile is None:
            raise RuntimeError(f"refusing ANC write: product {product_id or 'unknown'} has no protocol profile")
        if not profile.verified:
            raise RuntimeError(f"refusing ANC write: {profile.name} profile is not hardware-verified")
        if mode not in profile.anc.write_indices:
            raise RuntimeError(f"refusing ANC write: {mode} is not supported by {profile.name}")
        transport.exchange_raw(HELLO, wait=2.0)
        register_frames = transport.exchange_raw(REGISTER, wait=1.5)
        write_frames = transport.query(
            SET_ANC,
            profile.anc.payload_for(mode),
            sequence=profile.anc.sequence_for(mode),
            wait=1.0,
        )

    # Buds Pro stops answering the ANC query in the control session. Verify in
    # a new socket after BlueZ releases channel 15.
    state_frames = []
    for attempt in range(12):
        time.sleep(1.0)
        try:
            with RfcommTransport(device.address) as verifier:
                state_frames = verifier.query(QUERY_ANC, b"\x01\x01", sequence=0xF0, wait=0.3)
            break
        except OSError as error:
            if error.errno != 16 or attempt == 11:
                responses = ", ".join(
                    f"0x{frame.command:04x}:{frame.payload.hex()}" for frame in write_frames
                ) or "none"
                registration = ", ".join(
                    f"0x{frame.command:04x}:{frame.payload.hex()}" for frame in register_frames
                ) or "none"
                raise RuntimeError(
                    "ANC write sent but verification channel stayed busy; "
                    f"register responses: {registration}; write responses: {responses}"
                ) from error
    observed = next((value for frame in state_frames if (value := parse_anc_state(frame, profile.anc))), None)
    expected_mode = mode if mode in ("off", "transparency", "on") else "on"
    expected_level = mode if mode not in ("off", "transparency", "on") else None
    if observed is None or observed.mode != expected_mode or (expected_level and observed.level != expected_level):
        registration = ", ".join(
            f"0x{frame.command:04x}:{frame.payload.hex()}" for frame in register_frames
        ) or "none"
        responses = ", ".join(
            f"0x{frame.command:04x}:{frame.payload.hex()}" for frame in write_frames
        ) or "none"
        raise RuntimeError(
            f"ANC verification failed: requested {mode}, device reported {observed or 'no state'}; "
            f"register responses: {registration}; write responses: {responses}"
        )
    return {
        "name": device.name,
        "product_id": product_id,
        "anc": observed.mode,
        "anc_level": observed.level,
        "verified": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="oneplus-buds")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("devices", help="list connected candidate devices")
    subparsers.add_parser("status", help="query product, battery and ANC state")
    anc_parser = subparsers.add_parser("anc", help="query or safely set ANC state")
    anc_parser.add_argument(
        "mode",
        choices=("status", "on", "off", "transparency", "light", "medium", "deep", "smart"),
    )
    args = parser.parse_args()
    try:
        if args.command == "devices":
            output = [_device_dict(device) for device in connected_devices()]
        elif args.command == "status":
            output = protocol_status()
        elif args.mode == "status":
            status = protocol_status()
            output = {"anc": status["anc"], "anc_level": status["anc_level"]}
        else:
            output = set_anc(args.mode)
        print(json.dumps(output, indent=2))
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"oneplus-buds: {error}\n")


if __name__ == "__main__":
    main()
