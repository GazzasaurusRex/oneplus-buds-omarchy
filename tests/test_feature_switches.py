"""Feature04 writes must be confirmed rather than inferred from missing data."""
from dataclasses import replace
import unittest

from oneplus_buds.bridge import BudsFrontendBridge
from oneplus_buds.controller import BudsController
from oneplus_buds.models import EventBatch
from oneplus_buds.profiles import PROFILES
from oneplus_buds.protocol import Frame
from oneplus_buds.session import OpoSession
from test_controller import DEVICE, STATUS


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

    def test_frontend_can_set_wear_and_gets_confirmed_snapshot_without_unlocking_unsupported_features(self):
        wire = FeatureTransport(Frame(0x8403, 1, b"\x00"),
                                Frame(0x810D, 2, b"\x00\x01\x04\x00"))
        with OpoSession(DEVICE, PROFILES["064414"], transport=wire) as session:
            class Backend:
                def start_session(self, _address):
                    return session, replace(STATUS, product_id="064414"), EventBatch((), 0)
            controller = BudsController(backend=Backend())
            controller.start()
            emitted = []
            bridge = BudsFrontendBridge(emitted.append, controller=controller)
            reply = bridge.execute("set_feature_switch", {"feature":"wear_detection", "enabled":False})
            self.assertTrue(reply["ok"], reply)
            self.assertTrue(reply["result"]["verified"])
            self.assertFalse(emitted[-1]["snapshot"]["feature_switches"]["wear_detection"])
            self.assertIn("wear_detection", emitted[-1]["snapshot"]["writable_features"])
            blocked = bridge.execute("set_feature_switch", {"feature":"vocal_enhance", "enabled":True})
            self.assertFalse(blocked["ok"])
            self.assertEqual(len(wire.requests), 2)

    def test_three_remaining_controls_write_both_values_and_publish_confirmed_state(self):
        for name, feature in (("click_to_take_photo", 13), ("multipoint", 17),
                              ("high_quality_audio", 24)):
            for enabled in (False, True):
                with self.subTest(name=name, enabled=enabled):
                    wire = FeatureTransport(Frame(0x8403, 1, b"\x00"),
                        Frame(0x810D, 2, bytes((0, 1, feature, int(enabled)))))
                    backend = FeatureBackend([(wire, replace(STATUS, product_id="064414"))])
                    controller = BudsController(backend=backend)
                    controller.start()
                    emitted = []
                    reply = BudsFrontendBridge(emitted.append, controller=controller).execute(
                        "set_feature_switch", {"feature":name, "enabled":enabled})
                    self.assertTrue(reply["ok"], reply)
                    self.assertTrue(reply["result"]["verified"])
                    self.assertEqual(emitted[-1]["snapshot"]["feature_switches"][name], enabled)
                    self.assertIn(name, emitted[-1]["snapshot"]["writable_features"])
                    self.assertEqual(wire.requests, [(0x0403, bytes((feature,int(enabled))), 0x8403),
                                                   (0x010D, bytes((1,feature)), 0x810D)])
                    controller.shutdown()

    def test_link_changing_feature_recovers_same_pair_and_reads_without_replaying_write(self):
        for feature in (17, 24):
            with self.subTest(feature=feature):
                first = FeatureTransport(ConnectionError("link reset"), None)
                second = FeatureTransport(None, Frame(0x810D, 3, bytes((0,1,feature,1))))
                nord = replace(STATUS, product_id="064414")
                backend = FeatureBackend([(first,nord), (second,nord)])
                controller = BudsController(backend=backend)
                controller.start()
                result = controller.set_feature_switch(feature, True)
                self.assertTrue(result["verified"])
                self.assertTrue(controller.snapshot().session_connected)
                self.assertEqual(backend.addresses, [None, DEVICE.address])
                self.assertEqual(first.requests, [(0x0403,bytes((feature,1)),0x8403)])
                self.assertEqual(second.requests, [(0x010D,bytes((1,feature)),0x810D)])
                controller.shutdown()

    def test_failed_recovery_or_changed_identity_cannot_confirm_codec_setting(self):
        nord = replace(STATUS, product_id="064414")
        other_address = replace(nord, device=replace(DEVICE,address="11:22:33:44:55:66"))
        other_product = replace(nord,product_id="062014")
        for recovered in (ConnectionError("not connected yet"), other_address, other_product):
            with self.subTest(recovered=recovered):
                first = FeatureTransport(ConnectionError("link reset"), None)
                second = FeatureTransport(None, Frame(0x810D,3,b"\x00\x01\x18\x01"))
                entry = recovered if isinstance(recovered,Exception) else (second,recovered)
                backend = FeatureBackend([(first,nord),entry])
                controller = BudsController(backend=backend)
                controller.start()
                result = controller.set_feature_switch(24,True)
                self.assertFalse(result["verified"])
                self.assertFalse(controller.snapshot().session_connected)
                self.assertNotIn("high_quality_audio",controller.snapshot().feature_switches)
                self.assertEqual(second.requests, [])
                controller.shutdown()

    def test_rejected_link_changing_write_never_becomes_success_through_recovery(self):
        first = FeatureTransport(Frame(0x8403,1,b"\x01"), ConnectionError("read link reset"))
        second = FeatureTransport(None, Frame(0x810D,3,b"\x00\x01\x18\x01"))
        nord = replace(STATUS, product_id="064414")
        backend = FeatureBackend([(first,nord),(second,nord)])
        controller = BudsController(backend=backend)
        controller.start()
        result = controller.set_feature_switch(24,True)
        self.assertEqual(result["set_status"],1)
        self.assertFalse(result["verified"])
        self.assertEqual(backend.addresses,[None])
        self.assertEqual(first.requests,[(0x0403,b"\x18\x01",0x8403)])
        controller.shutdown()


class FeatureBackend:
    def __init__(self, entries):
        self.entries = list(entries)
        self.addresses = []

    def start_session(self, address):
        self.addresses.append(address)
        entry = self.entries.pop(0)
        if isinstance(entry,Exception):
            raise entry
        wire,status = entry
        session = OpoSession(status.device, PROFILES["064414"], transport=wire)
        session.__enter__()
        return session,status,EventBatch((),0)

