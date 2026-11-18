"""App-derived hold-cycle payloads and measured Nord response.

Controller/bridge integration tests are added once those layers land.
"""
import unittest
from dataclasses import replace

from oneplus_buds.protocol import Frame
from test_touch import WireTransport, session_for


class CyclePeer(WireTransport):
    def __init__(self, *, ignore=False, ack=0, broken_readback=False):
        super().__init__(ignore=ignore, ack=ack)
        self.broken_readback = broken_readback

    def request(self, command, payload, response, **kwargs):
        if command == 0x0404:
            self.requests.append((command, payload, response))
            if not self.ignore:
                self.cycle_mask = payload[2]
            if self.ack is None:
                raise TimeoutError("ACK missing")
            return Frame(0x8404, 1, bytes((self.ack,)))
        if command == 0x010C and self.broken_readback and any(
                command == 0x0404 for command, _, _ in self.requests):
            raise TimeoutError("cycle readback lost")
        return super().request(command, payload, response, **kwargs)


class HoldCycleTests(unittest.TestCase):
    def test_measured_action_two_response_is_a_shared_cycle(self):
        from oneplus_buds.touch import parse_hold_cycle
        self.assertEqual(parse_hold_cycle(Frame(0x810C, 1, b"\x00\x02\x01\x06")), 6)

    def test_current_anc_and_malformed_replies_are_rejected(self):
        from oneplus_buds.touch import parse_hold_cycle
        for payload in (b"", b"\x00\x02\x01", b"\x01\x02\x01\x06",
                        b"\x00\x01\x01\x06", b"\x00\x02\x03\x06",
                        b"\x00\x02\x01\x86", b"\x00\x02\x01\x06\x00"):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_hold_cycle(Frame(0x810C, 1, payload))
        with self.assertRaises(ValueError):
            parse_hold_cycle(Frame(0x8404, 1, b"\x00\x02\x01\x06"))

    def test_all_four_app_valid_combinations_have_exact_wire_payloads(self):
        for modes, payload in (
            (("anc", "off"), b"\x02\x01\x03"),
            (("off", "transparency"), b"\x02\x01\x05"),
            (("anc", "transparency"), b"\x02\x01\x06"),
            (("anc", "off", "transparency"), b"\x02\x01\x07"),
        ):
            with self.subTest(modes=modes):
                peer = CyclePeer()
                status, mask = session_for(peer).set_hold_cycle(modes)
                self.assertEqual(status, 0)
                self.assertEqual(mask, payload[-1])
                self.assertEqual(peer.requests, [(0x010C, b"\x02\x01", 0x810C),
                    (0x0404, payload, 0x8404), (0x010C, b"\x02\x01", 0x810C)])

    def test_minimum_two_unique_known_modes_and_permission_required(self):
        for modes in ((), ("anc",), ("anc", "anc"), ("off", "future"), ("off", 2)):
            peer = CyclePeer()
            with self.subTest(modes=modes), self.assertRaises(ValueError):
                session_for(peer).set_hold_cycle(modes)
            self.assertEqual(peer.requests, [])
        # A verified profile without hold-cycle support data cannot write.
        peer = CyclePeer()
        with self.assertRaises(ValueError):
            session_for(peer, "062014").set_hold_cycle(("anc", "off"))
        # A community profile without the hold_cycle permission cannot write.
        session = session_for(peer)
        session.profile = replace(session.profile,
                                  community_write_permissions=frozenset({"anc"}))
        with self.assertRaises(ValueError):
            session.set_hold_cycle(("anc", "off"))
        self.assertEqual(peer.requests, [])

    def test_authentication_required_before_write(self):
        peer = CyclePeer()
        session = session_for(peer)
        session._authenticated = False
        with self.assertRaisesRegex(RuntimeError, "authentication"):
            session.set_hold_cycle(("anc", "off"))
        self.assertEqual(peer.requests, [])


if __name__ == "__main__":
    unittest.main()
