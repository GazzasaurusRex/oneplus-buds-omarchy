import json
from pathlib import Path
from threading import Event, Thread
import unittest
from unittest.mock import patch

from oneplus_buds.availability import Availability, BlueZAvailability
from oneplus_buds.bluez import DEVICE_INTERFACE
from oneplus_buds.controller import BudsController
from oneplus_buds.protocol import FrameStream, QUERY_PRODUCT_ID, QUERY_BATTERY, QUERY_ANC, QUERY_REMOTE_VERSION
from oneplus_buds.session import OpoSession
from test_controller import DEVICE

FIXTURES = json.loads((Path(__file__).parent / 'fixtures/opo_sessions.json').read_text())


def frame(hex_string):
    return FrameStream().feed(bytes.fromhex(hex_string))[0]


class StartupTransport:
    def __init__(self, fixture):
        self.fixture = fixture
        self.enters = self.exits = 0
        self.queries = []
        self.raw_waits = []
        self.optional = []

    def __enter__(self):
        self.enters += 1
        return self

    def __exit__(self, *_args):
        self.exits += 1

    def query(self, command, *args, **kwargs):
        self.queries.append(command)
        return []

    def exchange_raw(self, packet, wait):
        self.raw_waits.append(wait)
        return []

    def request(self, command, *args, **kwargs):
        self.queries.append(command)
        if command == QUERY_PRODUCT_ID:
            return frame(self.fixture['rx_product'])
        if command == QUERY_BATTERY:
            return frame(FIXTURES['buds_pro']['rx_battery'])
        if command == QUERY_ANC:
            return frame(self.fixture.get('rx_anc_off', self.fixture.get('rx_anc_transparency')))
        raise AssertionError(command)

    def send_query(self, command):
        self.optional.append(command)
        return frame(self.fixture['rx_version']).sequence

    def receive(self, wait):
        return [frame(self.fixture['rx_version'])]


class StartupTests(unittest.TestCase):
    def test_one_socket_fresh_profile_and_deferred_firmware_both_models(self):
        for fixture in FIXTURES['buds_pro'], FIXTURES['buds_pro_2']:
            with self.subTest(product=fixture['product_id']):
                transport = StartupTransport(fixture)
                with patch('oneplus_buds.session.RfcommTransport', return_value=transport) as factory:
                    session, status, initial = OpoSession.bootstrap(DEVICE)
                factory.assert_called_once()
                self.assertEqual(transport.enters, 1)
                self.assertEqual(transport.exits, 0)
                self.assertEqual(status.product_id, fixture['product_id'])
                self.assertEqual(session.profile.product_id, fixture['product_id'])
                self.assertTrue(session._authenticated)
                self.assertEqual(transport.raw_waits, [2.0, 1.5])
                self.assertEqual(transport.queries.count(0x0100), 1)
                self.assertTrue(status.battery)
                self.assertIsNotNone(status.anc)
                self.assertIsNone(status.firmware_version)
                self.assertNotIn(QUERY_REMOTE_VERSION, transport.queries)
                self.assertNotIn(0x0200, transport.queries)
                self.assertEqual(transport.optional, [])
                controller = BudsController()
                controller._status = status
                controller._session = session
                controller._running = True
                snapshot = controller.poll(0)
                self.assertIsNotNone(snapshot.status.firmware_version)
                self.assertIn(0x0200, transport.queries)
                self.assertEqual(transport.optional, [QUERY_REMOTE_VERSION])
                controller.poll(0)
                self.assertEqual(transport.optional, [QUERY_REMOTE_VERSION])
                controller.shutdown()
                self.assertEqual(transport.exits, 1)

    def test_failure_closes_bootstrap_socket(self):
        transport = StartupTransport(FIXTURES['buds_pro'])
        transport.request = lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError('missing'))
        with patch('oneplus_buds.session.RfcommTransport', return_value=transport):
            with self.assertRaises(TimeoutError):
                OpoSession.bootstrap(DEVICE)
        self.assertEqual(transport.exits, 1)


