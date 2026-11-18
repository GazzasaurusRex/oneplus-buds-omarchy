"""Pin measured gesture bytes and exercise the real session/bridge boundary."""
from dataclasses import replace
import unittest

from oneplus_buds.bluez import Device
from oneplus_buds.bridge import BudsFrontendBridge, serialize_snapshot
from oneplus_buds.controller import BudsController
from oneplus_buds.models import StatusResult
from oneplus_buds.profiles import PROFILES
from oneplus_buds.protocol import Frame


MEASURED = bytes.fromhex(
    "00 0a 02 01 01 00 02 01 02 06 02 01 03 05 02 01 04 08 02 01 06 00 "
    "01 01 01 00 01 01 02 06 01 01 03 05 01 01 04 08 01 01 06 00")
DEVICE = Device(address="AA:BB:CC:DD:EE:FF", name="Test buds", connected=True,
                uuids=(), battery=100)
STATUS = StatusResult(DEVICE, "064414", "OnePlus Nord Buds 3 Pro", (), None,
                      None, "on", "deep")


class WireTransport:
    """In-memory RFCOMM peer; ACK can succeed while the device ignores a write."""
    def __init__(self, ignore=False, payload=MEASURED, ack=0):
        self.payload = payload
        self.ignore = ignore
        self.ack = ack
        self.requests = []
        self.cycle_mask = 6

    def __exit__(self, *args):
        pass

    def request(self, command, payload, response, **kwargs):
        self.requests.append((command, payload, response))
        if command == 0x010C and payload == b"\x02\x01":
            return Frame(0x810C, 1, bytes((0, 2, 1, self.cycle_mask)))
        if command == 0x0108:
            return Frame(0x8108, 1, self.payload)
        if command == 0x0401:
            if not self.ignore:
                body = bytearray(self.payload)
                for offset in range(2, len(body), 4):
                    if body[offset:offset + 3] == payload[1:4]:
                        body[offset + 3] = payload[4]
                self.payload = bytes(body)
            if self.ack is None:
                raise TimeoutError("ACK missing")
            return Frame(0x8401, 2, bytes((self.ack,)))
        raise AssertionError(f"unexpected command {command:x}")


def session_for(transport, product="064414"):
    from oneplus_buds.session import OpoSession
    session = OpoSession(DEVICE, PROFILES[product], transport=transport)
    session._connected = True
    session._authenticated = True
    return session


def controller_for(transport, product="064414"):
    controller = BudsController()
    controller._running = True
    controller._status = replace(STATUS, product_id=product)
    controller._session = session_for(transport, product)
    return controller


