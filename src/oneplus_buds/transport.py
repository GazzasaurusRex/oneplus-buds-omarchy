from __future__ import annotations

import socket
import time
from collections.abc import Callable

from .protocol import Frame, FrameStream, encode_frame


class RfcommTransport:
    def __init__(
        self,
        address: str,
        channel: int = 15,
        timeout: float = 3.0,
        connect_attempts: int = 1,
        retry_delay: float = 1.0,
    ) -> None:
        self.address = address
        self.channel = channel
        self.timeout = timeout
        self.connect_attempts = connect_attempts
        self.retry_delay = retry_delay
        self._socket: socket.socket | None = None
        self._sequence = 1
        self._stream = FrameStream()

    def __enter__(self) -> "RfcommTransport":
        for attempt in range(self.connect_attempts):
            sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            sock.settimeout(self.timeout)
            try:
                sock.connect((self.address, self.channel))
            except OSError as error:
                sock.close()
                if error.errno != 16 or attempt == self.connect_attempts - 1:
                    raise
                time.sleep(self.retry_delay)
            else:
                self._socket = sock
                return self
        raise RuntimeError("unreachable RFCOMM connection retry state")

    def __exit__(self, *_: object) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def query(
        self,
        command: int,
        payload: bytes = b"",
        wait: float = 0.15,
        sequence: int | None = None,
    ) -> list[Frame]:
        if self._socket is None:
            raise RuntimeError("transport is not connected")
        frame_sequence = self._sequence if sequence is None else sequence
        if sequence is None:
            self._sequence = 1 if frame_sequence == 0xFE else frame_sequence + 1
        self._socket.sendall(encode_frame(command, frame_sequence, payload))
        return self._receive_burst(wait)

    def exchange_raw(self, packet: bytes, wait: float) -> list[Frame]:
        if self._socket is None:
            raise RuntimeError("transport is not connected")
        self._socket.sendall(packet)
        return self._receive_burst(wait)

    def request(
        self,
        command: int,
        payload: bytes,
        response_command: int,
        *,
        sequence: int | None = None,
        on_sent: Callable[[], None] | None = None,
        on_frames: Callable[[list[Frame]], None] | None = None,
        timeout: float | None = None,
    ) -> Frame:
        """Wait for this transaction's reply, without a sleep or idle-burst drain.

        The caller serializes all reads/writes. Unrelated frames are delivered
        once to the session, including frames following the reply in one recv.
        A timeout never retries a setting write.
        """
        if self._socket is None:
            raise RuntimeError("transport is not connected")
        frame_sequence = self._sequence if sequence is None else sequence
        if sequence is None:
            self._sequence = 1 if frame_sequence == 0xFE else frame_sequence + 1
        self._socket.sendall(encode_frame(command, frame_sequence, payload))
        if on_sent:
            on_sent()
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("OPO response deadline expired")
                self._socket.settimeout(remaining)
                chunk = self._socket.recv(512)
                if not chunk:
                    raise ConnectionError("RFCOMM peer disconnected")
                frames = self._stream.feed(chunk)
                reply = next((frame for frame in frames
                              if frame.command == response_command
                              and frame.sequence == frame_sequence), None)
                if on_frames:
                    on_frames([frame for frame in frames if frame is not reply])
                if reply is not None:
                    return reply
        finally:
            self._socket.settimeout(self.timeout)

    def receive(self, wait: float = 0.0) -> list[Frame]:
        if self._socket is None:
            raise RuntimeError("transport is not connected")
        if wait == 0:
            # The service waits between polls outside the controller lock.
            # Bound each drain so notification floods cannot starve commands.
            frames: list[Frame] = []
            self._socket.setblocking(False)
            try:
                for _ in range(16):
                    try:
                        chunk = self._socket.recv(512)
                    except BlockingIOError:
                        break
                    if not chunk:
                        raise ConnectionError("RFCOMM peer disconnected")
                    frames.extend(self._stream.feed(chunk))
            finally:
                self._socket.settimeout(self.timeout)
            return frames
        return self._receive_burst(wait)

    def _receive_burst(self, wait: float) -> list[Frame]:
        if self._socket is None:
            raise RuntimeError("transport is not connected")
        time.sleep(wait)
        frames: list[Frame] = []
        deadline = time.monotonic() + self.timeout
        self._socket.settimeout(0.2)
        while time.monotonic() < deadline:
            try:
                chunk = self._socket.recv(512)
            except TimeoutError:
                break
            if not chunk:
                break
            frames.extend(self._stream.feed(chunk))
        self._socket.settimeout(self.timeout)
        return frames
