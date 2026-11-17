"""Community-tested profile for the OnePlus Nord Buds 3 Pro (product 064414).

The ANC bitmap, the English app labels and the native EQ IDs were measured on
one contributor unit (recorded firmware 155.155.101), not copied from another
model. These tests pin the measured values so a later profile edit cannot
silently change the wire format or broaden the write permissions.
"""
from __future__ import annotations

import unittest

from oneplus_buds.profiles import PROFILES

PRODUCT_ID = "064414"


class NordBuds3ProProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = PROFILES[PRODUCT_ID]

    def test_profile_is_community_tested_with_two_write_classes(self) -> None:
        self.assertEqual(self.profile.product_id, PRODUCT_ID)
        self.assertEqual(self.profile.name, "OnePlus Nord Buds 3 Pro")
        self.assertEqual(self.profile.compatibility, "community_tested")
        self.assertFalse(self.profile.verified)
        self.assertEqual(self.profile.community_write_permissions,
                         frozenset({"anc", "eq_preset"}))
        self.assertTrue(self.profile.can_write("anc"))
        self.assertTrue(self.profile.can_write("eq_preset"))
        self.assertFalse(self.profile.can_write("custom_eq"))
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
            if product_id != PRODUCT_ID:
                self.assertEqual(profile.anc.level_labels, {}, product_id)

    def test_native_eq_exposes_only_the_three_measured_presets(self) -> None:
        eq = self.profile.eq
        self.assertIsNotNone(eq)
        assert eq is not None
        self.assertEqual([preset.eq_id for preset in eq.presets], [3, 4, 5])
        self.assertEqual([preset.name for preset in eq.presets],
                         ["Balanced (Default)", "Serenade", "Bass"])
        self.assertTrue(eq.write_verified)
        self.assertFalse(eq.supports_custom)
        self.assertFalse(eq.custom_write_verified)

    def test_capabilities_stay_within_the_tested_scope(self) -> None:
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
            }),
        )

    def test_unconfirmed_switch_names_stay_unnamed(self) -> None:
        # The capability audit found no model support for the separate game
        # mode switch 0x06, and 0x0b is Golden Sound on this model, not the
        # shared hearing-enhancement name.
        self.assertEqual(self.profile.unconfirmed_feature_switches,
                         frozenset({0x06, 0x0B}))


if __name__ == "__main__":
    unittest.main()
