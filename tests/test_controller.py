import unittest

from oneplus_buds.bluez import Device
from oneplus_buds.controller import BudsController
from oneplus_buds.models import ControlResult, EventBatch, SafeEvent, StatusResult


DEVICE = Device(
    address="AA:BB:CC:DD:EE:FF",
    name="OnePlus Buds Pro 2",
    connected=True,
    uuids=("0000079a-d102-11e1-9b23-00025b00a5a5",),
    battery=80,
)
STATUS = StatusResult(
    device=DEVICE,
    product_id="062014",
    model="OnePlus Buds Pro 2",
    remote_version=(),
    firmware_version="196.196.101",
    battery={"left": {"percentage": 80, "charging": False}},
    anc="off",
    anc_level=None,
)


class ControllerTests(unittest.TestCase):
    def test_start_poll_updates_cache_and_shutdown_closes(self):
        session = FakeSession(
            initial=EventBatch((SafeEvent("notification", {"event_code": 2}),), 3),
            polls=[EventBatch((SafeEvent("anc", {"mode": "on", "level": "smart"}),), 0)],
        )
        controller = BudsController(FakeBackend([session]))
        started = controller.start()
        self.assertTrue(started.session_connected)
        self.assertEqual(started.notification_event_codes, (2,))
        self.assertEqual(started.ignored_frames, 3)
        updated = controller.poll()
        self.assertEqual((updated.status.anc, updated.status.anc_level), ("on", "smart"))
        stopped = controller.shutdown()
        self.assertFalse(stopped.session_connected)
        self.assertEqual(session.exits, 1)

    def test_verified_write_temporarily_releases_session(self):
        first = FakeSession()
        second = FakeSession()
        backend = FakeBackend([first, second])
        controller = BudsController(backend, reuse_session=False)
        controller.start()
        result = controller.set_anc("transparency")
        snapshot = controller.snapshot()
        self.assertTrue(result.verified)
        self.assertEqual(snapshot.status.anc, "transparency")
        self.assertTrue(snapshot.session_connected)
        self.assertEqual(first.exits, 1)
        self.assertEqual(second.enters, 1)
        controller.shutdown()

    def test_poll_reconnects_once_after_transport_error(self):
        failed = FakeSession(polls=[OSError(5, "disconnected")])
        replacement = FakeSession(
            initial=EventBatch((SafeEvent("notification", {"event_code": 4}),), 0)
        )
        controller = BudsController(FakeBackend([failed, replacement]))
        controller.start()
        snapshot = controller.poll()
        self.assertEqual(snapshot.reconnect_count, 1)
        self.assertEqual(snapshot.notification_event_codes, (4,))
        self.assertTrue(snapshot.session_connected)
        self.assertEqual(failed.exits, 1)
        controller.shutdown()

    def test_poll_requires_started_controller(self):
        with self.assertRaisesRegex(RuntimeError, "not running"):
            BudsController(FakeBackend([])).poll()


class FakeBackend:
    def __init__(self, sessions):
        self.sessions = list(sessions)

    def start_session(self, address=None):
        status = self.status(address)
        session = self.open_session(status.device.address, status=status)
        session.__enter__()
        try:
            batch = session.authenticate_and_subscribe()
        except BaseException:
            session.__exit__(None, None, None)
            raise
        return session, status, batch

    def status(self, _address=None):
        return STATUS

    def open_session(self, _address=None, *, status=None):
        self.asserted_status = status
        return self.sessions.pop(0)

    def set_anc(self, mode, _address=None):
        return ControlResult(
            name=DEVICE.name,
            product_id="062014",
            anc=mode,
            anc_level=None,
            set_status=0,
            verified=True,
        )


class FakeSession:
    def __init__(self, initial=None, polls=None):
        self.initial = initial or EventBatch((), 0)
        self.polls = list(polls or [])
        self.advertised_event_codes = (1, 2)
        self.enters = 0
        self.exits = 0

    def __enter__(self):
        self.enters += 1
        return self

    def __exit__(self, *_args):
        self.exits += 1

    def authenticate_and_subscribe(self):
        return self.initial

    def poll(self, _wait):
        item = self.polls.pop(0) if self.polls else EventBatch((), 0)
        if isinstance(item, Exception):
            raise item
        return item


if __name__ == "__main__":
    unittest.main()
