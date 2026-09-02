import unittest

from oneplus_buds.protocol import ANC_MODES, STATUS_QUERY_PAYLOAD, Frame, FrameStream, decode_frame, encode_frame, parse_anc, parse_battery, parse_broadcast_codes, parse_product_id


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
        self.assertEqual(parse_anc(Frame(0x810C, 1, b"\x01\x01\x04")), "transparency")

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
        self.assertEqual(
            encode_frame(0x0404, 0x42, bytes((1, 1, ANC_MODES["on"]))).hex(),
            "aa0a00000404420300010102",
        )
        self.assertEqual(ANC_MODES, {"off": 1, "on": 2, "transparency": 4})
        self.assertEqual(parse_broadcast_codes(Frame(0x8200, 1, b"\x00\x03\x01\x02\x03")), b"\x01\x02\x03")
        self.assertEqual(
            encode_frame(0x010D, 0, STATUS_QUERY_PAYLOAD).hex(),
            "aa1300000d01000c000b05040b111318061b1c2728",
        )


if __name__ == "__main__":
    unittest.main()
