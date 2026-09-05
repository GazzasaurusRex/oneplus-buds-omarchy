from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AncProfile:
    write_indices: dict[str, int]
    read_modes: dict[int, str]
    read_levels: dict[int, str]
    sequences: dict[str, int]

    def payload_for(self, mode: str) -> bytes:
        try:
            index = self.write_indices[mode]
        except KeyError as error:
            raise ValueError(f"ANC mode {mode!r} is not supported by this device profile") from error
        bitmap = 1 << index
        width = index // 8 + 1
        return b"\x01\x01" + bitmap.to_bytes(width, "little")

    def sequence_for(self, mode: str) -> int:
        return self.sequences.get(mode, 0x42)


@dataclass(frozen=True)
class DeviceProfile:
    product_id: str
    name: str
    service_uuid: str
    anc: AncProfile
    capabilities: frozenset[str]
    verified: bool


PROFILES = {
    "060C14": DeviceProfile(
        product_id="060C14",
        name="OnePlus Buds Pro",
        service_uuid="00001107-d102-11e1-9b23-00025b00a5a5",
        anc=AncProfile(
            write_indices={"off": 0, "transparency": 1, "light": 2, "on": 3, "deep": 3, "smart": 4},
            read_modes={0: "off", 1: "transparency", 2: "on", 3: "on", 4: "on"},
            read_levels={2: "light", 3: "deep", 4: "smart"},
            sequences={"off": 0x40},
        ),
        capabilities=frozenset(
            {
                "battery",
                "case_battery",
                "anc",
                "transparency",
                "anc_levels",
                "smart_anc",
            }
        ),
        verified=True,
    ),
    "062014": DeviceProfile(
        product_id="062014",
        name="OnePlus Buds Pro 2",
        service_uuid="0000079a-d102-11e1-9b23-00025b00a5a5",
        anc=AncProfile(
            write_indices={
                "off": 0,
                "on": 1,
                "transparency": 2,
                "deep": 4,
                "medium": 5,
                "light": 6,
                "smart": 7,
            },
            read_modes={0: "off", 1: "on", 2: "transparency", 3: "off", 8: "transparency"},
            read_levels={4: "deep", 5: "medium", 6: "light", 7: "smart"},
            sequences={"off": 0x40},
        ),
        capabilities=frozenset(
            {
                "battery",
                "case_battery",
                "anc",
                "transparency",
                "anc_levels",
                "smart_anc",
            }
        ),
        verified=True,
    ),
}


def profile_for_product(product_id: str | None) -> DeviceProfile | None:
    return PROFILES.get(product_id or "")
