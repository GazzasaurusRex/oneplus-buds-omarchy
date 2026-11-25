from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


CompatibilityState = Literal["verified", "community_tested", "experimental"]
WriteOperation = Literal["anc", "eq_preset", "custom_eq", "touch", "hold_cycle",
                         "feature_switch", "bass_level", "find"]

# Parent noise-control modes. Every other writable mode is an ANC strength and
# is verified as main mode "on" plus that level.
MAIN_ANC_MODES = ("off", "transparency", "on", "adaptive")


@dataclass(frozen=True)
class AncProfile:
    write_indices: dict[str, int]
    read_modes: dict[int, str]
    read_levels: dict[int, str]
    sequences: dict[str, int]
    # Optional display labels per internal level key. The phone app names the
    # intensities differently per model (Low/Moderate/High/Auto on the Nord
    # Buds 3 Pro), so the labels belong to the device profile.
    level_labels: dict[str, str] = field(default_factory=dict)
    write_targets: dict[str, tuple[str, str | None]] = field(default_factory=dict)

    def expected_state(self, mode: str) -> tuple[str, str | None]:
        if mode in self.write_targets:
            return self.write_targets[mode]
        return (mode, None) if mode in MAIN_ANC_MODES else ("on", mode)

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
class EqPresetProfile:
    eq_id: int
    key: str
    name: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class EqCreateLayout:
    slot_id: int
    frequencies_hz: tuple[int, ...]
    min_gain_db: int
    max_gain_db: int


@dataclass(frozen=True)
class EqProfile:
    presets: tuple[EqPresetProfile, ...]
    supports_custom: bool
    write_verified: bool
    custom_write_verified: bool
    # Creating/renaming/deleting custom entries needs its own hardware evidence;
    # updating a curve does not imply management rights (Nord-only so far).
    custom_manage_verified: bool = False
    # Custom profiles live in their own id range above the factory presets.
    custom_base: int | None = None
    custom_max: int | None = None
    # Some devices ignore the plain preset command for custom entries and
    # select them only by writing the unchanged curve back (Nord Buds 3 Pro).
    custom_select_via_write: bool = False
    writable_preset_ids: tuple[int, ...] | None = None
    writable_custom_ids: tuple[int, ...] | None = None
    managed_custom_ids: tuple[int, ...] | None = None
    empty_create_layout: EqCreateLayout | None = None
    # These models need an existing curve as a creation template.
    custom_keep_last: bool = False

    def preset_for(self, value: str) -> EqPresetProfile | None:
        normalized = value.strip().lower()
        return next((preset for preset in self.presets
                     if normalized in (preset.key, str(preset.eq_id), *preset.aliases)), None)


PRO_EQ_PRESETS = (
    EqPresetProfile(0, "balanced", "Balanced"),
    EqPresetProfile(1, "deep-sea-bass", "Deep Sea Bass"),
    EqPresetProfile(2, "pure-vocals", "Pure Vocals"),
    EqPresetProfile(3, "bright-and-crisp", "Bright & Crisp"),
)

PRO_2_EQ_PRESETS = (
    EqPresetProfile(0, "balanced", "Balanced"),
    EqPresetProfile(1, "bass", "Bass", ("deep-sea-bass",)),
    EqPresetProfile(2, "serenade", "Serenade", ("pure-vocals",)),
    EqPresetProfile(3, "bold", "Bold", ("bright-and-crisp",)),
    EqPresetProfile(7, "hans-zimmer-soundscape-tuning", "Hans Zimmer Soundscape Tuning"),
)

# Buds 4 swaps the Pro 2 IDs for Bass and Serenade.
BUDS_4_EQ_PRESETS = (
    EqPresetProfile(0, "balanced", "Balanced"),
    EqPresetProfile(1, "serenade", "Serenade", ("pure-vocals",)),
    EqPresetProfile(2, "bass", "Bass", ("deep-sea-bass",)),
)

# The Nord Buds 3 Pro answers the native EQ selection with factory IDs. The
# phone app exposes exactly three of them; the owner confirmed the mapping by
# changing every preset in the app and reading the device back:
#   id 3 = Balanced (Default), id 4 = Serenade, id 5 = Bass
# The device accepts the other factory IDs as well, but the app does not offer
# them. Its catalogue query returns no entries, so this profile is preset-only.
NORD_BUDS_3_PRO_EQ_PRESETS = (
    EqPresetProfile(3, "balanced", "Balanced (Default)", ("ausgewogen",)),
    EqPresetProfile(4, "serenade", "Serenade", ("serenad",)),
    EqPresetProfile(5, "bass", "Bass", ("bass-boost",)),
)


