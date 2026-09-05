from __future__ import annotations

from dataclasses import dataclass

from .profiles import AncProfile

SOF = 0xAA

QUERY_CAPABILITIES = 0x0100
QUERY_BROADCAST_CODES = 0x0200
SUBSCRIBE_BROADCAST = 0x0205
QUERY_PRODUCT_ID = 0x0103
QUERY_BATTERY = 0x0106
QUERY_ANC = 0x010C
QUERY_STATUS = 0x010D
SET_ANC = 0x0404
RESPONSE_SET_ANC = 0x8404

RESPONSE_PRODUCT_ID = 0x8103
RESPONSE_BATTERY = 0x8106
RESPONSE_ANC = 0x810C
NOTIFY_STATE = 0x0204
RESPONSE_BROADCAST_CODES = 0x8200

# Authentication frames have a legacy envelope that is not representable by
# encode_frame: HELLO carries a trailing 0x12 beyond its zero inner length.
HELLO = bytes.fromhex("AA 07 00 00 00 01 23 00 00 12")
REGISTER = bytes.fromhex("AA 0C 00 00 00 85 41 05 00 00 B5 50 A0 69")
STATUS_QUERY_PAYLOAD = bytes.fromhex("0B 05 04 0B 11 13 18 06 1B 1C 27 28")


@dataclass(frozen=True)
class Frame:
    command: int
    sequence: int
    payload: bytes


@dataclass(frozen=True)
class AncState:
    mode: str
    level: str | None
    index: int


def encode_frame(command: int, sequence: int, payload: bytes = b"") -> bytes:
    if not 0 <= sequence <= 0xFF:
        raise ValueError("sequence must fit in one byte")
    if len(payload) > 0xFFFF:
        raise ValueError("payload is too long")
    total_length = 7 + len(payload)
    if total_length > 0xFF:
        raise ValueError("frame is too long for OPOv1 length field")
    return bytes(
        (
            SOF,
            total_length,
            0,
            0,
            command & 0xFF,
            command >> 8,
            sequence,
            len(payload) & 0xFF,
            len(payload) >> 8,
        )
    ) + payload


def decode_frame(data: bytes) -> Frame:
    if len(data) < 9 or data[0] != SOF:
        raise ValueError("not an OPOv1 frame")
    expected = data[1] + 2
    if len(data) != expected:
        raise ValueError(f"frame length mismatch: expected {expected}, got {len(data)}")
    payload_length = data[7] | data[8] << 8
    actual_payload_length = len(data) - 9
    # Buds Pro capability response 0x8100 reports an inner length one byte
    # shorter than the payload delimited by the authoritative outer length.
    command = data[4] | data[5] << 8
    if payload_length != actual_payload_length and not (
        (command == 0x8100 and payload_length + 1 == actual_payload_length)
        or command == NOTIFY_STATE
    ):
        raise ValueError("payload length mismatch")
    return Frame(command, data[6], data[9:])


class FrameStream:
    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[Frame]:
        self._buffer.extend(data)
        frames: list[Frame] = []
        while self._buffer:
            try:
                start = self._buffer.index(SOF)
            except ValueError:
                self._buffer.clear()
                break
            del self._buffer[:start]
            if len(self._buffer) < 2:
                break
            frame_length = self._buffer[1] + 2
            if frame_length < 9:
                del self._buffer[0]
                continue
            if len(self._buffer) < frame_length:
                break
            raw = bytes(self._buffer[:frame_length])
            del self._buffer[:frame_length]
            frames.append(decode_frame(raw))
        return frames


def parse_product_id(frame: Frame) -> str | None:
    if frame.command != RESPONSE_PRODUCT_ID or len(frame.payload) < 4:
        return None
    if frame.payload[0] != 0:
        return None
    return frame.payload[1:4][::-1].hex().upper()


def parse_battery(frame: Frame) -> dict[str, dict[str, int | bool]] | None:
    if frame.command != RESPONSE_BATTERY:
        return None
    names = {1: "left", 2: "right", 3: "case"}
    result: dict[str, dict[str, int | bool]] = {}
    payload = frame.payload
    # Buds Pro prefixes the component pairs with their count. Some related
    # implementations report pair-only responses, so accept both forms.
    if payload and len(payload) == 1 + payload[0] * 2:
        payload = payload[1:]
    for offset in range(0, len(payload) - 1, 2):
        component, raw = payload[offset : offset + 2]
        if component in names:
            result[names[component]] = {
                "percentage": raw & 0x7F,
                "charging": bool(raw & 0x80),
            }
    return result


def parse_anc_state(frame: Frame, profile: AncProfile) -> AncState | None:
    if frame.command not in (RESPONSE_ANC, NOTIFY_STATE):
        return None
    payload = frame.payload
    for offset in range(len(payload) - 2):
        if payload[offset : offset + 2] == b"\x01\x01":
            bitmap = int.from_bytes(payload[offset + 2 :], "little")
            if bitmap == 0:
                return None
            index = (bitmap & -bitmap).bit_length() - 1
            mode = profile.read_modes.get(index)
            level = profile.read_levels.get(index)
            if mode is None and level is not None:
                mode = "on"
            if mode is not None:
                return AncState(mode=mode, level=level, index=index)
    return None


def parse_anc(frame: Frame, profile: AncProfile) -> str | None:
    state = parse_anc_state(frame, profile)
    return state.mode if state else None


def parse_broadcast_codes(frame: Frame) -> bytes | None:
    if frame.command != RESPONSE_BROADCAST_CODES or len(frame.payload) < 2:
        return None
    status, count = frame.payload[:2]
    if status != 0 or len(frame.payload) < 2 + count:
        return None
    return frame.payload[2 : 2 + count]


def parse_set_anc_status(frame: Frame) -> int | None:
    if frame.command != RESPONSE_SET_ANC or not frame.payload:
        return None
    return frame.payload[0]
