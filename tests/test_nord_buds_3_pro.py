"""Community-tested profile for the OnePlus Nord Buds 3 Pro (product 064414).

The ANC bitmap, the English app labels and the native EQ IDs were measured on
one contributor unit (recorded firmware 155.155.101), not copied from another
model. These tests pin the measured values so a later profile edit cannot
silently change the wire format or broaden the write permissions.
"""
from __future__ import annotations

import unittest

from oneplus_buds.profiles import PROFILES, feature_capabilities

PRODUCT_ID = "064414"


class NordBuds3ProProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = PROFILES[PRODUCT_ID]

    def test_profile_is_community_tested_with_evidenced_write_classes(self) -> None:
        self.assertEqual(self.profile.product_id, PRODUCT_ID)
        self.assertEqual(self.profile.name, "OnePlus Nord Buds 3 Pro")
        self.assertEqual(self.profile.compatibility, "community_tested")
        self.assertFalse(self.profile.verified)
        self.assertEqual(self.profile.community_write_permissions,
                         frozenset({"anc", "eq_preset", "custom_eq", "touch",
                                    "hold_cycle", "feature_switch", "bass_level", "find"}))
        for operation in ("anc", "eq_preset", "custom_eq", "touch", "hold_cycle",
                          "feature_switch", "bass_level", "find"):
            self.assertTrue(self.profile.can_write(operation), operation)
        self.assertEqual(self.profile.service_uuid,
                         "0000079a-d102-11e1-9b23-00025b00a5a5")

    def test_anc_write_indices_match_the_measured_bitmap(self) -> None:
        self.assertEqual(
            self.profile.anc.write_indices,
            {"off": 0, "on": 1, "transparency": 2, "deep": 4, "medium": 5,
             "light": 6, "auto": 7},
        )
        # The phone app's device table lists Auto at index 7 for this model.
        self.assertEqual(self.profile.anc.payload_for("auto"), b"\x01\x01\x80")

    def test_anc_payload_bytes_match_the_measured_frames(self) -> None:
        expected = {
            "off": b"\x01\x01\x01",
            "on": b"\x01\x01\x02",
            "transparency": b"\x01\x01\x04",
            "deep": b"\x01\x01\x10",
            "medium": b"\x01\x01\x20",
            "light": b"\x01\x01\x40",
        }
        for mode, payload in expected.items():
            self.assertEqual(self.profile.anc.payload_for(mode), payload, mode)

    def test_anc_read_aliases_cover_the_measured_reports(self) -> None:
        self.assertEqual(self.profile.anc.read_modes[0], "off")
        self.assertEqual(self.profile.anc.read_modes[1], "on")
        self.assertEqual(self.profile.anc.read_modes[2], "transparency")
        self.assertEqual(self.profile.anc.read_levels[4], "deep")
        self.assertEqual(self.profile.anc.read_levels[5], "medium")
        self.assertEqual(self.profile.anc.read_levels[6], "light")
        self.assertEqual(self.profile.anc.read_levels[7], "auto")

    def test_level_labels_match_the_english_phone_app(self) -> None:
        # The owner changed every level in the phone app and read the device
        # back; the English resources name them Low, Moderate, High and Auto.
        self.assertEqual(self.profile.anc.level_labels,
                         {"deep": "High", "medium": "Moderate",
                          "light": "Low", "auto": "Auto"})

    def test_other_profiles_keep_empty_level_labels(self) -> None:
        for product_id, profile in PROFILES.items():
            if product_id not in (PRODUCT_ID, "067814"):
                self.assertEqual(profile.anc.level_labels, {}, product_id)

    def test_pro4_adaptive_writes_match_level_specific_readback(self) -> None:
        profile = PROFILES["067814"]
        self.assertTrue(profile.can_write("anc"))
        self.assertFalse(profile.can_write("eq_preset"))
        expected = {"off": "010101", "transparency": "010104", "adaptive-less-noise": "01010010",
                    "adaptive": "01010020", "adaptive-more-noise": "01010040",
                    "deep": "010110"}
        self.assertEqual(set(profile.anc.write_indices), set(expected))
        for mode, payload in expected.items():
            self.assertEqual(profile.anc.payload_for(mode).hex(), payload)
            target = (mode, None) if mode in ("off", "transparency") else ("adaptive", mode)
            if mode == "deep":
                target = ("on", "deep")
            self.assertEqual(profile.anc.expected_state(mode), target)

    def test_native_eq_presets_and_measured_custom_range(self) -> None:
        eq = self.profile.eq
        self.assertIsNotNone(eq)
        assert eq is not None
        self.assertEqual([preset.eq_id for preset in eq.presets], [3, 4, 5])
        self.assertEqual([preset.name for preset in eq.presets],
                         ["Balanced (Default)", "Serenade", "Bass"])
        self.assertTrue(eq.write_verified)
        self.assertTrue(eq.supports_custom)
        self.assertTrue(eq.custom_write_verified)
        self.assertTrue(eq.custom_manage_verified)
        # The device holds exactly three custom slots (7, 8, 9); it refused id 10.
        self.assertEqual((eq.custom_base, eq.custom_max), (7, 3))

    def test_capabilities_cover_the_measured_features(self) -> None:
        self.assertEqual(
            self.profile.capabilities,
            frozenset({
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
            }),
        )

    def test_unconfirmed_switch_names_stay_unnamed(self) -> None:
        # The capability audit found no model support for the separate game
        # mode switch 0x06, and 0x0b is Golden Sound on this model, not the
        # shared hearing-enhancement name.
        self.assertEqual(self.profile.unconfirmed_feature_switches,
                         frozenset({0x06, 0x0B}))

    def test_touch_choices_pin_the_hardware_verified_round_trips(self) -> None:
        self.assertEqual(self.profile.touch_functions, {
            1: (0, 1), 2: (0, 1, 2, 3, 5, 6, 17),
            3: (0, 2, 3, 5, 6, 17), 6: (0, 11, 12),
        })

    def test_writable_features_pin_the_six_audited_switches(self) -> None:
        self.assertEqual(self.profile.writable_features, frozenset({
            "bass_engine", "personal_noise", "wear_detection",
            "click_to_take_photo", "multipoint", "high_quality_audio",
        }))
        self.assertTrue(self.profile.hold_cycle_supported)

    def test_feature_labels_are_the_audited_allowlist(self) -> None:
        self.assertEqual(self.profile.feature_labels, {
            "personal_noise": "Personalised noise cancellation",
            "bass_engine": "BassWave",
            "wear_detection": "Auto play/pause",
            "click_to_take_photo": "Camera control",
            "multipoint": "Dual connection",
            "high_quality_audio": "Hi-Res mode",
        })

    def test_feature_capabilities_filters_to_the_audited_allowlist(self) -> None:
        switches = {"personal_noise": True, "bass_engine": False, "wear_detection": True,
                    "click_to_take_photo": True, "multipoint": False,
                    "high_quality_audio": True, "low_latency": False,
                    "hearing_enhancement": False}
        self.assertEqual(feature_capabilities(self.profile, switches),
                         {"personal_noise", "bass_engine", "wear_detection",
                          "click_to_take_photo", "multipoint", "high_quality_audio"})
        # No allowlist preserves generic discovery for unaudited models.
        self.assertEqual(feature_capabilities(PROFILES["062014"], switches), set(switches))
        self.assertEqual(feature_capabilities(None, switches), set(switches))

    def test_other_profiles_do_not_gain_new_feature_writes(self) -> None:
        buds_4 = PROFILES["065414"]
        for operation in ("touch", "hold_cycle", "feature_switch", "bass_level", "find"):
            self.assertFalse(buds_4.can_write(operation), operation)
        self.assertEqual(buds_4.community_write_permissions,
                         frozenset({"anc", "eq_preset", "custom_eq"}))
        for product_id in ("060C14", "062014", "065414"):
            profile = PROFILES[product_id]
            self.assertEqual(profile.touch_functions, {}, product_id)
            self.assertEqual(profile.writable_features, frozenset(), product_id)
            self.assertFalse(profile.hold_cycle_supported, product_id)
            self.assertIsNone(profile.feature_labels, product_id)
            self.assertFalse(profile.eq.custom_manage_verified, product_id)
            self.assertNotIn("bass_engine", profile.capabilities, product_id)
            self.assertNotIn("find_earbuds", profile.capabilities, product_id)


if __name__ == "__main__":
    unittest.main()
