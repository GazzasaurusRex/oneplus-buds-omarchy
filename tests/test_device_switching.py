"""Exercise physical identity changes through the real runner and UI models."""
import json
import subprocess
import unittest
from dataclasses import replace
from threading import Event

from oneplus_buds.bridge import BudsFrontendBridge, serialize_snapshot
from oneplus_buds.controller import BudsController
from oneplus_buds.models import EventBatch, SafeEvent
from test_controller import STATUS, FakeSession

B = replace(STATUS, device=replace(STATUS.device, address='11:22:33:44:55:66',
            name='OnePlus Buds Pro'), product_id='060C14', model='OnePlus Buds Pro',
            firmware_version='541.541.510', battery={'right': {'percentage': 42}},
            anc='on', anc_level='deep')


class SwitchingBackend:
    def __init__(self, first, second):
        self.current = first
        self.second = second
        self.selected = []
        self.sessions = []

    def status(self, address=None):
        self.selected.append(address)
        if self.current is None:
            raise RuntimeError('no compatible device connected')
        if address is not None and address != self.current.device.address:
            raise RuntimeError(f'selected device {address} unavailable')
        return self.current

    def open_session(self, address=None, *, status=None):
        assert status is self.current
        assert address == status.device.address
        session = FakeSession(initial=EventBatch((
            SafeEvent('feature_switches', {'multipoint': True} if status is self.second
                      else {'low_latency': True}),
            SafeEvent('notification', {'event_code': 4 if status is self.second else 9}),
        ), 1 if status is self.second else 7))
        session.authentications = 0
        authenticate = session.authenticate_and_subscribe
        def auth():
            session.authentications += 1
            return authenticate()
        session.authenticate_and_subscribe = auth
        self.sessions.append(session)
        return session


class SwitchingTests(unittest.TestCase):
    def test_runner_switches_both_directions_and_ui_replaces_state(self):
        for first, second in ((STATUS, B), (B, STATUS)):
            with self.subTest(first=first.model):
                backend = SwitchingBackend(first, second)
                controller = BudsController(backend)
                cancelled = Event()
                events = []
                saw_gap = False
                def emit(event):
                    nonlocal saw_gap
                    events.append(event)
                    if event['type'] != 'snapshot':
                        return
                    snapshot = event['snapshot']
                    status = snapshot['status']
                    if status and status['product_id'] == first.product_id:
                        backend.current = None
                        backend.sessions[0].polls = [ConnectionError('disconnected')]
                    elif status is None and not cancelled.is_set():
                        saw_gap = True
                        self.assertEqual(snapshot['feature_switches'], {})
                        self.assertEqual(snapshot['anc_modes'], [])
                        self.assertEqual(snapshot['notification_event_codes'], [])
                        backend.current = second
                    elif status and status['product_id'] == second.product_id:
                        self.assertTrue(saw_gap)
                        self.assertEqual(controller.address, second.device.address)
                        self.assertEqual(status['battery'], second.battery)
                        self.assertEqual(status['anc'], second.anc)
                        self.assertEqual(status['firmware_version'], second.firmware_version)
                        self.assertEqual(snapshot['feature_switches'], {'multipoint': True})
                        self.assertEqual(snapshot['notification_event_codes'], [4])
                        self.assertEqual(snapshot['ignored_frames'], 1)
                        cancelled.set()
                bridge = BudsFrontendBridge(emit, controller=controller, poll_interval=0)
                bridge.runner.initial_retry_delay = 0.001
                bridge.run(cancelled)
                self.assertEqual(backend.selected, [None, None, None])
                self.assertEqual([s.authentications for s in backend.sessions], [1, 1])
                self.assertEqual([s.exits for s in backend.sessions], [1, 1])
                # Feed real bridge events through the production JS reducer.
                script = """
const m = require('./BridgeModel.js');
let state = m.initialState();
for (const event of JSON.parse(process.argv[1])) {
  state = m.applyMessage(state, event);
  if (state.snapshot && state.snapshot.status &&
      state.snapshot.status.product_id === process.argv[2]) {
    console.log(JSON.stringify(state.snapshot)); break;
  }
}
"""
                result = subprocess.check_output(['node', '-e', script,
                    json.dumps(events), second.product_id], text=True)
                ui = json.loads(result)
                self.assertEqual(ui['status']['model'], second.model)
                self.assertEqual('medium' in ui['anc_modes'], second.product_id == '062014')

    def test_immediate_replacement_and_repeated_empty_retries(self):
        backend = SwitchingBackend(STATUS, B)
        controller = BudsController(backend)
        controller.start()
        backend.current = B
        backend.sessions[0].polls = [ConnectionError('gone')]
        switched = controller.poll()
        self.assertEqual(switched.status, B)
        self.assertEqual(backend.sessions[0].exits, 1)
        self.assertEqual(backend.sessions[1].authentications, 1)
        backend.current = None
        backend.sessions[1].polls = [ConnectionError('gone')]
        with self.assertRaises(RuntimeError):
            controller.poll()
        for _ in range(3):
            with self.assertRaises(RuntimeError):
                controller.start()
            self.assertIsNone(controller.snapshot().status)
            self.assertFalse(controller.snapshot().session_connected)
            self.assertEqual(controller.snapshot().feature_switches, {})
        backend.current = STATUS
        self.assertEqual(controller.start().status, STATUS)
        controller.shutdown()

    def test_explicit_selection_stays_pinned_and_failed_start_clears_state(self):
        backend = SwitchingBackend(STATUS, B)
        controller = BudsController(backend, address=STATUS.device.address)
        controller.start()
        backend.current = B
        backend.sessions[0].polls = [ConnectionError('gone')]
        with self.assertRaises(RuntimeError):
            controller.poll()
        self.assertEqual(controller.address, STATUS.device.address)
        self.assertIsNone(controller.snapshot().status)
        self.assertEqual(len(backend.sessions), 1)

    def test_failed_authentication_does_not_publish_partial_device(self):
        backend = SwitchingBackend(STATUS, B)
        original = backend.open_session
        def open_session(*args, **kwargs):
            session = original(*args, **kwargs)
            def fail():
                raise RuntimeError('authentication failed')
            session.authenticate_and_subscribe = fail
            return session
        backend.open_session = open_session
        controller = BudsController(backend)
        with self.assertRaises(RuntimeError):
            controller.start()
        self.assertIsNone(controller.address)
        self.assertIsNone(serialize_snapshot(controller.snapshot())['status'])
        self.assertEqual(backend.sessions[0].exits, 1)
