from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar
from dataclasses import replace

from .lifecycle_trace import mark
from .bluez import Device, select_device
from .models import CapabilityResult, ControlResult, EqControlResult, EqStatusResult, StatusResult
from .profiles import compatibility_for_product, profile_for_product
from .report import build_status_report
from .protocol import (
    HELLO,
    QUERY_ANC,
    QUERY_BATTERY,
    QUERY_BROADCAST_CODES,
    QUERY_CAPABILITIES,
    QUERY_PRODUCT_ID,
    QUERY_REMOTE_VERSION,
    QUERY_STATUS,
    REGISTER,
    SET_ANC,
    STATUS_QUERY_PAYLOAD,
    SUBSCRIBE_BROADCAST,
    AncState,
    FEATURE_SWITCH_NAMES,
    Frame,
    format_firmware_version,
    parse_anc_state,
    parse_battery,
    parse_broadcast_codes,
    parse_feature_switches,
    parse_product_id,
    parse_remote_version,
    parse_set_anc_status,
)
from .transport import RfcommTransport
from .timing import AncRequestError, PhaseTimer
from .session import OpoSession

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
        "services_resolved": device.services_resolved,
        "transport": "RFCOMM channel 15" if device.looks_compatible else None,
    }
    if include_address:
        result["address"] = device.address
    return result


def read_status(address: str | None = None) -> StatusResult:
    mark("status.begin")
    device = select_device(address)
    mark("compatible_device_selected")
    with RfcommTransport(device.address, connect_attempts=4) as transport:
        transport.query(QUERY_CAPABILITIES)
        product_frames = transport.query(QUERY_PRODUCT_ID)
        version_frames = transport.query(QUERY_REMOTE_VERSION)
        battery_frames = transport.query(QUERY_BATTERY)
        anc_frames = transport.query(QUERY_ANC, b"\x01\x01")
    product_id = _first_parsed(product_frames, parse_product_id)
    profile = profile_for_product(product_id)
    anc_state = (
        _first_parsed(anc_frames, lambda frame: parse_anc_state(frame, profile.anc))
        if profile
        else None
    )
    mark("profile_resolved", product_id=product_id or "unknown")
    version_records = _first_parsed(version_frames, parse_remote_version)
    mark("status.end")
    return StatusResult(
        device=device,
        product_id=product_id,
        model=profile.name if profile else None,
        remote_version=version_records or (),
        firmware_version=format_firmware_version(version_records),
        battery=_first_parsed(battery_frames, parse_battery),
        anc=anc_state.mode if anc_state else None,
        anc_level=anc_state.level if anc_state else None,
    )


def query_status(address: str | None = None) -> dict[str, object]:
    return read_status(address).to_dict()


def read_capabilities(address: str | None = None) -> CapabilityResult:
    status = read_status(address)
    profile = profile_for_product(status.product_id)
    feature_switches = query_feature_switches(address)
    capabilities = set(profile.capabilities) if profile else set()
    capabilities.update(feature_switches)
    return CapabilityResult(
        model=status.model,
        product_id=status.product_id,
        compatibility=compatibility_for_product(status.product_id),
        capabilities=tuple(sorted(capabilities)),
        anc_modes=tuple(sorted(profile.anc.write_indices))
        if profile and profile.verified else (),
        feature_switches=feature_switches,
        eq_write_verified=bool(
            profile and profile.verified and profile.eq and profile.eq.write_verified
        ),
        eq_presets=tuple(
            {"id": preset.eq_id, "key": preset.key, "name": preset.name}
            for preset in profile.eq.presets
        ) if profile and profile.eq else (),
        supports_custom_eq=bool(profile and profile.eq and profile.eq.supports_custom),
        custom_eq_write_verified=bool(
            profile and profile.verified and profile.eq and profile.eq.custom_write_verified
        ),
    )


def query_capabilities(address: str | None = None) -> dict[str, object]:
    return read_capabilities(address).to_dict()


def query_feature_switches(address: str | None = None) -> dict[str, bool]:
    device = select_device(address)
    with RfcommTransport(device.address, connect_attempts=4) as transport:
        transport.query(QUERY_CAPABILITIES)
        transport.exchange_raw(HELLO, wait=2.0)
        transport.exchange_raw(REGISTER, wait=1.5)
        advertised_frames = transport.query(QUERY_BROADCAST_CODES, wait=0.5)
        advertised = _first_parsed(advertised_frames, parse_broadcast_codes)
        if advertised:
            payload = bytes((len(advertised),)) + advertised
            transport.query(SUBSCRIBE_BROADCAST, payload, wait=0.5)
        status_frames = transport.query(
            QUERY_STATUS,
            STATUS_QUERY_PAYLOAD,
            sequence=0,
            wait=0.8,
        )
    switches = _first_parsed(status_frames, parse_feature_switches) or {}
    return {
        name: switches[feature]
        for feature, name in FEATURE_SWITCH_NAMES.items()
        if feature in switches
    }


