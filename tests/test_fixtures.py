import json
import re
import unittest
from pathlib import Path

from oneplus_buds.profiles import PROFILES
from oneplus_buds.protocol import FrameStream, format_firmware_version, parse_anc_state, parse_battery, parse_broadcast_codes, parse_feature_switches, parse_product_id, parse_remote_version


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "opo_sessions.json"


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_text = FIXTURE_PATH.read_text()
        cls.sessions = json.loads(cls.fixture_text)

    def frame(self, model: str, key: str):
        frames = FrameStream().feed(bytes.fromhex(self.sessions[model][key]))
        self.assertEqual(len(frames), 1)
        return frames[0]

    def test_fixture_is_anonymised(self):
        self.assertIsNone(re.search(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", self.fixture_text))

    def test_buds_pro_session(self):
        session = self.sessions["buds_pro"]
        profile = PROFILES[session["product_id"]]
        self.assertEqual(parse_product_id(self.frame("buds_pro", "rx_product")), "060C14")
        records = parse_remote_version(self.frame("buds_pro", "rx_version"))
        self.assertEqual(format_firmware_version(records), "541.541.510")
        self.assertEqual(parse_anc_state(self.frame("buds_pro", "rx_anc_off"), profile.anc).mode, "off")
        self.assertEqual(parse_battery(self.frame("buds_pro", "rx_battery"))["case"]["percentage"], 80)
        self.assertEqual(self.frame("buds_pro", "rx_set_success").payload, b"\x00")

    def test_buds_pro_2_session(self):
        session = self.sessions["buds_pro_2"]
        profile = PROFILES[session["product_id"]]
        self.assertEqual(parse_product_id(self.frame("buds_pro_2", "rx_product")), "062014")
        records = parse_remote_version(self.frame("buds_pro_2", "rx_version"))
        self.assertEqual(format_firmware_version(records), "196.196.101")
        self.assertEqual(
            parse_broadcast_codes(self.frame("buds_pro_2", "rx_notification_capabilities")),
            bytes.fromhex("01 02 03 04 08 0b f1 f2 f3 0a"),
        )
        switches = parse_feature_switches(self.frame("buds_pro_2", "rx_feature_switches"))
        self.assertEqual(switches[0x04], True)
        self.assertEqual(switches[0x11], False)
        state = parse_anc_state(self.frame("buds_pro_2", "rx_anc_transparency"), profile.anc)
        self.assertEqual((state.mode, state.index), ("transparency", 8))

    def test_buds_4_session(self):
        session = self.sessions["buds_4"]
        profile = PROFILES[session["product_id"]]
        self.assertEqual(parse_product_id(self.frame("buds_4", "rx_product")), "065414")
        records = parse_remote_version(self.frame("buds_4", "rx_version"))
        self.assertEqual(format_firmware_version(records), "138.138.105")
        battery = parse_battery(self.frame("buds_4", "rx_battery"))
        self.assertEqual(battery["left"]["percentage"], 100)
        self.assertNotIn("case", battery)
        self.assertEqual(
            parse_broadcast_codes(self.frame("buds_4", "rx_notification_capabilities")),
            bytes.fromhex("01 02 03 04 08 0b f1 f2 f3"),
        )
        switches = parse_feature_switches(self.frame("buds_4", "rx_feature_switches"))
        self.assertEqual(switches[0x04], True)
        self.assertEqual(switches[0x11], True)
        expected = {
            "off": ("off", None, 3),
            "smart": ("on", "smart", 7),
            "transparency": ("transparency", None, 8),
            "adaptive": ("adaptive", None, 11),
        }
        for key, values in expected.items():
            state = parse_anc_state(self.frame("buds_4", f"rx_anc_{key}"), profile.anc)
            self.assertEqual((state.mode, state.level, state.index), values)
        # The Adaptive SET frame was captured from the official app.
        sent = self.frame("buds_4", "tx_set_adaptive")
        self.assertEqual(sent.payload, profile.anc.payload_for("adaptive"))
        self.assertEqual(self.frame("buds_4", "rx_set_success").payload, b"\x00")


if __name__ == "__main__":
    unittest.main()
