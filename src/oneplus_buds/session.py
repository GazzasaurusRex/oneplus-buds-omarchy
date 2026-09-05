from __future__ import annotations

from .bluez import Device
from .models import EventBatch, SafeEvent
from .profiles import DeviceProfile
from .protocol import (
    HELLO,
    NOTIFY_STATE,
    QUERY_BROADCAST_CODES,
    QUERY_CAPABILITIES,
    REGISTER,
    RESPONSE_ANC,
    RESPONSE_BATTERY,
    RESPONSE_STATUS,
    SUBSCRIBE_BROADCAST,
    Frame,
    parse_anc_state,
    parse_battery,
    parse_broadcast_codes,
    parse_feature_switches,
)
from .transport import RfcommTransport


class OpoSession:
    def __init__(self, device: Device, profile: DeviceProfile) -> None:
        self.device = device
        self.profile = profile
        self._transport = RfcommTransport(device.address, connect_attempts=4)
        self._connected = False
        self.advertised_event_codes: tuple[int, ...] = ()

    def __enter__(self) -> "OpoSession":
        self._transport.__enter__()
        self._connected = True
        return self

    def __exit__(self, *args: object) -> None:
        self._connected = False
        self._transport.__exit__(*args)

    def authenticate_and_subscribe(self) -> EventBatch:
        self._require_connected()
        frames: list[Frame] = []
        frames.extend(self._transport.query(QUERY_CAPABILITIES))
        frames.extend(self._transport.exchange_raw(HELLO, wait=2.0))
        frames.extend(self._transport.exchange_raw(REGISTER, wait=1.5))
        advertised_frames = self._transport.query(QUERY_BROADCAST_CODES, wait=0.5)
        frames.extend(advertised_frames)
        advertised = next(
            (codes for frame in advertised_frames if (codes := parse_broadcast_codes(frame)) is not None),
            b"",
        )
        self.advertised_event_codes = tuple(advertised)
        if advertised:
            payload = bytes((len(advertised),)) + advertised
            frames.extend(self._transport.query(SUBSCRIBE_BROADCAST, payload, wait=0.5))
        return self._redact(frames)

    def poll(self, wait: float = 0.2) -> EventBatch:
        self._require_connected()
        return self._redact(self._transport.receive(wait))

    def _redact(self, frames: list[Frame]) -> EventBatch:
        events: list[SafeEvent] = []
        ignored = 0
        for frame in frames:
            event = self._safe_event(frame)
            if event is None:
                ignored += 1
            else:
                events.append(event)
        return EventBatch(tuple(events), ignored)

    def _safe_event(self, frame: Frame) -> SafeEvent | None:
        if frame.command == RESPONSE_BATTERY:
            battery = parse_battery(frame)
            return SafeEvent("battery", battery) if battery is not None else None
        if frame.command == RESPONSE_ANC:
            state = parse_anc_state(frame, self.profile.anc)
            if state is not None:
                return SafeEvent("anc", {"mode": state.mode, "level": state.level})
            return None
        if frame.command == RESPONSE_STATUS:
            switches = parse_feature_switches(frame)
            return SafeEvent("feature_switches", switches) if switches is not None else None
        if frame.command == NOTIFY_STATE and frame.payload:
            return SafeEvent("notification", {"event_code": frame.payload[0]})
        return None

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("session is not connected")