def write_anc(mode: str, address: str | None = None) -> ControlResult:
    timer = PhaseTimer()
    try:
        result = _write_anc(mode, address, timer)
    except (OSError, RuntimeError) as error:
        timer.mark("failed_phase")
        raise AncRequestError(str(error), timer.finish("backend_total")) from error
    return replace(result, timings_ms=timer.finish("backend_total"))


def _write_anc(mode: str, address: str | None, timer: PhaseTimer) -> ControlResult:
    device = select_device(address)
    timer.mark("discovery")
    with RfcommTransport(device.address, connect_attempts=4) as transport:
        timer.mark("write_connect")
        transport.query(QUERY_CAPABILITIES)
        product_frames = transport.query(QUERY_PRODUCT_ID)
        timer.mark("profile_queries")
        product_id = _first_parsed(product_frames, parse_product_id)
        profile = profile_for_product(product_id)
        if profile is None:
            raise RuntimeError(f"refusing ANC write: product {product_id or 'unknown'} has no protocol profile")
        if not profile.verified:
            raise RuntimeError(f"refusing ANC write: {profile.name} profile is not hardware-verified")
        if mode not in profile.anc.write_indices:
            raise RuntimeError(f"refusing ANC write: {mode} is not supported by {profile.name}")
        transport.exchange_raw(HELLO, wait=2.0)
        timer.mark("hello")
        register_frames = transport.exchange_raw(REGISTER, wait=1.5)
        timer.mark("register")
        write_frames = transport.query(
            SET_ANC,
            profile.anc.payload_for(mode),
            sequence=profile.anc.sequence_for(mode),
            wait=1.0,
        )
        timer.mark("set_exchange")
        set_status = _first_parsed(write_frames, parse_set_anc_status)

    timer.mark("write_close")
    try:
        with RfcommTransport(device.address, connect_attempts=12) as verifier:
            timer.mark("verify_connect")
            state_frames = verifier.query(QUERY_ANC, b"\x01\x01", sequence=0xF0, wait=0.3)
            timer.mark("verify_query")
    except OSError as error:
        raise RuntimeError(
            "ANC write sent but verification channel stayed busy; "
            f"register responses: {_frame_summary(register_frames)}; "
            f"write responses: {_frame_summary(write_frames)}"
        ) from error

    timer.mark("verify_close")
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
    return ControlResult(
        name=device.name,
        product_id=product_id,
        anc=observed.mode,
        anc_level=observed.level,
        set_status=set_status,
        verified=True,
    )


def set_anc(mode: str, address: str | None = None) -> dict[str, object]:
    return write_anc(mode, address).to_dict()


def read_eq(address: str | None = None) -> EqStatusResult:
    device = select_device(address)
    session, _status, _events = OpoSession.bootstrap(device)
    try:
        result, _batch = session.eq_status()
        return result
    finally:
        session.__exit__(None, None, None)


def query_eq(address: str | None = None) -> dict[str, object]:
    return read_eq(address).to_dict()


def write_eq(preset: str, address: str | None = None) -> EqControlResult:
    device = select_device(address)
    session, _status, _events = OpoSession.bootstrap(device)
    try:
        result, _batch = session.set_eq(preset)
        return result
    finally:
        session.__exit__(None, None, None)


def set_eq(preset: str, address: str | None = None) -> dict[str, object]:
    return write_eq(preset, address).to_dict()


def write_custom_eq(entry_id: int, gains_db: tuple[int, ...],
                    address: str | None = None) -> EqControlResult:
    device = select_device(address)
    session, _status, _events = OpoSession.bootstrap(device)
    try:
        result, _batch = session.set_custom_eq(entry_id, gains_db)
        return result
    finally:
        session.__exit__(None, None, None)


def set_custom_eq(entry_id: int, gains_db: tuple[int, ...],
                  address: str | None = None) -> dict[str, object]:
    return write_custom_eq(entry_id, gains_db, address).to_dict()


def diagnostics_report(address: str | None = None) -> dict[str, object]:
    device = select_device(address)
    status = read_status(device.address)
    return build_status_report(status)


def _frame_summary(frames: list[Frame]) -> str:
    return ", ".join(f"0x{frame.command:04x}:{frame.payload.hex()}" for frame in frames) or "none"
