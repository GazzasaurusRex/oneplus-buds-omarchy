from __future__ import annotations

from dataclasses import dataclass

from .profiles import AncProfile

SOF = 0xAA

QUERY_CAPABILITIES = 0x0100
QUERY_BROADCAST_CODES = 0x0200
SUBSCRIBE_BROADCAST = 0x0205
QUERY_PRODUCT_ID = 0x0103
QUERY_REMOTE_VERSION = 0x0105
QUERY_BATTERY = 0x0106
QUERY_ANC = 0x010C
QUERY_STATUS = 0x010D
QUERY_EQ = 0x010F
QUERY_EQ_ALL = 0x0122
SET_ANC = 0x0404
SET_EQ = 0x0406
SET_EQ_DETAIL = 0x0418
RESPONSE_SET_ANC = 0x8404
RESPONSE_SET_EQ = 0x8406
RESPONSE_SET_EQ_DETAIL = 0x8418

RESPONSE_PRODUCT_ID = 0x8103
RESPONSE_REMOTE_VERSION = 0x8105
RESPONSE_BATTERY = 0x8106
RESPONSE_ANC = 0x810C
RESPONSE_STATUS = 0x810D
RESPONSE_EQ = 0x810F
RESPONSE_EQ_ALL = 0x8122
NOTIFY_STATE = 0x0204
NOTIFY_EQ = 0x0504
RESPONSE_BROADCAST_CODES = 0x8200

FEATURE_SWITCH_NAMES = {
    0x04: "wear_detection",
    0x06: "low_latency",
    0x0B: "hearing_enhancement",
    0x11: "multipoint",
    0x18: "high_quality_audio",
}

# Authentication frames have a legacy envelope that is not representable by
# encode_frame: HELLO carries a trailing 0x12 beyond its zero inner length.
HELLO = bytes.fromhex("AA 07 00 00 00 01 23 00 00 12")
REGISTER = bytes.fromhex("AA 0C 00 00 00 85 41 05 00 00 B5 50 A0 69")
STATUS_QUERY_PAYLOAD = bytes.fromhex("0B 05 04 0B 11 13 18 06 1B 1C 27 28")
EQ_ALL_QUERY_PAYLOAD = bytes.fromhex("01 05")


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


@dataclass(frozen=True)
class VersionRecord:
    component: int
    kind: int
    value: str


@dataclass(frozen=True)
class EqBand:
    frequency_hz: int
    gain_db: int


@dataclass(frozen=True)
class EqEntry:
    eq_id: int
    name: str
    selected: bool
    min_gain_db: int
    max_gain_db: int
    bands: tuple[EqBand, ...]


VERSION_COMPONENTS = {1: "left", 2: "right", 3: "case"}


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


def parse_remote_version(frame: Frame) -> tuple[VersionRecord, ...] | None:
    if frame.command != RESPONSE_REMOTE_VERSION or len(frame.payload) < 2:
        return None
    status, count = frame.payload[:2]
    if status != 0:
        return None
    try:
        fields = frame.payload[2:].decode("ascii").split(",")
    except UnicodeDecodeError:
        return None
    if len(fields) != count * 3:
        return None
    records: list[VersionRecord] = []
    for offset in range(0, len(fields), 3):
        component, kind, value = fields[offset : offset + 3]
        if not component.isdecimal() or not kind.isdecimal() or not value.isdecimal():
            return None
        records.append(VersionRecord(int(component), int(kind), value))
    return tuple(records)


def format_firmware_version(records: tuple[VersionRecord, ...] | None) -> str | None:
    if not records:
        return None
    components = {
        record.component: record.value
        for record in records
        if record.kind == 2 and record.component in VERSION_COMPONENTS
    }
    if 1 not in components or 2 not in components:
        return None
    return ".".join(components[component] for component in (1, 2, 3) if component in components)


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


def parse_feature_switches(frame: Frame) -> dict[int, bool] | None:
    if frame.command != RESPONSE_STATUS or len(frame.payload) < 2:
        return None
    status, count = frame.payload[:2]
    if status != 0 or len(frame.payload) < 2 + count * 2:
        return None
    result: dict[int, bool] = {}
    for offset in range(2, 2 + count * 2, 2):
        feature, value = frame.payload[offset : offset + 2]
        if value not in (0, 1):
            return None
        result[feature] = bool(value)
    return result


