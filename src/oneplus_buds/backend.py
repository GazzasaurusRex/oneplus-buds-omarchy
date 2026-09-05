from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from . import __version__
from .bluez import Device, select_device
from .profiles import profile_for_product
from .protocol import (
    HELLO,
    QUERY_ANC,
    QUERY_BATTERY,
    QUERY_CAPABILITIES,
    QUERY_PRODUCT_ID,
    REGISTER,
    SET_ANC,
    AncState,
    Frame,
    parse_anc_state,
    parse_battery,
    parse_product_id,
    parse_set_anc_status,
)
from .transport import RfcommTransport

T = TypeVar("T")


def _first_parsed(frames: list[Frame], parser: Callable[[Frame], T | None]) -> T | None:
    for frame in frames:
        value = parser(frame)
        if value is not None:
            return value
    return None


def device_summary(device: Device, *, include_address: bool = False) -> dict[str, object]:
    result: dict[str, object] = {
        "name": device.name,
        "connected": device.connected,
        "compatible": device.looks_compatible,
        "bluez_battery": device.battery,
        "transport": "RFCOMM channel 15" if device.looks_compatible else None,
    }
    if include_address:
        result["address"] = device.address
    return result


def query_status(address: str | None = None) -> dict[str, object]:
    device = select_device(address)
    result = device_summary(device)
    with RfcommTransport(device.address, connect_attempts=4) as transport:
        transport.query(QUERY_CAPABILITIES)
        product_frames = transport.query(QUERY_PRODUCT_ID)
        battery_frames = transport.query(QUERY_BATTERY)
        anc_frames = transport.query(QUERY_ANC, b"\x01\x01")
    product_id = _first_parsed(product_frames, parse_product_id)
    profile = profile_for_product(product_id)
    anc_state = (
        _first_parsed(anc_frames, lambda frame: parse_anc_state(frame, profile.anc))
        if profile
        else None
    )
    result.update(
        {
            "product_id": product_id,
            "model": profile.name if profile else None,
            "battery": _first_parsed(battery_frames, parse_battery),
            "anc": anc_state.mode if anc_state else None,
            "anc_level": anc_state.level if anc_state else None,
        }
    )
    return result


def query_capabilities(address: str | None = None) -> dict[str, object]:
    status = query_status(address)
    product_id = status.get("product_id")
    profile = profile_for_product(product_id if isinstance(product_id, str) else None)
    return {
        "model": status["model"],
        "product_id": product_id,
        "compatibility": "verified" if profile and profile.verified else "experimental",
        "capabilities": sorted(profile.capabilities) if profile else [],
        "anc_modes": sorted(profile.anc.write_indices) if profile else [],
    }


def set_anc(mode: str, address: str | None = None) -> dict[str, object]:
    device = select_device(address)
    with RfcommTransport(device.address, connect_attempts=4) as transport:
        transport.query(QUERY_CAPABILITIES)
        product_frames = transport.query(QUERY_PRODUCT_ID)
        product_id = _first_parsed(product_frames, parse_product_id)
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
        set_status = _first_parsed(write_frames, parse_set_anc_status)

    try:
        with RfcommTransport(device.address, connect_attempts=12) as verifier:
            state_frames = verifier.query(QUERY_ANC, b"\x01\x01", sequence=0xF0, wait=0.3)
    except OSError as error:
        raise RuntimeError(
            "ANC write sent but verification channel stayed busy; "
            f"register responses: {_frame_summary(register_frames)}; "
            f"write responses: {_frame_summary(write_frames)}"
        ) from error

    observed = _first_parsed(state_frames, lambda frame: parse_anc_state(frame, profile.anc))
    expected_mode = mode if mode in ("off", "transparency", "on") else "on"
    expected_level = mode if mode not in ("off", "transparency", "on") else None
    if not isinstance(observed, AncState) or observed.mode != expected_mode or (
        expected_level and observed.level != expected_level
    ):
        raise RuntimeError(
            f"ANC verification failed: requested {mode}, device reported {observed or 'no state'}; "
            f"register responses: {_frame_summary(register_frames)}; "
            f"write responses: {_frame_summary(write_frames)}"
        )
    return {
        "name": device.name,
        "product_id": product_id,
        "anc": observed.mode,
        "anc_level": observed.level,
        "set_status": set_status,
        "verified": True,
    }


def diagnostics_report(address: str | None = None) -> dict[str, object]:
    device = select_device(address)
    status = query_status(device.address)
    product_id = status.get("product_id")
    profile = profile_for_product(product_id if isinstance(product_id, str) else None)
    return {
        "backend_version": __version__,
        "device": {
            "reported_name": device.name,
            "model": status["model"],
            "product_id": product_id,
            "connected": device.connected,
            "protocol": "OPOv1/0xAA",
            "transport": "Bluetooth Classic RFCOMM channel 15",
            "service_uuids": sorted(device.uuids),
            "compatibility": "verified" if profile and profile.verified else "experimental",
        },
        "capabilities": sorted(profile.capabilities) if profile else [],
        "state": {
            "battery": status["battery"],
            "anc": status["anc"],
            "anc_level": status["anc_level"],
        },
        "privacy": "Bluetooth address and unrelated devices omitted",
    }


def _frame_summary(frames: list[Frame]) -> str:
    return ", ".join(f"0x{frame.command:04x}:{frame.payload.hex()}" for frame in frames) or "none"
