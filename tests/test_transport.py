import unittest
from unittest.mock import Mock, patch

from oneplus_buds.transport import RfcommTransport


class TransportTests(unittest.TestCase):
    @patch("oneplus_buds.transport.time.sleep")
    @patch("oneplus_buds.transport.socket.socket")
    def test_retries_transient_busy(self, socket_factory, sleep):
        sockets = [Mock(), Mock(), Mock()]
        sockets[0].connect.side_effect = OSError(16, "busy")
        sockets[1].connect.side_effect = OSError(16, "busy")
        socket_factory.side_effect = sockets

        with RfcommTransport("AA:BB:CC:DD:EE:FF", connect_attempts=3, retry_delay=0.25):
            pass

        self.assertEqual(socket_factory.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        sockets[0].close.assert_called_once()
        sockets[1].close.assert_called_once()
        sockets[2].close.assert_called_once()

    @patch("oneplus_buds.transport.time.sleep")
    @patch("oneplus_buds.transport.socket.socket")
    def test_does_not_retry_non_busy_error(self, socket_factory, sleep):
        sock = Mock()
        sock.connect.side_effect = OSError(13, "denied")
        socket_factory.return_value = sock
        with self.assertRaises(OSError):
            with RfcommTransport("AA:BB:CC:DD:EE:FF", connect_attempts=3):
                pass
        self.assertEqual(socket_factory.call_count, 1)
        sleep.assert_not_called()
        sock.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