@dataclass(frozen=True)
class DeviceProfile:
    product_id: str
    name: str
    service_uuid: str
    anc: AncProfile
    eq: EqProfile | None
    capabilities: frozenset[str]
    compatibility: CompatibilityState
    # Feature IDs whose shared names are not confirmed on this model stay unnamed.
    unconfirmed_feature_switches: frozenset[int] = frozenset()
    # Community-tested profiles are read-only by default. Each listed operation
    # must have separate hardware evidence; one permission never enables another.
    community_write_permissions: frozenset[WriteOperation] = frozenset()
    # Feature switches that may be written; an unlisted switch stays read-only.
    writable_features: frozenset[str] = frozenset()
    # Wire action -> allowed function IDs. Empty means no touch writes.
    touch_functions: dict[int, tuple[int, ...]] = field(default_factory=dict)
    hold_cycle_supported: bool = False
    # None preserves generic discovery for unaudited models. An audited map
    # lists only audited model switches and their app labels.
    feature_labels: dict[str, str] | None = None
    # Remember the last usable case level and poll it in the background. Only
    # the Nord has this evidence; other case-capable models show live values.
    case_battery_cached: bool = False
    anc_write_verified: bool = False

    @property
    def verified(self) -> bool:
        """Maintainer hardware verification, distinct from community evidence."""
        return self.compatibility == "verified"

    def can_write(self, operation: WriteOperation) -> bool:
        """Authorize a specific write class without broadening compatibility."""
        if self.compatibility == "experimental" and operation == "feature_switch":
            return bool(self.writable_features)
        if self.compatibility == "experimental" and self.eq is not None:
            if operation == "eq_preset":
                return self.eq.write_verified and bool(self.eq.writable_preset_ids)
            if operation == "custom_eq":
                return self.eq.custom_write_verified and bool(self.eq.writable_custom_ids)
        return self.verified or (operation == "anc" and self.anc_write_verified) or (
            self.compatibility == "community_tested"
            and operation in self.community_write_permissions
        )


