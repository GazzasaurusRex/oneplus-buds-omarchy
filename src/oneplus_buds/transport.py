from __future__ import annotations

import socket
import time

from .protocol import Frame, FrameStream, encode_frame


class RfcommTransport:
    def __init__(self, address: str, channel: int = 15, timeout: float = 3.0) -> None:
        self.address = address
        self.channel = channel
        self.timeout = timeout
        self._socket: socket.socket | None = None
        self._sequence = 1
        self._stream = FrameStream()

    def __enter__(self) -> "RfcommTransport":
        sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        sock.settimeout(self.timeout)
        sock.connect((self.address, self.channel))
        self._socket = sock
        return self

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
