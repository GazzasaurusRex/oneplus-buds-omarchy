import unittest
from unittest.mock import patch

from oneplus_buds.bluez import Device
from oneplus_buds.profiles import PROFILES
from oneplus_buds.protocol import NOTIFY_STATE, QUERY_BROADCAST_CODES, SUBSCRIBE_BROADCAST, Frame
from oneplus_buds.session import OpoSession


DEVICE = Device(
    address="AA:BB:CC:DD:EE:FF",
    name="OnePlus Buds Pro 2",
    connected=True,
    uuids=("0000079a-d102-11e1-9b23-00025b00a5a5",),
    battery=80,
)


class SessionTests(unittest.TestCase):
    def test_poll_refreshes_case_battery_without_reconnecting(self):
        transport = FakeTransport({0x0106: [Frame(0x8106, 2,
            bytes.fromhex("00 03 01 64 02 64 03 32"))]})
        def no_blocking_query(*args, **kwargs):
            self.fail("background battery reads must not block foreground controls")
        transport.query = no_blocking_query
        with patch("oneplus_buds.session.monotonic", return_value=0):
            session = OpoSession(DEVICE, PROFILES["064414"], transport=transport)
        with session, patch("oneplus_buds.session.monotonic", return_value=11):
            batch = session.poll(0)
            self.assertEqual([event.data["case"]["percentage"]
                for event in batch.events if event.kind == "battery"], [50])
            session.poll(0)
        self.assertEqual(transport.queries, [(0x0106, b"")])

    def test_session_subscribes_and_redacts_notification_payloads(self):
        peer_payload = b"\x06private peer device name and address"
        transport = FakeTransport(
            {
                QUERY_BROADCAST_CODES: [Frame(0x8200, 1, b"\x00\x02\x04\x06")],
                SUBSCRIBE_BROADCAST: [Frame(NOTIFY_STATE, 0xFF, peer_payload)],
            }
        )
        with patch("oneplus_buds.session.RfcommTransport", return_value=transport):
            with OpoSession(DEVICE, PROFILES["062014"]) as session:
                batch = session.authenticate_and_subscribe()
                self.assertEqual(session.advertised_event_codes, (4, 6))
        self.assertEqual(batch.events[-1].kind, "notification")
        self.assertEqual(batch.events[-1].data, {"event_code": 6})
        self.assertNotIn("private peer", repr(batch))
        self.assertIn((SUBSCRIBE_BROADCAST, b"\x02\x04\x06"), transport.queries)

    def test_poll_returns_typed_safe_events_and_ignored_count(self):
        transport = FakeTransport({}, received=[
            Frame(0x8106, 1, b"\x01\x64\x02\x63"),
            Frame(0x9999, 2, b"secret"),
        ])
        with patch("oneplus_buds.session.RfcommTransport", return_value=transport):
            with OpoSession(DEVICE, PROFILES["062014"]) as session:
                batch = session.poll()
        self.assertEqual(batch.events[0].kind, "battery")
        self.assertEqual(batch.events[0].data["left"]["percentage"], 100)
        self.assertEqual(batch.ignored_frames, 1)
        self.assertNotIn("secret", repr(batch))

    def test_selected_mode_push_is_state_but_active_intensity_stays_diagnostic(self):
        session = OpoSession(DEVICE, PROFILES["064414"])
        batch = session._redact([
            Frame(NOTIFY_STATE, 0xFF, b"\x03\x01\x01\x80"),
            Frame(NOTIFY_STATE, 0xFF, b"\x03\x04\x01\x10"),
        ])
        self.assertEqual([event.kind for event in batch.events], ["anc", "notification"])
        self.assertEqual(batch.events[0].data, {"mode": "on", "level": "auto"})
        self.assertEqual(batch.events[1].data, {"event_code": 3})
        unknown = session._redact([Frame(NOTIFY_STATE, 0xFF, b"\x03\x01\x01\x00\x08")])
        self.assertEqual([event.kind for event in unknown.events], ["notification"])

    def test_selected_mode_pushes_follow_existing_profile_maps(self):
        pro_2 = OpoSession(DEVICE, PROFILES["062014"])
        batch = pro_2._redact([Frame(NOTIFY_STATE, 0xFF, b"\x03\x01\x01\x20")])
        self.assertEqual(batch.events[0].kind, "anc")
        self.assertEqual(batch.events[0].data, {"mode": "on", "level": "medium"})
        buds_4 = OpoSession(DEVICE, PROFILES["065414"])
        batch = buds_4._redact([Frame(NOTIFY_STATE, 0xFF, b"\x03\x01\x01\x00\x08")])
        self.assertEqual(batch.events[0].kind, "anc")
        self.assertEqual(batch.events[0].data, {"mode": "adaptive", "level": None})

    def test_session_must_be_connected(self):
        session = OpoSession(DEVICE, PROFILES["062014"])
        with self.assertRaisesRegex(RuntimeError, "not connected"):
            session.poll()


class FakeTransport:
    def __init__(self, responses, received=None):
        self.responses = responses
        self.received = received or []
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def query(self, command, *args, **_kwargs):
        payload = args[0] if args else b""
        self.queries.append((command, payload))
        return self.responses.get(command, [])

    def exchange_raw(self, *_args, **_kwargs):
        return []

    def send_query(self, command):
        self.queries.append((command, b""))
        self.received.extend(self.responses.get(command, []))
        return 1

    def receive(self, _wait):
        return self.received


if __name__ == "__main__":
    unittest.main()