PROFILES = {
    "067814": DeviceProfile(
        product_id="067814",
        name="OnePlus Buds Pro 4",
        service_uuid="0000079a-d102-11e1-9b23-00025b00a5a5",
        anc=AncProfile(
            write_indices={"off": 0, "transparency": 2, "adaptive": 13,
                           "adaptive-less-noise": 12, "adaptive-more-noise": 14,
                           "deep": 4, "medium": 5, "light": 6, "auto": 7},
            read_modes={3: "off", 8: "transparency", 12: "adaptive",
                        13: "adaptive", 14: "adaptive"},
            read_levels={4: "deep", 5: "medium", 6: "light", 7: "auto",
                         12: "adaptive-less-noise", 13: "adaptive", 14: "adaptive-more-noise"},
            sequences={},
            level_labels={"adaptive": "Standard", "adaptive-less-noise": "Less noise",
                          "adaptive-more-noise": "More noise", "deep": "High",
                          "medium": "Moderate", "light": "Low", "auto": "Auto"},
            write_targets={mode: ("adaptive", mode) for mode in
                           ("adaptive", "adaptive-less-noise", "adaptive-more-noise")},
        ),
        eq=EqProfile(
            (
                EqPresetProfile(0, "balanced", "Balanced"),
                EqPresetProfile(1, "bold", "Bold"),
                EqPresetProfile(2, "serenade", "Serenade"),
                EqPresetProfile(3, "bass", "Bass"),
                EqPresetProfile(7, "dynaudio-featured", "Dynaudio Featured"),
            ),
            supports_custom=True, write_verified=True, custom_write_verified=True,
            custom_select_via_write=True, writable_preset_ids=(0, 1, 2, 3, 7),
            writable_custom_ids=(4,), custom_manage_verified=True,
            custom_base=4, custom_max=2, managed_custom_ids=(5,),
            empty_create_layout=EqCreateLayout(
                4, (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000), -6, 6,
            ),
        ),
        capabilities=frozenset({"battery", "case_battery", "firmware", "anc", "eq",
                                "feature_switches"}),
        compatibility="experimental",
        feature_labels={"wear_detection": "In-ear detection"},
        writable_features=frozenset({"wear_detection"}),
        anc_write_verified=True,
    ),
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
        eq=EqProfile(PRO_EQ_PRESETS, supports_custom=False, write_verified=True,
                     custom_write_verified=False),
        capabilities=frozenset(
            {
                "battery",
                "case_battery",
                "firmware",
                "anc",
                "transparency",
                "anc_levels",
                "smart_anc",
                "eq",
            }
        ),
        compatibility="verified",
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
        eq=EqProfile(PRO_2_EQ_PRESETS, supports_custom=True, write_verified=True,
                     custom_write_verified=True),
        capabilities=frozenset(
            {
                "battery",
                "case_battery",
                "firmware",
                "anc",
                "transparency",
                "anc_levels",
                "smart_anc",
                "eq",
                "custom_eq",
            }
        ),
        compatibility="verified",
    ),
    "065414": DeviceProfile(
        product_id="065414",
        name="OnePlus Buds 4",
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
                "adaptive": 11,
            },
            read_modes={3: "off", 8: "transparency", 11: "adaptive"},
            read_levels={4: "deep", 5: "medium", 6: "light", 7: "smart"},
            sequences={"off": 0x40},
        ),
        eq=EqProfile(BUDS_4_EQ_PRESETS, supports_custom=True, write_verified=True,
                     custom_write_verified=True),
        capabilities=frozenset(
            {
                "battery",
                "case_battery",
                "firmware",
                "anc",
                "transparency",
                "anc_levels",
                "smart_anc",
                "adaptive_anc",
                "eq",
                "custom_eq",
            }
        ),
        compatibility="community_tested",
        # HeyMelody showed Hi-Res on while 0x18 read off; 0x0b has no matching toggle.
        unconfirmed_feature_switches=frozenset({0x0B, 0x18}),
        community_write_permissions=frozenset({"anc", "eq_preset", "custom_eq"}),
    ),
    "064414": DeviceProfile(
        product_id="064414",
        name="OnePlus Nord Buds 3 Pro",
        service_uuid="0000079a-d102-11e1-9b23-00025b00a5a5",
        anc=AncProfile(
            write_indices={
                "off": 0,
                "on": 1,
                "transparency": 2,
                "deep": 4,
                "medium": 5,
                "light": 6,
                "auto": 7,
            },
            read_modes={0: "off", 1: "on", 2: "transparency", 3: "off", 8: "transparency"},
            read_levels={4: "deep", 5: "medium", 6: "light", 7: "auto"},
            sequences={"off": 0x40},
            # The English phone app names the four intensities Low, Moderate,
            # High and Auto; the internal keys stay light/medium/deep/auto.
            level_labels={"deep": "High", "medium": "Moderate",
                          "light": "Low", "auto": "Auto"},
        ),
        eq=EqProfile(NORD_BUDS_3_PRO_EQ_PRESETS, supports_custom=True,
                     write_verified=True, custom_write_verified=True,
                     custom_manage_verified=True, custom_base=7, custom_max=3,
                     custom_select_via_write=True, custom_keep_last=True),
        capabilities=frozenset(
            {
                "battery",
                "case_battery",
                "firmware",
                "anc",
                "transparency",
                "anc_levels",
                "eq",
                "custom_eq",
                "bass_engine",
                "feature_switches",
                "find_earbuds",
                "touch_controls",
                "hold_cycle",
            }
        ),
        compatibility="community_tested",
        # The capability audit found no model support for the separate game
        # mode switch 0x06; 0x0b is Golden Sound here, not hearing enhancement.
        unconfirmed_feature_switches=frozenset({0x06, 0x0B}),
        # Owner-verified writable switches; everything else stays read-only.
        writable_features=frozenset({
            "bass_engine", "personal_noise", "wear_detection",
            "click_to_take_photo", "multipoint", "high_quality_audio",
        }),
        # Wireless Earphones 17.6.6 whitelist 064414 plus the owner's audited
        # app labels; generic switch replies do not establish support.
        feature_labels={
            "personal_noise": "Personalised noise cancellation",
            "bass_engine": "BassWave",
            "wear_detection": "Auto play/pause",
            "click_to_take_photo": "Camera control",
            "multipoint": "Dual connection",
            "high_quality_audio": "Hi-Res mode",
        },
        touch_functions={
            1: (0, 1),
            2: (0, 1, 2, 3, 5, 6, 17),
            3: (0, 2, 3, 5, 6, 17),
            6: (0, 11, 12),
        },
        hold_cycle_supported=True,
        case_battery_cached=True,
        # Each operation has separate owner hardware evidence with fresh
        # read-back; one permission never enables another.
        community_write_permissions=frozenset({
            "anc", "eq_preset", "custom_eq", "touch", "hold_cycle",
            "feature_switch", "bass_level", "find",
        }),
    ),
}


def profile_for_product(product_id: str | None) -> DeviceProfile | None:
    return PROFILES.get(product_id or "")


def feature_capabilities(profile: DeviceProfile | None, switches: dict[str, bool]) -> set[str]:
    """Keep raw diagnostic switch replies separate from advertised support."""
    names = set(switches)
    if profile is not None and profile.feature_labels is not None:
        names.intersection_update(profile.feature_labels)
    return names


def compatibility_for_product(product_id: str | None) -> CompatibilityState:
    profile = profile_for_product(product_id)
    return profile.compatibility if profile else "experimental"
