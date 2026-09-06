import unittest
from threading import Event, Thread
from unittest.mock import MagicMock, Mock, patch

from oneplus_buds.controller import BudsController
from oneplus_buds.models import ControlResult, EventBatch
from oneplus_buds.profiles import PROFILES
from oneplus_buds.protocol import Frame, SET_ANC, QUERY_ANC, encode_frame
from oneplus_buds.session import OpoSession
from oneplus_buds.timing import AncRequestError
from oneplus_buds.transport import RfcommTransport
from test_controller import DEVICE, FakeBackend, FakeSession


class TransactionTests(unittest.TestCase):
    def transport(self, chunks):
        transport = RfcommTransport(DEVICE.address)
        transport._socket = Mock()
        transport._socket.recv.side_effect = chunks
        return transport

    @patch('oneplus_buds.transport.time.sleep')
    def test_fragmented_correlated_reply_preserves_other_frames_without_sleep(self, sleep):
        stale = encode_frame(0x810C, 99, b'old')
        ack = encode_frame(0x8404, 1, b'\x00')
        reply = encode_frame(0x810C, 1, b'\x00\x01\x01\x01')
        notification = encode_frame(0x0204, 0xff, b'\x06private')
        transport = self.transport([stale + ack + reply[:4], reply[4:] + notification])
        collected = []
        sent = Mock()
        result = transport.request(QUERY_ANC, b'\x01\x01', 0x810C,
                                   on_sent=sent, on_frames=collected.extend)
        self.assertEqual(result.sequence, 1)
        self.assertEqual([f.command for f in collected], [0x810C, 0x8404, 0x0204])
        sleep.assert_not_called()
        sent.assert_called_once()
        transport._socket.sendall.assert_called_once()
        transport._socket.settimeout.assert_called_with(3.0)

    def test_timeout_or_eof_never_retries_write(self):
        for failure in [TimeoutError(), b'']:
            transport = self.transport([failure])
            with self.assertRaises(OSError):
                transport.request(SET_ANC, b'\x01\x01\x01', 0x8404)
            transport._socket.sendall.assert_called_once()
            transport._socket.settimeout.assert_called_with(3.0)

    @patch('oneplus_buds.transport.time.monotonic', side_effect=[0, 0, 4])
    def test_unrelated_frame_flood_cannot_extend_deadline(self, _clock):
        transport = self.transport([encode_frame(0x0204, 0xff, b'x')])
        with self.assertRaises(TimeoutError):
            transport.request(QUERY_ANC, b'\x01\x01', 0x810C)
        self.assertEqual(transport._socket.recv.call_count, 1)

    @patch('oneplus_buds.transport.time.sleep')
    def test_nonblocking_poll_and_disconnect(self, sleep):
        transport = self.transport([encode_frame(0x0204, 1, b'\x06'), BlockingIOError()])
        self.assertEqual(len(transport.receive(0)), 1)
        sleep.assert_not_called()
        transport._socket.settimeout.assert_called_with(3.0)
        transport._socket.recv.side_effect = [b'']
        with self.assertRaises(ConnectionError):
            transport.receive(0)


class SessionControlTests(unittest.TestCase):
    def session(self, product='062014', state=b'\x00\x01\x01\x01', ack=b'\x00'):
        session = OpoSession(DEVICE, PROFILES[product])
        session._connected = session._authenticated = True
        transport = MagicMock()
        def request(command, payload, response_command, **kwargs):
            if kwargs.get('on_sent'):
                kwargs['on_sent']()
            kwargs['on_frames']([Frame(0x0204, 0xff, b'\x06private peer data')])
            if command == SET_ANC and isinstance(ack, Exception):
                raise ack
            return Frame(response_command, 1, ack if command == SET_ANC else state)
        transport.request.side_effect = request
        session._transport = transport
        return session

    def test_both_profiles_verify_query_without_reauth_or_resubscription(self):
        for product in PROFILES:
            session = self.session(product, ack=b'\x0e')
            result, batch = session.set_anc('off')
            self.assertTrue(result.verified)
            self.assertEqual(result.set_status, 14)
            self.assertLessEqual(result.timings_ms['command_sent_elapsed'], result.timings_ms['verified_elapsed'])
            self.assertEqual([c.args[0] for c in session._transport.request.call_args_list], [SET_ANC, QUERY_ANC])
            session._transport.exchange_raw.assert_not_called()
            session._transport.__exit__.assert_not_called()
            self.assertNotIn('private', repr(batch))

    def test_ack_missing_still_requires_fresh_query(self):
        session = self.session(ack=TimeoutError())
        result, _ = session.set_anc('off')
        self.assertTrue(result.verified)
        self.assertIsNone(result.set_status)
        self.assertEqual(session._transport.request.call_count, 2)

    def test_mismatch_invalid_status_and_missing_state_never_verify(self):
        for state in [b'\x00\x01\x01\x02', b'\x01\x01\x01\x01', b'']:
            session = self.session(state=state)
            with self.assertRaises(AncRequestError):
                session.set_anc('off')

    def test_settling_requeries_state_but_never_replays_write(self):
        session = self.session()
        session._transport.request.side_effect = [
            Frame(0x8404, 0x40, b'\x00'),
            Frame(0x810C, 1, b'\x00\x01\x01\x02'),
            Frame(0x810C, 2, b'\x00\x01\x01\x01'),
        ]
        result, _ = session.set_anc('off')
        self.assertTrue(result.verified)
        self.assertEqual(result.verification_queries, 2)
        self.assertEqual([call.args[0] for call in session._transport.request.call_args_list],
                         [SET_ANC, QUERY_ANC, QUERY_ANC])

    def test_permanent_mismatch_has_bounded_queries(self):
        session = self.session(state=b'\x00\x01\x01\x02')
        with self.assertRaises(AncRequestError):
            session.set_anc('off')
        self.assertEqual(session._transport.request.call_count, 33)

    def test_unknown_mode_and_unauthenticated_session_cannot_write(self):
        session = self.session()
        with self.assertRaises(ValueError):
            session.set_anc('unknown')
        session._authenticated = False
        with self.assertRaises(RuntimeError):
            session.set_anc('off')
        session._transport.request.assert_not_called()


