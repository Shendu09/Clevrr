from __future__ import annotations

import fnmatch
import logging
import socket
import threading
import time
from typing import Optional

from .message import BusMessage, MessageType
from .metrics import BusMetrics
from .object_pool import message_pool
from .topic_queue import TopicQueueManager
from .transport import TransportServer


class BusServer:
    def __init__(self) -> None:
        self._queues = TopicQueueManager(per_topic_maxsize={"vision.screenshot": 5})
        self._metrics = BusMetrics(enabled=True)
        self._transport = TransportServer(on_message=self._on_incoming)
        self._subscriptions: dict[str, set[socket.socket]] = {}
        self._sub_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._dispatch_thread: Optional[threading.Thread] = None
        self.logger = logging.getLogger("clevrr.bus")

    def start(self) -> None:
        self._stop_event.clear()
        self._transport.start()
        self._dispatch_thread = threading.Thread(
            target=self._dispatch_loop,
            name="clevrr-bus-dispatch",
            daemon=True,
        )
        self._dispatch_thread.start()
        self.logger.info("Bus server started")

    def stop(self) -> None:
        self._stop_event.set()
        self._transport.stop()
        if self._dispatch_thread:
            self._dispatch_thread.join(timeout=3)
        self.logger.info("Bus server stopped")

    def get_metrics(self) -> dict:
        return {
            **self._metrics.summary(),
            "queues": self._queues.sizes(),
            "dropped": self._queues.dropped(),
            "pool": message_pool.stats(),
        }

    def _on_incoming(self, msg: BusMessage, conn: socket.socket) -> None:
        if msg.type == MessageType.SUBSCRIBE:
            self._handle_subscribe(msg.topic, conn)
            return

        if msg.type == MessageType.UNSUBSCRIBE:
            self._handle_unsubscribe(msg.topic, conn)
            return

        if msg.type in {MessageType.PUBLISH, MessageType.REQUEST, MessageType.REPLY}:
            self._queues.put(msg)

    def _handle_subscribe(self, pattern: str, conn: socket.socket) -> None:
        with self._sub_lock:
            if pattern not in self._subscriptions:
                self._subscriptions[pattern] = set()
            self._subscriptions[pattern].add(conn)

    def _handle_unsubscribe(self, pattern: str, conn: socket.socket) -> None:
        with self._sub_lock:
            if pattern in self._subscriptions:
                self._subscriptions[pattern].discard(conn)

    def _dispatch_loop(self) -> None:
        while not self._stop_event.is_set():
            msg = self._queues.get_any(timeout=0.05)
            if msg is None:
                continue
            start = time.monotonic()
            self._dispatch(msg)
            latency_ms = (time.monotonic() - start) * 1000
            self._metrics.record(msg.topic, latency_ms)

    def _dispatch(self, msg: BusMessage) -> None:
        with self._sub_lock:
            targets: list[socket.socket] = []
            for pattern, sockets in self._subscriptions.items():
                if fnmatch.fnmatch(msg.topic, pattern):
                    targets.extend(sockets)

        dead: list[socket.socket] = []
        for sock in targets:
            try:
                self._transport.send(sock, msg)
            except Exception:
                dead.append(sock)

        if dead:
            with self._sub_lock:
                dead_set = set(dead)
                for pattern in self._subscriptions:
                    self._subscriptions[pattern] -= dead_set
