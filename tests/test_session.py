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

    def receive(self, _wait):
        return self.received


if __name__ == "__main__":
    unittest.main()
