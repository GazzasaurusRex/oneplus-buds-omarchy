"""Search tone acknowledgement parsing at the session boundary.

Controller/bridge integration tests (expiry, recovery, device tokens) are added
once those layers land.
"""
from dataclasses import replace
import unittest

from oneplus_buds.profiles import PROFILES
from oneplus_buds.protocol import Frame
from oneplus_buds.session import OpoSession
from test_controller import STATUS

NORD = replace(STATUS, product_id="064414", model="OnePlus Nord Buds 3 Pro")


class FindTransport:
    def __init__(self, reply):
        self.reply = reply
        self.requests = []

    def request(self, command, payload, response_command):
        self.requests.append((command, payload, response_command))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


class FindSessionTests(unittest.TestCase):
    def session(self, reply, product="064414"):
        transport = FindTransport(reply)
        session = OpoSession(NORD.device, PROFILES[product], transport=transport)
        session._connected = session._authenticated = True
        return session, transport

    def test_start_and_stop_parse_their_own_acknowledgement(self):
        for ringing, payload in ((True, b"\x01"), (False, b"\x00")):
            session, transport = self.session(Frame(0x8400, 1, b"\x00"))
            self.assertEqual(session.find_earbuds(ringing), (0, True))
            self.assertEqual(transport.requests, [(0x0400, payload, 0x8400)])

    def test_rejection_is_preserved_and_missing_or_invalid_ack_is_unknown(self):
        for reply, expected in ((Frame(0x8400, 1, b"\x0e"), 14),
                (Frame(0x8400, 1, b""), None),
                (Frame(0x8400, 1, b"\x00\x01"), 0),
                (Frame(0x8404, 1, b"\x00"), None), (TimeoutError(), None)):
            with self.subTest(reply=reply):
                session, transport = self.session(reply)
                self.assertEqual(session.find_earbuds(True), (expected, True))
                self.assertEqual(len(transport.requests), 1)

    def test_unverified_unsupported_and_unauthenticated_sessions_cannot_ring(self):
        for invalid in ("unverified", "unsupported", "unauthenticated"):
            session, transport = self.session(Frame(0x8400, 1, b"\x00"))
            if invalid == "unverified":
                session.profile = replace(session.profile, compatibility="experimental")
            elif invalid == "unsupported":
                session.profile = replace(session.profile, capabilities=frozenset())
            else:
                session._authenticated = False
            with self.assertRaises((ValueError, RuntimeError)):
                session.find_earbuds(True)
            self.assertEqual(transport.requests, [])

    def test_community_profile_without_find_permission_cannot_ring(self):
        session, transport = self.session(Frame(0x8400, 1, b"\x00"), product="065414")
        with self.assertRaises(ValueError):
            session.find_earbuds(True)
        self.assertEqual(transport.requests, [])


if __name__ == "__main__":
    unittest.main()
