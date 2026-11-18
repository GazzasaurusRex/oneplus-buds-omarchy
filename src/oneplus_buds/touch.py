"""OPOv1 touch assignments, with UI labels separate from wire numbers."""
from dataclasses import dataclass

from .protocol import Frame, RESPONSE_TOUCH, RESPONSE_ANC


ACTION_LABELS = {1: "Single tap", 2: "Double tap", 3: "Triple tap",
                 4: "Touch & hold", 6: "Long hold"}
FUNCTION_LABELS = {
    0: "None", 1: "Play / pause", 2: "Play music", 3: "Voice assistant",
    5: "Previous track", 6: "Next track", 8: "Switch noise control",
    11: "Volume up", 12: "Volume down", 17: "Game mode",
}

HOLD_CYCLE_QUERY = b"\x02\x01"
HOLD_CYCLE_OPTIONS = (
    ("anc", "Noise cancellation", 2),
    ("off", "Off", 1),
    ("transparency", "Transparency", 4),
)


def hold_cycle_mask(modes: tuple[str, ...]) -> int:
    values = {key: bit for key, _, bit in HOLD_CYCLE_OPTIONS}
    if (not 2 <= len(modes) <= 3
            or any(not isinstance(mode, str) or mode not in values for mode in modes)
            or len(set(modes)) != len(modes)):
        raise ValueError("choose at least two distinct supported hold modes")
    return sum(values[mode] for mode in modes)


def parse_hold_cycle(frame: Frame) -> int:
    data = frame.payload
    if (frame.command != RESPONSE_ANC or len(data) != 4
            or data[:3] != b"\x00\x02\x01" or data[3] not in (3, 5, 6, 7)):
        raise ValueError("device returned malformed hold cycle")
    return data[3]


def serialize_hold_cycle(mask: int | None, writable: bool) -> dict[str, object] | None:
    if mask is None:
        return None
    return {"modes": [key for key, _, bit in HOLD_CYCLE_OPTIONS if mask & bit],
            "options": [{"value": key, "label": label} for key, label, _ in HOLD_CYCLE_OPTIONS],
            "min_selected": 2, "shared": True, "writable": writable}


@dataclass(frozen=True)
class TouchBinding:
    device_type: int
    button: int
    action: int
    function: int

    @property
    def key(self) -> tuple[int, int, int]:
        return self.device_type, self.button, self.action

    def write_payload(self) -> bytes:
        return bytes((1, self.device_type, self.button, self.action, self.function))


def parse_touch_bindings(frame: Frame) -> tuple[TouchBinding, ...]:
    data = frame.payload
    if (frame.command != RESPONSE_TOUCH or len(data) < 2 or data[0] != 0
            or len(data) != 2 + 4 * data[1]):
        raise ValueError("device returned malformed touch controls")
    bindings = tuple(TouchBinding(*data[i:i + 4]) for i in range(2, len(data), 4))
    if (len({binding.key for binding in bindings}) != len(bindings)
            or any(binding.device_type not in (1, 2, 4) or binding.button == 0
                   or binding.action == 0 for binding in bindings)):
        raise ValueError("device returned invalid or duplicate touch controls")
    return bindings


def serialize_touch_controls(bindings: tuple[TouchBinding, ...],
                             functions: dict[int, tuple[int, ...]],
                             writable: bool) -> list[dict[str, object]]:
    controls = []
    for binding in bindings:
        allowed = functions.get(binding.action, ()) if (
            writable and binding.device_type in (1, 2) and binding.button == 1) else ()
        controls.append({
            "side": binding.device_type,
            "side_label": {1: "Left", 2: "Right", 4: "Both"}[binding.device_type],
            "button": binding.button,
            "action": binding.action,
            "action_label": ACTION_LABELS.get(binding.action, f"Gesture {binding.action}"),
            "function": binding.function,
            "function_label": FUNCTION_LABELS.get(binding.function, f"Unknown ({binding.function})"),
            "options": [{"value": value, "label": FUNCTION_LABELS[value]} for value in allowed],
            "writable": bool(allowed),
        })
    return controls
