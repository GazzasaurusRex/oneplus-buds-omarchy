import json
import unittest
from unittest.mock import patch

from oneplus_buds.backend import set_anc
from oneplus_buds.bridge import BudsFrontendBridge
from oneplus_buds.controller import BudsController
from oneplus_buds.protocol import QUERY_ANC, QUERY_PRODUCT_ID, SET_ANC, Frame
from oneplus_buds.timing import AncRequestError, PhaseTimer
from test_backend import DEVICE, FakeTransport
from test_controller import FakeBackend, FakeSession


class TimingTests(unittest.TestCase):
    def test_monotonic_phase_durations_and_total(self):
        with patch('oneplus_buds.timing.monotonic', side_effect=[10, 10.25, 11, 11.5]):
            timer = PhaseTimer()
            timer.mark('hello')
            timer.mark('register')
            self.assertEqual(timer.finish('total'),
                             {'hello': 250, 'register': 750, 'total': 1500})

    @patch('oneplus_buds.backend.select_device', return_value=DEVICE)
    def test_backend_times_independent_verification_and_rejects_mismatch(self, _device):
        for state, succeeds in [(b'\x00\x01\x01\x01', True), (b'\x00\x01\x01\x02', False)]:
            control = FakeTransport({QUERY_PRODUCT_ID: [Frame(0x8103, 1, b'\x00\x14\x20\x06')],
                                     SET_ANC: [Frame(0x8404, 2, b'\x00')]})
            verifier = FakeTransport({QUERY_ANC: [Frame(0x810c, 3, state)]})
            with patch('oneplus_buds.backend.RfcommTransport', side_effect=[control, verifier]) as factory:
                if succeeds:
                    result = set_anc('off')
                    self.assertTrue(result['verified'])
                    timings = result['timings_ms']
                else:
                    with self.assertRaises(AncRequestError) as caught:
                        set_anc('off')
                    timings = caught.exception.timings_ms
                self.assertEqual(factory.call_count, 2)
            self.assertTrue({'hello', 'register', 'set_exchange', 'verify_connect',
                             'verify_query', 'backend_total'} <= timings.keys())
            self.assertTrue(all(isinstance(v, float) and v >= 0 for v in timings.values()))
            self.assertNotIn(DEVICE.address, json.dumps(timings))

    def test_controller_includes_resume_and_preserves_failure_timings_in_bridge(self):
        backend = FakeBackend([FakeSession(), FakeSession(), FakeSession()])
        controller = BudsController(backend, reuse_session=False)
        controller.start()
        result = controller.set_anc('off')
        self.assertIn('monitor_resume', result.timings_ms)
        self.assertIn('controller_lock_wait', result.timings_ms)
        with patch.object(backend, 'set_anc', side_effect=AncRequestError('failed', {'hello': 2000.0})):
            response = BudsFrontendBridge(lambda _: None, controller=controller).execute('set_anc', {'mode': 'on'})
        self.assertFalse(response['ok'])
        timings = response['error']['timings_ms']
        self.assertEqual(timings['hello'], 2000.0)
        self.assertIn('monitor_recovery', timings)
        self.assertIn('controller_total', timings)
        self.assertTrue(controller.snapshot().session_connected)
        controller.shutdown()
