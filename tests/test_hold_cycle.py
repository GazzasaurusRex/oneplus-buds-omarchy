"""App-derived hold-cycle payloads and measured Nord response."""
import unittest
from dataclasses import replace

from oneplus_buds.bridge import BudsFrontendBridge, serialize_snapshot
from oneplus_buds.protocol import Frame
from test_touch import WireTransport, controller_for, session_for


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

    def test_fewer_than_two_reported_modes_fail_closed_before_any_write(self):
        from oneplus_buds.touch import parse_hold_cycle
        for mask in (0, 1, 2, 4):
            with self.subTest(mask=mask):
                with self.assertRaises(ValueError):
                    parse_hold_cycle(Frame(0x810C, 1, bytes((0, 2, 1, mask))))
                peer = CyclePeer()
                peer.cycle_mask = mask
                emitted = []
                bridge = BudsFrontendBridge(emitted.append, controller=controller_for(peer))
                result = bridge.execute("set_hold_cycle", {"modes": ["anc", "off"]})
                self.assertFalse(result["ok"])
                self.assertIsNone(emitted[-1]["snapshot"]["hold_cycle"])
                self.assertFalse(emitted[-1]["snapshot"]["session_connected"])
                self.assertFalse(any(c == 0x0404 for c, _, _ in peer.requests))

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
        peer = CyclePeer()
        with self.assertRaises(ValueError):
            session_for(peer, "062014").set_hold_cycle(("anc", "off"))
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

    def test_snapshot_has_shared_choices_and_readback_after_write(self):
        controller = controller_for(CyclePeer())
        controller.touch_controls()
        cycle = serialize_snapshot(controller.snapshot())["hold_cycle"]
        self.assertEqual(cycle["modes"], ["anc", "transparency"])
        self.assertEqual([x["value"] for x in cycle["options"]], ["anc", "off", "transparency"])
        self.assertEqual(cycle["min_selected"], 2)
        self.assertTrue(cycle["shared"])
        emitted = []
        bridge = BudsFrontendBridge(emitted.append, controller=controller)
        result = bridge.execute("set_hold_cycle", {"modes": ["anc", "off"]})
        self.assertTrue(result["ok"])
        self.assertTrue(result["result"]["verified"])
        self.assertEqual(emitted[-1]["snapshot"]["hold_cycle"]["modes"], ["anc", "off"])

    def test_ignored_write_does_not_pass_verification(self):
        emitted = []
        bridge = BudsFrontendBridge(emitted.append, controller=controller_for(CyclePeer(ignore=True)))
        result = bridge.execute("set_hold_cycle", {"modes": ["anc", "off"]})
        self.assertTrue(result["ok"])
        self.assertFalse(result["result"]["verified"])
        self.assertEqual(emitted[-1]["snapshot"]["hold_cycle"]["modes"], ["anc", "transparency"])

    def test_lost_readback_invalidates_state_and_never_retries(self):
        peer = CyclePeer(broken_readback=True)
        emitted = []
        controller = controller_for(peer)
        controller.touch_controls()
        result = BudsFrontendBridge(emitted.append, controller=controller).execute(
            "set_hold_cycle", {"modes": ["anc", "off"]})
        self.assertFalse(result["ok"])
        self.assertEqual(sum(command == 0x0404 for command, _, _ in peer.requests), 1)
        self.assertIsNone(emitted[-1]["snapshot"]["hold_cycle"])
        self.assertFalse(emitted[-1]["snapshot"]["session_connected"])

    def test_missing_ack_is_verified_only_by_fresh_read_explicit_rejection_fails(self):
        for ack, expected in ((None, True), (1, False)):
            with self.subTest(ack=ack):
                controller = controller_for(CyclePeer(ack=ack))
                result = controller.set_hold_cycle(("anc", "off"))
                self.assertEqual(result["verified"], expected)

    def test_malformed_ack_clears_cycle_without_retrying_write(self):
        class MalformedAck(CyclePeer):
            def request(self, command, payload, response, **kwargs):
                frame = super().request(command, payload, response, **kwargs)
                return replace(frame, payload=b"\x00\x00") if command == 0x0404 else frame

        peer = MalformedAck()
        controller = controller_for(peer)
        controller.touch_controls()
        emitted = []
        result = BudsFrontendBridge(emitted.append, controller=controller).execute(
            "set_hold_cycle", {"modes": ["anc", "off"]})
        self.assertFalse(result["ok"])
        self.assertIsNone(emitted[-1]["snapshot"]["hold_cycle"])
        self.assertEqual(sum(c == 0x0404 for c, _, _ in peer.requests), 1)

    def test_bridge_rejects_bad_types_and_fields_before_any_request(self):
        peer = CyclePeer()
        bridge = BudsFrontendBridge(lambda _: None, controller=controller_for(peer))
        for params in ({}, {"modes": "anc,off"}, {"modes": ["anc", True]},
                       {"modes": ["anc", "off"], "side": 1}):
            with self.subTest(params=params):
                result = bridge.execute("set_hold_cycle", params)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["code"], "invalid_parameters")
        self.assertEqual(peer.requests, [])


if __name__ == "__main__":
    unittest.main()
