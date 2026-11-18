"""Search tone confirmation, expiry and device-owned recovery."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from oneplus_buds.bridge import BudsFrontendBridge, serialize_snapshot
from oneplus_buds.controller import BudsController
from oneplus_buds.models import EventBatch
from oneplus_buds.profiles import PROFILES
from oneplus_buds.protocol import Frame
from oneplus_buds.session import OpoSession
from test_controller import STATUS, FakeSession

NORD = replace(STATUS, product_id="064414", model="OnePlus Nord Buds 3 Pro")


class FindTransport:
    def __init__(self, reply):
        self.reply = reply
        self.requests = []

    def request(self, command, payload, response_command, **kwargs):
        self.requests.append((command, payload, response_command))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


class FindSessionTests(unittest.TestCase):
    def session(self, reply):
        transport = FindTransport(reply)
        session = OpoSession(NORD.device, PROFILES["064414"], transport=transport)
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


class FindingSession(FakeSession):
    def __init__(self, replies=()):
        super().__init__()
        self.replies = list(replies)
        self.find_calls = []

    def find_earbuds(self, ringing):
        self.find_calls.append(ringing)
        reply = self.replies.pop(0) if self.replies else (0, True)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def feature_switches(self, ids):
        return {}

    def bass_engine_status(self):
        return -10, 10, 0


class FindingBackend:
    def __init__(self, sessions):
        self.sessions = list(sessions)
        self.current = NORD

    def start_session(self, address=None):
        session = self.sessions.pop(0)
        return session, self.current, EventBatch((), 0)


class FindControllerTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        clock = patch("oneplus_buds.controller.monotonic", side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)

    def controller(self, *sessions):
        backend = FindingBackend(sessions)
        controller = BudsController(backend)
        controller.start()
        self.addCleanup(controller.shutdown)
        return controller, backend

    def test_confirmed_start_and_stop_publish_shared_state(self):
        controller, _ = self.controller(FindingSession())
        events = []
        bridge = BudsFrontendBridge(events.append, controller=controller)
        start = bridge.execute("find_earbuds", {"ringing": True})
        self.assertTrue(start["result"].get("acknowledged"))
        self.assertEqual(events[-1]["snapshot"].get("find_state"), "ringing")
        stop = bridge.execute("find_earbuds", {"ringing": False})
        self.assertTrue(stop["result"].get("acknowledged"))
        self.assertEqual(events[-1]["snapshot"].get("find_state"), "stopped")

    def test_start_timeout_keeps_stop_option_and_manual_stop_confirms(self):
        controller, _ = self.controller(FindingSession([(None, True), (0, True)]))
        result = controller.find_earbuds(True)
        self.assertFalse(result.get("acknowledged", True))
        self.assertEqual(serialize_snapshot(controller.snapshot()).get("find_state"), "unknown")
        self.assertEqual(controller.find_earbuds(False).get("state"), "stopped")

    def test_rejected_start_remains_stopped_and_does_not_arm_expiry(self):
        session = FindingSession([(14, True)])
        controller, _ = self.controller(session)
        self.assertEqual(controller.find_earbuds(True).get("state"), "stopped")
        self.now = 60
        controller.poll(0)
        self.assertEqual(session.find_calls, [True])

    def test_rejected_stop_never_claims_silence(self):
        controller, _ = self.controller(FindingSession([(0, True), (14, True)]))
        controller.find_earbuds(True)
        result = controller.find_earbuds(False)
        self.assertFalse(result.get("acknowledged", True))
        self.assertEqual(result.get("state"), "unknown")

    def test_confirmed_and_uncertain_starts_expire_once_at_fifty_seconds(self):
        for start_reply in ((0, True), (None, True)):
            with self.subTest(start=start_reply):
                self.now = 0
                session = FindingSession([start_reply, (0, True)])
                controller, _ = self.controller(session)
                controller.find_earbuds(True)
                self.now = 49.9
                controller.poll(0)
                self.assertEqual(session.find_calls, [True])
                self.now = 50
                self.assertEqual(serialize_snapshot(controller.poll(0)).get("find_state"), "stopped")
                self.now = 60
                controller.poll(0)
                self.assertEqual(session.find_calls, [True, False])

    def test_failed_expiry_retains_unknown_without_repeating_stop(self):
        session = FindingSession([(0, True), (None, True), (0, True)])
        controller, _ = self.controller(session)
        controller.find_earbuds(True)
        self.now = 50
        self.assertEqual(serialize_snapshot(controller.poll(0)).get("find_state"), "unknown")
        self.now = 60
        controller.poll(0)
        self.assertEqual(session.find_calls, [True, False])
        self.assertEqual(controller.find_earbuds(False).get("state"), "stopped")

    def test_transport_loss_preserves_unknown_for_same_device_without_start_replay(self):
        first = FindingSession([ConnectionError("lost")])
        second = FindingSession()
        controller, _ = self.controller(first, second)
        result = controller.find_earbuds(True)
        self.assertEqual(result.get("state"), "unknown")
        controller.poll(0)
        self.assertEqual(serialize_snapshot(controller.snapshot()).get("find_state"), "unknown")
        self.assertEqual(second.find_calls, [])
        controller.find_earbuds(False)
        self.assertEqual(second.find_calls, [False])

    def test_shutdown_stops_owned_tone_before_closing_session(self):
        session = FindingSession()
        controller, _ = self.controller(session)
        controller.find_earbuds(True)
        controller.shutdown()
        self.assertEqual(session.find_calls, [True, False])
        self.assertEqual(session.exits, 1)

    def test_another_device_does_not_inherit_unknown_search_or_deadline(self):
        first = FindingSession([ConnectionError("lost")])
        second = FindingSession()
        controller, backend = self.controller(first, second)
        controller.find_earbuds(True)
        backend.current = replace(NORD, device=replace(NORD.device, address="11:22:33:44:55:66"))
        controller.poll(0)
        self.now = 60
        snapshot = serialize_snapshot(controller.poll(0))
        self.assertEqual(snapshot.get("find_state"), "stopped")
        self.assertEqual(second.find_calls, [])

    def test_direct_stop_after_loss_cannot_rediscover_another_pair(self):
        first = FindingSession([ConnectionError("lost")])
        second, reconnected = FindingSession(), FindingSession()
        controller, backend = self.controller(first, second, reconnected)
        controller.find_earbuds(True)
        backend.current = replace(NORD, device=replace(NORD.device, address="11:22:33:44:55:66"))
        with self.assertRaises(ValueError):
            controller.find_earbuds(False)
        self.assertEqual(second.find_calls, [])
        backend.current = NORD
        controller.refresh()
        self.assertEqual(serialize_snapshot(controller.snapshot()).get("find_state"), "unknown")

    def test_queued_gui_command_is_bound_to_its_snapshot_device(self):
        first, second = FindingSession(), FindingSession()
        controller, backend = self.controller(first, second)
        device_id = serialize_snapshot(controller.snapshot()).get("find_device_id")
        self.assertIsInstance(device_id, str)
        self.assertNotIn(NORD.device.address, device_id)
        backend.current = replace(NORD, device=replace(NORD.device, address="11:22:33:44:55:66"))
        controller.refresh()
        bridge = BudsFrontendBridge(lambda event: None, controller=controller)
        for ringing in (True, False):
            reply = bridge.execute("find_earbuds", {"ringing":ringing,"device_id":device_id})
            self.assertFalse(reply["ok"])
            self.assertEqual(second.find_calls, [])
        current_id = serialize_snapshot(controller.snapshot()).get("find_device_id")
        self.assertNotEqual(device_id, current_id)
        reply = bridge.execute("find_earbuds", {"ringing":True,"device_id":current_id})
        self.assertTrue(reply["result"]["acknowledged"])