def parse_set_anc_status(frame: Frame) -> int | None:
    if frame.command != RESPONSE_SET_ANC or not frame.payload:
        return None
    return frame.payload[0]


def parse_eq_id(frame: Frame) -> int | None:
    if frame.command == RESPONSE_EQ:
        if len(frame.payload) != 2 or frame.payload[0] != 0:
            return None
        return frame.payload[1]
    if frame.command == NOTIFY_EQ and len(frame.payload) == 1:
        return frame.payload[0]
    return None


def parse_eq_entries(frame: Frame) -> tuple[EqEntry, ...] | None:
    """Parse the device-authored native EQ catalogue conservatively."""
    if frame.command != RESPONSE_EQ_ALL or len(frame.payload) < 2:
        return None
    status, count = frame.payload[:2]
    if status != 0:
        return None
    payload = frame.payload
    offset = 2
    entries: list[EqEntry] = []
    try:
        for _ in range(count):
            if offset + 5 > len(payload):
                return None
            selected = payload[offset]
            minimum = int.from_bytes(payload[offset + 1 : offset + 2], "little", signed=True)
            maximum = int.from_bytes(payload[offset + 2 : offset + 3], "little", signed=True)
            eq_id = payload[offset + 3]
            name_length = payload[offset + 4]
            offset += 5
            if selected not in (0, 1) or minimum > maximum or offset + name_length + 1 > len(payload):
                return None
            name = payload[offset : offset + name_length].decode("utf-8")
            offset += name_length
            band_count = payload[offset]
            offset += 1
            if band_count == 0 or offset + band_count * 3 > len(payload):
                return None
            bands: list[EqBand] = []
            frequencies: set[int] = set()
            for _ in range(band_count):
                frequency = int.from_bytes(payload[offset : offset + 2], "little")
                gain = int.from_bytes(payload[offset + 2 : offset + 3], "little", signed=True)
                offset += 3
                if frequency == 0 or frequency in frequencies or not minimum <= gain <= maximum:
                    return None
                frequencies.add(frequency)
                bands.append(EqBand(frequency, gain))
            entries.append(EqEntry(eq_id, name, bool(selected), minimum, maximum, tuple(bands)))
    except UnicodeDecodeError:
        return None
    if offset != len(payload) or len({entry.eq_id for entry in entries}) != len(entries):
        return None
    return tuple(entries)


def parse_set_eq_status(frame: Frame) -> int | None:
    if frame.command not in (RESPONSE_SET_EQ, RESPONSE_SET_EQ_DETAIL) or not frame.payload:
        return None
    return frame.payload[0]


def encode_eq_detail_payload(entry: EqEntry, gains_db: tuple[int, ...]) -> bytes:
    """Encode an update of an existing custom entry after strict validation."""
    if not 0 <= entry.eq_id <= 0xFF:
        raise ValueError("EQ id must fit in one byte")
    if len(gains_db) != len(entry.bands):
        raise ValueError(f"custom EQ requires exactly {len(entry.bands)} gains")
    if any(not isinstance(gain, int) or not entry.min_gain_db <= gain <= entry.max_gain_db
           for gain in gains_db):
        raise ValueError(
            f"custom EQ gains must be whole dB values from {entry.min_gain_db} to {entry.max_gain_db}"
        )
    name = entry.name.encode("utf-8")
    if len(name) > 0xFF or len(entry.bands) > 0xFF:
        raise ValueError("custom EQ definition is too large")
    payload = bytearray((2, entry.min_gain_db & 0xFF, entry.max_gain_db & 0xFF,
                         entry.eq_id, len(name)))
    payload.extend(name)
    payload.append(len(entry.bands))
    for band, gain in zip(entry.bands, gains_db, strict=True):
        if not 0 < band.frequency_hz <= 0xFFFF:
            raise ValueError("custom EQ frequency must fit in two bytes")
        payload.extend(band.frequency_hz.to_bytes(2, "little"))
        payload.append(gain & 0xFF)
    return bytes(payload)