class TouchTests(unittest.TestCase):
    def test_measured_table_has_five_bindings_per_side(self):
        from oneplus_buds.touch import parse_touch_bindings
        bindings = parse_touch_bindings(Frame(0x8108, 1, MEASURED))
        self.assertEqual(len(bindings), 10)
        self.assertEqual([(b.device_type, b.button, b.action, b.function)
                          for b in bindings[:5]],
                         [(2, 1, 1, 0), (2, 1, 2, 6), (2, 1, 3, 5),
                          (2, 1, 4, 8), (2, 1, 6, 0)])

    def test_bad_tables_never_become_successful_state(self):
        from oneplus_buds.touch import parse_touch_bindings
        for payload in (b"", b"\x00", b"\x01\x00", MEASURED[:-1],
                        MEASURED + b"\x00", b"\x00\x02" + MEASURED[2:6] * 2,
                        b"\x00\x01\x03\x01\x01\x00"):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_touch_bindings(Frame(0x8108, 1, payload))
        with self.assertRaises(ValueError):
            parse_touch_bindings(Frame(0x8401, 1, MEASURED))

    def test_write_is_one_entry_and_readback_is_fresh(self):
        from oneplus_buds.touch import TouchBinding
        peer = WireTransport()
        session = session_for(peer)
        status, bindings = session.set_touch_binding(TouchBinding(1, 1, 2, 5))
        self.assertEqual(status, 0)
        self.assertEqual(peer.requests, [(0x0108, b"", 0x8108),
            (0x0401, b"\x01\x01\x01\x02\x05", 0x8401),
            (0x0108, b"", 0x8108)])
        self.assertEqual(next(b.function for b in bindings
                              if b.device_type == 1 and b.action == 2), 5)
        self.assertEqual(bindings[1].function, 6)  # right side unchanged

    def test_unsupported_targets_never_write(self):
        from oneplus_buds.touch import TouchBinding
        for product, binding in (
            ("062014", TouchBinding(1, 1, 2, 5)),
            ("064414", TouchBinding(4, 1, 2, 5)),
            ("064414", TouchBinding(1, 6, 2, 5)),
            ("064414", TouchBinding(1, 1, 1, 6)),
            ("064414", TouchBinding(1, 1, 3, 1)),
            ("064414", TouchBinding(1, 1, 4, 8)),
            ("064414", TouchBinding(1, 1, 2, 255)),
        ):
            peer = WireTransport()
            with self.subTest(product=product, binding=binding):
                with self.assertRaises(ValueError):
                    session_for(peer, product).set_touch_binding(binding)
                self.assertFalse(any(c == 0x0401 for c, _, _ in peer.requests))

    def test_missing_binding_cannot_be_created_by_accident(self):
        from oneplus_buds.touch import TouchBinding
        peer = WireTransport(payload=b"\x00\x00")
        with self.assertRaises(ValueError):
            session_for(peer).set_touch_binding(TouchBinding(1, 1, 2, 5))
        self.assertEqual(len(peer.requests), 1)

    def test_ack_alone_does_not_verify_and_actual_state_is_published(self):
        controller = controller_for(WireTransport(ignore=True))
        emitted = []
        bridge = BudsFrontendBridge(emitted.append, controller=controller)
        result = bridge.execute("set_touch_control", {"side": 1, "action": 2, "function": 5})
        self.assertTrue(result["ok"])
        self.assertFalse(result["result"]["verified"])
        bindings = emitted[-1]["snapshot"]["touch_controls"]
        self.assertEqual(next(b["function"] for b in bindings
                              if b["side"] == 1 and b["action"] == 2), 6)

    def test_missing_ack_can_be_verified_but_explicit_rejection_cannot(self):
        for ack, verified in ((None, True), (1, False)):
            with self.subTest(ack=ack):
                controller = controller_for(WireTransport(ack=ack))
                result = controller.set_touch_control(1, 2, 5)
                self.assertEqual(result["verified"], verified)

    def test_bridge_rejects_json_type_errors_and_unknown_fields(self):
        peer = WireTransport()
        bridge = BudsFrontendBridge(lambda _: None, controller=controller_for(peer))
        for params in ({"side": True, "action": 2, "function": 5},
                       {"side": 1, "action": "2", "function": 5},
                       {"side": 1, "action": 2, "function": 1.0},
                       {"side": 1, "action": 2},
                       {"side": 1, "action": 2, "function": 5, "extra": 1}):
            with self.subTest(params=params):
                result = bridge.execute("set_touch_control", params)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["code"], "invalid_parameters")
        self.assertEqual(peer.requests, [])

    def test_choices_match_app_masks_and_unknown_current_function_is_preserved(self):
        controller = controller_for(WireTransport(payload=MEASURED[:-1] + b"\xfe"))
        bridge = BudsFrontendBridge(lambda _: None, controller=controller)
        result = bridge.execute("touch_controls")
        self.assertTrue(result["ok"])
        controls = serialize_snapshot(controller.snapshot())["touch_controls"]
        choices = {c["action"]: [o["value"] for o in c["options"]]
                   for c in controls if c["side"] == 2}
        self.assertEqual(choices, {1: [0, 1], 2: [0, 1, 2, 3, 5, 6, 17],
                                  3: [0, 2, 3, 5, 6, 17], 4: [], 6: [0, 11, 12]})
        self.assertIn("254", controls[-1]["function_label"])

    def test_unauthenticated_session_cannot_write(self):
        from oneplus_buds.touch import TouchBinding
        peer = WireTransport()
        session = session_for(peer)
        session._authenticated = False
        with self.assertRaisesRegex(RuntimeError, "authentication"):
            session.set_touch_binding(TouchBinding(1, 1, 2, 5))
        self.assertEqual(peer.requests, [])

    def test_closing_session_clears_cached_controls(self):
        controller = controller_for(WireTransport())
        controller.touch_controls()
        controller._session = None
        controller._close_session()
        self.assertEqual(serialize_snapshot(controller.snapshot())["touch_controls"], [])

    def test_uncertain_write_invalidates_controls_and_emits_unavailable_snapshot(self):
        class LostReadback(WireTransport):
            def request(self, command, payload, response, **kwargs):
                if command == 0x0108 and any(c == 0x0401 for c, _, _ in self.requests):
                    raise TimeoutError("readback lost")
                return super().request(command, payload, response, **kwargs)

        peer = LostReadback()
        controller = controller_for(peer)
        controller.touch_controls()
        emitted = []
        bridge = BudsFrontendBridge(emitted.append, controller=controller)
        result = bridge.execute("set_touch_control", {"side": 1, "action": 2, "function": 5})
        self.assertFalse(result["ok"])
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0]["snapshot"]["touch_controls"], [])
        self.assertFalse(emitted[0]["snapshot"]["session_connected"])
        self.assertEqual(sum(c == 0x0401 for c, _, _ in peer.requests), 1)

    def test_failed_refresh_invalidates_the_previously_loaded_table(self):
        peer = WireTransport()
        controller = controller_for(peer)
        controller.touch_controls()
        peer.payload = b"\x01\x00"
        emitted = []
        bridge = BudsFrontendBridge(emitted.append, controller=controller)
        result = bridge.execute("touch_controls")
        self.assertFalse(result["ok"])
        self.assertEqual(emitted[-1]["snapshot"]["touch_controls"], [])

    def test_malformed_ack_invalidates_state_without_retrying_the_write(self):
        class MalformedAck(WireTransport):
            def request(self, command, payload, response, **kwargs):
                frame = super().request(command, payload, response, **kwargs)
                return replace(frame, payload=b"") if command == 0x0401 else frame

        peer = MalformedAck()
        controller = controller_for(peer)
        controller.touch_controls()
        emitted = []
        result = BudsFrontendBridge(emitted.append, controller=controller).execute(
            "set_touch_control", {"side": 1, "action": 2, "function": 5})
        self.assertFalse(result["ok"])
        self.assertIn("acknowledgement", result["error"]["message"])
        self.assertEqual(emitted[-1]["snapshot"]["touch_controls"], [])
        self.assertEqual(sum(c == 0x0401 for c, _, _ in peer.requests), 1)


if __name__ == "__main__":
    unittest.main()