class AvailabilityTests(unittest.TestCase):
    def test_arrival_during_attempt_is_not_lost_and_consumed_once(self):
        availability = Availability()
        before = availability.token()
        availability.notify()
        self.assertFalse(availability.wait(Event(), 30, before))
        cancelled = Event()
        done = Event()
        thread = Thread(target=lambda: (availability.wait(cancelled, 30, availability.token()), done.set()))
        thread.start()
        self.assertFalse(done.wait(0.03))
        cancelled.set()
        self.assertTrue(done.wait(0.3))
        thread.join()

    def test_only_new_compatible_availability_wakes_retry(self):
        watcher = BlueZAvailability()
        props = {'Name': 'OnePlus Buds Pro', 'Connected': False,
                 'UUIDs': ['00001107-d102-11e1-9b23-00025b00a5a5']}
        watcher.added('/a', {DEVICE_INTERFACE: props})
        self.assertEqual(watcher.token(), 0)
        watcher.changed(DEVICE_INTERFACE, {'Connected': True}, [], '/a')
        self.assertEqual(watcher.token(), 1)
        for changes in ({'Connected': True}, {'ServicesResolved': True}, {'RSSI': -10}):
            watcher.changed(DEVICE_INTERFACE, changes, [], '/a')
        self.assertEqual(watcher.token(), 1)
        watcher.changed(DEVICE_INTERFACE, {'Connected': False}, [], '/a')
        watcher.changed(DEVICE_INTERFACE, {'Connected': True}, [], '/a')
        self.assertEqual(watcher.token(), 2)
        watcher.added('/unrelated', {DEVICE_INTERFACE: {'Name': 'Speaker', 'Connected': True}})
        self.assertEqual(watcher.token(), 2)
        watcher.removed('/a', [DEVICE_INTERFACE])
        watcher.added('/a', {DEVICE_INTERFACE: {**props, 'Connected': True}})
        self.assertEqual(watcher.token(), 3)

    def test_late_uuids_can_make_a_connected_device_eligible(self):
        watcher = BlueZAvailability()
        watcher.changed(DEVICE_INTERFACE, {'Name': 'OnePlus Buds Pro', 'Connected': True}, [], '/a')
        self.assertEqual(watcher.token(), 0)
        watcher.changed(DEVICE_INTERFACE, {'UUIDs': list(DEVICE.uuids)}, [], '/a')
        self.assertEqual(watcher.token(), 1)

    def test_alias_is_accepted_when_bluez_name_is_absent(self):
        watcher = BlueZAvailability()
        watcher.added('/a', {DEVICE_INTERFACE: {
            'Alias': 'OnePlus Buds Pro',
            'Connected': True,
            'UUIDs': list(DEVICE.uuids),
        }})
        self.assertEqual(watcher.token(), 1)

    def test_daemon_restart_discards_hint_cache(self):
        watcher = BlueZAvailability()
        watcher._properties['/old'] = {'Connected': True}
        watcher.owner_changed('org.bluez', ':1.1', '')
        self.assertEqual(watcher._properties, {})
        self.assertEqual(watcher.token(), 0)
        watcher.owner_changed('org.bluez', '', ':1.2')
        self.assertEqual(watcher.token(), 1)

    def test_runner_wakes_once_then_keeps_failure_backoff(self):
        from oneplus_buds.service import BudsServiceRunner
        from test_service import FakeController, EMPTY_SNAPSHOT, RecordingEvent
        availability = Availability()
        cancelled = RecordingEvent(cancel_after_waits=1)
        # Avoid a real wait: inspect the exact token delivered by the runner.
        waits = []
        def wait(cancel, delay, token):
            waits.append((delay, token, availability.token()))
            if len(waits) == 1:
                return False
            cancel.wait(0)
            return True
        availability.wait = wait
        def state_changed(state):
            if state.connection == 'disconnected' and state.attempt == 1:
                availability.notify()
        controller = FakeController(starts=[RuntimeError('absent'), RuntimeError('not ready')])
        BudsServiceRunner(controller, availability=availability, on_state=state_changed).run(cancelled)
        self.assertEqual(waits, [(1.0, 0, 1), (2.0, 1, 1)])
