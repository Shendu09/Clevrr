from __future__ import annotations

import platform
import socket
import threading
import time
import uuid
from typing import Callable, Optional

from .message import BusMessage, MessageType
from .transport import (
    TCP_HOST,
    TCP_PORT,
    UNIX_SOCKET_PATH,
    WIN_PIPE_NAME,
    frame,
    recv_framed,
)


class BusClient:
    def __init__(self, client_id: str = "") -> None:
        self._id = client_id or str(uuid.uuid4())[:8]
        self._sock: Optional[socket.socket] = None
        self._stop = threading.Event()
        self._subs: dict[str, Callable[[BusMessage], None]] = {}
        self._pending: dict[str, threading.Event] = {}
        self._replies: dict[str, BusMessage] = {}
        self._send_lock = threading.Lock()
        self.logger_name = f"clevrr.client.{self._id}"

    def connect(self) -> None:
        os_name = platform.system()
        if os_name != "Windows" and hasattr(socket, "AF_UNIX"):
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.connect(UNIX_SOCKET_PATH)
        else:
            _ = WIN_PIPE_NAME
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.connect((TCP_HOST, TCP_PORT))

        try:
            self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass

        threading.Thread(target=self._listen_loop, daemon=True).start()

    def disconnect(self) -> None:
        self._stop.set()
        if self._sock:
            self._sock.close()
            self._sock = None

    def publish(self, topic: str, payload: Optional[dict] = None) -> None:
        msg = BusMessage.publish(topic, payload or {}, self._id)
        self._send(msg)

    def request(
        self,
        topic: str,
        payload: Optional[dict] = None,
        timeout: float = 5.0,
    ) -> Optional[BusMessage]:
        msg = BusMessage.request(topic, payload or {}, self._id)
        evt = threading.Event()
        self._pending[msg.id] = evt
        self._send(msg)

        if evt.wait(timeout=timeout):
            return self._replies.pop(msg.id, None)

        self._pending.pop(msg.id, None)
        return None

    def subscribe(
        self,
        topic_pattern: str,
        handler: Callable[[BusMessage], None],
    ) -> None:
        self._subs[topic_pattern] = handler
        sub_msg = BusMessage(
            id=str(uuid.uuid4())[:8],
            type=MessageType.SUBSCRIBE,
            topic=topic_pattern,
            payload={},
            sender_id=self._id,
            reply_to="",
            ts=time.time(),
            ttl=30,
        )
        self._send(sub_msg)

    def _send(self, msg: BusMessage) -> None:
        if not self._sock:
            raise RuntimeError("Client is not connected")

        with self._send_lock:
            data = msg.to_bytes()
            self._sock.sendall(frame(data))

    def _listen_loop(self) -> None:
        if not self._sock:
            return

        while not self._stop.is_set():
            try:
                data = recv_framed(self._sock)
                if data is None:
                    break
                msg = BusMessage.from_bytes(data)
                self._handle(msg)
            except Exception:
                break

    def _handle(self, msg: BusMessage) -> None:
        if msg.type == MessageType.REPLY and msg.reply_to:
            if msg.reply_to in self._pending:
                self._replies[msg.reply_to] = msg
                self._pending.pop(msg.reply_to).set()
            return

        import fnmatch

        for pattern, handler in self._subs.items():
            if fnmatch.fnmatch(msg.topic, pattern):
                threading.Thread(target=handler, args=(msg,), daemon=True).start()
