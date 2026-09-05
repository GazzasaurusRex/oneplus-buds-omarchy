import unittest

from oneplus_buds.profiles import PROFILES
from oneplus_buds.protocol import HELLO, REGISTER, STATUS_QUERY_PAYLOAD, Frame, FrameStream, VersionRecord, decode_frame, encode_frame, format_firmware_version, parse_anc, parse_anc_state, parse_battery, parse_broadcast_codes, parse_feature_switches, parse_product_id, parse_remote_version, parse_set_anc_status


class ProtocolTests(unittest.TestCase):
    def test_frame_round_trip(self):
        encoded = encode_frame(0x010C, 0x42, b"\x01\x01")
        self.assertEqual(encoded.hex(), "aa0900000c014202000101")
        self.assertEqual(decode_frame(encoded), Frame(0x010C, 0x42, b"\x01\x01"))

    def test_stream_handles_fragmented_and_concatenated_frames(self):
        first = encode_frame(0x8103, 1, b"\x00\x14\x0c\x06")
        second = encode_frame(0x8106, 2, b"\x01\x64\x02\xe3")
        stream = FrameStream()
        self.assertEqual(stream.feed(first[:4]), [])
        self.assertEqual(stream.feed(first[4:] + second), [decode_frame(first), decode_frame(second)])

    def test_parsers(self):
        self.assertEqual(parse_product_id(Frame(0x8103, 1, b"\x00\x14\x0c\x06")), "060C14")
        self.assertEqual(
            parse_battery(Frame(0x8106, 1, b"\x01\x64\x02\xe3\x03\x32")),
            {
                "left": {"percentage": 100, "charging": False},
                "right": {"percentage": 99, "charging": True},
                "case": {"percentage": 50, "charging": False},
            },
        )
        self.assertEqual(parse_anc(Frame(0x810C, 1, b"\x01\x01\x04"), PROFILES["060C14"].anc), "on")

    def test_remote_version_parser(self):
        payload = b"\x00\x03" + b"1,1,11,1,2,541,1,3,541"
        self.assertEqual(
            parse_remote_version(Frame(0x8105, 1, payload)),
            (
                VersionRecord(1, 1, "11"),
                VersionRecord(1, 2, "541"),
                VersionRecord(1, 3, "541"),
            ),
        )
        self.assertIsNone(parse_remote_version(Frame(0x8105, 1, b"\x01\x00")))
        self.assertIsNone(parse_remote_version(Frame(0x8105, 1, b"\x00\x02" + b"1,1,11")))

    def test_firmware_version_uses_kind_two_component_records(self):
        records = (
            VersionRecord(1, 1, "11"),
            VersionRecord(1, 2, "541"),
            VersionRecord(2, 2, "541"),
            VersionRecord(3, 2, "510"),
        )
        self.assertEqual(format_firmware_version(records), "541.541.510")
        self.assertIsNone(format_firmware_version((VersionRecord(1, 2, "541"),)))

    def test_feature_switch_parser(self):
        frame = Frame(0x810D, 0, bytes.fromhex("00 03 04 01 11 00 18 00"))
        self.assertEqual(parse_feature_switches(frame), {0x04: True, 0x11: False, 0x18: False})
        self.assertIsNone(parse_feature_switches(Frame(0x810D, 0, b"\x00\x02\x04\x01")))
        self.assertIsNone(parse_feature_switches(Frame(0x810D, 0, b"\x00\x01\x04\x02")))

    def test_observed_buds_pro_responses(self):
        capability = bytes.fromhex("aa0d0000008101050000bf17682604")
        self.assertEqual(decode_frame(capability).command, 0x8100)
        battery = decode_frame(bytes.fromhex("aa0f00000681030800000302e401e40350"))
        self.assertEqual(
            parse_battery(battery),
            {
                "left": {"percentage": 100, "charging": True},
                "right": {"percentage": 100, "charging": True},
                "case": {"percentage": 80, "charging": False},
            },
        )
        subscribed = bytes.fromhex(
            "aa170000058204100000070100020003000400060008000a00"
            "aa0f00000402010b000203010402040304"
        )
        stream = FrameStream()
        frames = stream.feed(subscribed)
        self.assertEqual([frame.command for frame in frames], [0x8205, 0x0204])

    def test_buds_pro_anc_set_frames(self):
        anc = PROFILES["060C14"].anc
        self.assertEqual(
            encode_frame(0x0404, 0x42, anc.payload_for("on")).hex(),
            "aa0a00000404420300010108",
        )
        self.assertEqual(anc.payload_for("off"), b"\x01\x01\x01")
        self.assertEqual(anc.payload_for("transparency"), b"\x01\x01\x02")
        self.assertEqual(HELLO.hex(), "aa070000000123000012")
        self.assertEqual(REGISTER.hex(), "aa0c0000008541050000b550a069")
        self.assertEqual(parse_broadcast_codes(Frame(0x8200, 1, b"\x00\x03\x01\x02\x03")), b"\x01\x02\x03")
        self.assertEqual(
            encode_frame(0x010D, 0, STATUS_QUERY_PAYLOAD).hex(),
            "aa1300000d01000c000b05040b111318061b1c2728",
        )
        self.assertEqual(parse_set_anc_status(Frame(0x8404, 1, b"\x00")), 0)
        self.assertEqual(parse_set_anc_status(Frame(0x8404, 1, b"\x0e")), 14)
        self.assertIsNone(parse_set_anc_status(Frame(0x810C, 1, b"\x00")))

    def test_buds_pro_anc_bitmap_parser(self):
        anc = PROFILES["060C14"].anc
        for value in (4, 8, 16):
            self.assertEqual(parse_anc(Frame(0x810C, 1, bytes((0, 1, 1, value))), anc), "on")
        self.assertEqual(parse_anc(Frame(0x810C, 1, b"\x00\x01\x01\x02"), anc), "transparency")
        self.assertEqual(parse_anc(Frame(0x810C, 1, b"\x00\x01\x01\x01"), anc), "off")

    def test_buds_pro_2_profile_and_observed_transparency(self):
        profile = PROFILES["062014"]
        anc = profile.anc
        self.assertTrue(profile.verified)
        observed = Frame(0x810C, 0xF0, bytes.fromhex("00 01 01 00 01"))
        self.assertEqual(parse_anc_state(observed, anc).mode, "transparency")
        self.assertEqual(anc.payload_for("off"), bytes.fromhex("01 01 01"))
        self.assertEqual(anc.payload_for("on"), bytes.fromhex("01 01 02"))
        self.assertEqual(anc.payload_for("transparency"), bytes.fromhex("01 01 04"))
        self.assertEqual(anc.payload_for("deep"), bytes.fromhex("01 01 10"))
        self.assertEqual(anc.payload_for("medium"), bytes.fromhex("01 01 20"))
        self.assertEqual(anc.payload_for("light"), bytes.fromhex("01 01 40"))
        self.assertEqual(anc.payload_for("smart"), bytes.fromhex("01 01 80"))
        expected_levels = {4: "deep", 5: "medium", 6: "light", 7: "smart"}
        for index, level in expected_levels.items():
            bitmap = (1 << index).to_bytes(2, "little")
            state = parse_anc_state(Frame(0x810C, 1, b"\x00\x01\x01" + bitmap), anc)
            self.assertEqual((state.mode, state.level), ("on", level))


if __name__ == "__main__":
    unittest.main()
