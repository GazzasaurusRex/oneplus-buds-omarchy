"""Feature writes must be confirmed rather than inferred from missing data.

Controller/bridge integration tests are added once those layers land.
"""
import unittest

from oneplus_buds.profiles import PROFILES
from oneplus_buds.protocol import Frame
from oneplus_buds.session import OpoSession
from test_controller import DEVICE


class FeatureTransport:
    def __init__(self, reply, readback):
        self.reply = reply
        self.readback = readback
        self.requests = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def request(self, command, payload, response_command):
        self.requests.append((command, payload, response_command))
        result = self.reply if command == 0x0403 else self.readback
        if isinstance(result, Exception):
            raise result
        return result


class FeatureSwitchTests(unittest.TestCase):
    def test_wear_switch_both_directions_use_feature_ack_and_fresh_read(self):
        for enabled, payload, read in ((False, b"\x04\x00", b"\x00\x01\x04\x00"),
                                       (True, b"\x04\x01", b"\x00\x01\x04\x01")):
            with self.subTest(enabled=enabled):
                wire = FeatureTransport(Frame(0x8403, 1, b"\x00"), Frame(0x810D, 2, read))
                with OpoSession(DEVICE, PROFILES["064414"], transport=wire) as session:
                    self.assertEqual(session.set_feature_switch(4, enabled), (0, True))
                self.assertEqual(wire.requests, [(0x0403, payload, 0x8403),
                                               (0x010D, b"\x01\x04", 0x810D)])

    def test_rejection_malformed_ack_missing_or_contradictory_readback_never_verify(self):
        for ack, read in ((Frame(0x8403, 1, b"\x0e"), b"\x00\x01\x04\x00"),
                          (Frame(0x8403, 1, b""), b"\x00\x01\x04\x00"),
                          (Frame(0x8404, 1, b"\x00"), b"\x00\x01\x04\x00"),
                          (Frame(0x8403, 1, b"\x00"), b"\x00\x00"),
                          (Frame(0x8403, 1, b"\x00"), b"\x00\x01\x04\x01")):
            with self.subTest(ack=ack, read=read):
                wire = FeatureTransport(ack, Frame(0x810D, 2, read))
                with OpoSession(DEVICE, PROFILES["064414"], transport=wire) as session:
                    self.assertFalse(session.set_feature_switch(4, False)[1])

    def test_community_profile_without_feature_permission_cannot_write(self):
        wire = FeatureTransport(Frame(0x8403, 1, b"\x00"), Frame(0x810D, 2, b"\x00\x01\x04\x00"))
        with OpoSession(DEVICE, PROFILES["065414"], transport=wire) as session:
            with self.assertRaises(ValueError):
                session.set_feature_switch(4, False)
        self.assertEqual(wire.requests, [])

    def test_unlisted_feature_cannot_write_even_with_permission(self):
        wire = FeatureTransport(Frame(0x8403, 1, b"\x00"), Frame(0x810D, 2, b"\x00\x01\x09\x01"))
        with OpoSession(DEVICE, PROFILES["064414"], transport=wire) as session:
            with self.assertRaises(ValueError):
                session.set_feature_switch(0x09, True)  # vocal_enhance not audited writable
        self.assertEqual(wire.requests, [])


if __name__ == "__main__":
    unittest.main()