class ControllerReuseTests(unittest.TestCase):
    def controller(self):
        session = FakeSession()
        session.set_anc = Mock(return_value=(ControlResult(DEVICE.name, '062014', 'off', None, 0, True), EventBatch((), 0)))
        backend = FakeBackend([session, FakeSession()])
        backend.set_anc = Mock()
        controller = BudsController(backend)
        controller.start()
        return controller, session, backend

    def test_reuses_session_and_does_not_restore_monitoring(self):
        controller, session, backend = self.controller()
        for _ in range(2):
            self.assertTrue(controller.set_anc('off').verified)
        self.assertEqual(session.enters, 1)
        self.assertEqual(session.exits, 0)
        self.assertEqual(controller.snapshot().advertised_event_codes, (1, 2))
        backend.set_anc.assert_not_called()
        controller.shutdown()
        self.assertEqual(session.exits, 1)

    def test_atomic_result_snapshot_is_detached_from_later_monitoring(self):
        controller, session, _ = self.controller()
        result, snapshot = controller.set_anc_with_snapshot('off')
        controller.shutdown()
        self.assertTrue(result.verified)
        self.assertTrue(snapshot.session_connected)
        self.assertEqual(snapshot.status.anc, 'off')
        self.assertFalse(controller.snapshot().session_connected)

    def test_two_commands_serialize_on_the_same_session(self):
        controller, session, _ = self.controller()
        entered, release, second_started = Event(), Event(), Event()
        result = session.set_anc.return_value
        calls = []
        def write(mode):
            calls.append(mode)
            if len(calls) == 1:
                entered.set()
                release.wait(2)
            return result
        session.set_anc.side_effect = write
        first = Thread(target=controller.set_anc, args=('off',))
        def second_request():
            second_started.set()
            controller.set_anc('on')
        second = Thread(target=second_request)
        first.start()
        self.assertTrue(entered.wait(1))
        second.start()
        self.assertTrue(second_started.wait(1))
        self.assertEqual(calls, ['off'])
        release.set()
        first.join(1)
        second.join(1)
        self.assertEqual(calls, ['off', 'on'])
        self.assertEqual(session.enters, 1)
        controller.shutdown()

    def test_failure_is_not_retried_or_delayed_by_recovery(self):
        controller, session, backend = self.controller()
        session.set_anc.side_effect = AncRequestError('mismatch', {})
        with self.assertRaises(AncRequestError):
            controller.set_anc('off')
        self.assertEqual(session.exits, 1)
        self.assertIsNone(controller.snapshot().status.anc)
        self.assertEqual(len(backend.sessions), 1)
        backend.set_anc.assert_not_called()
        controller.poll(0)
        self.assertTrue(controller.snapshot().session_connected)
        controller.shutdown()

    def test_poll_and_shutdown_wait_for_command_owner(self):
        controller, session, _ = self.controller()
        entered, release, stopped = Event(), Event(), Event()
        result = session.set_anc.return_value
        def write(_mode):
            entered.set()
            release.wait(2)
            return result
        session.set_anc.side_effect = write
        worker = Thread(target=controller.set_anc, args=('off',))
        worker.start()
        self.assertTrue(entered.wait(1))
        closer = Thread(target=lambda: (controller.shutdown(), stopped.set()))
        closer.start()
        self.assertFalse(stopped.wait(0.02))
        self.assertEqual(session.exits, 0)
        release.set()
        worker.join(1)
        closer.join(1)
        self.assertTrue(stopped.is_set())
        self.assertEqual(session.exits, 1)
