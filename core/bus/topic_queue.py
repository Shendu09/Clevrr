from __future__ import annotations

import logging
import queue
import threading
from typing import Optional

from .message import BusMessage
from .topics import Topics


class TopicQueueManager:
    def __init__(
        self,
        default_maxsize: int = 200,
        per_topic_maxsize: Optional[dict[str, int]] = None,
    ) -> None:
        self.default_maxsize = default_maxsize
        self._per_topic_maxsize = per_topic_maxsize or {}
        self._queues: dict[str, queue.Queue[BusMessage]] = {}
        self._lock = threading.Lock()
        self._dropped_per_topic: dict[str, int] = {}
        self.logger = logging.getLogger("clevrr.bus.queues")

        for topic in Topics.all():
            size = self._per_topic_maxsize.get(topic, default_maxsize)
            self._queues[topic] = queue.Queue(maxsize=size)
            self._dropped_per_topic[topic] = 0

    def put(self, msg: BusMessage) -> bool:
        if msg.is_expired():
            with self._lock:
                self._dropped_per_topic[msg.topic] = (
                    self._dropped_per_topic.get(msg.topic, 0) + 1
                )
            return False

        q = self._get_or_create(msg.topic)
        try:
            q.put_nowait(msg)
            return True
        except queue.Full:
            with self._lock:
                self._dropped_per_topic[msg.topic] = (
                    self._dropped_per_topic.get(msg.topic, 0) + 1
                )
            self.logger.warning(f"Queue full for topic '{msg.topic}' — message dropped")
            return False

    def get(self, topic: str, timeout: float = 0.5) -> Optional[BusMessage]:
        q = self._get_or_create(topic)
        try:
            msg = q.get(timeout=timeout)
            if msg.is_expired():
                with self._lock:
                    self._dropped_per_topic[topic] = self._dropped_per_topic.get(topic, 0) + 1
                return None
            return msg
        except queue.Empty:
            return None

    def get_any(self, timeout: float = 0.1) -> Optional[BusMessage]:
        _ = timeout
        for topic, q in self._queues.items():
            try:
                msg = q.get_nowait()
                if not msg.is_expired():
                    return msg
                with self._lock:
                    self._dropped_per_topic[topic] = self._dropped_per_topic.get(topic, 0) + 1
            except queue.Empty:
                continue
        return None

    def sizes(self) -> dict[str, int]:
        return {topic: q.qsize() for topic, q in self._queues.items() if q.qsize() > 0}

    def dropped(self) -> dict[str, int]:
        return {
            topic: count
            for topic, count in self._dropped_per_topic.items()
            if count > 0
        }

    def _get_or_create(self, topic: str) -> queue.Queue[BusMessage]:
        with self._lock:
            if topic not in self._queues:
                self._queues[topic] = queue.Queue(maxsize=self.default_maxsize)
                self._dropped_per_topic[topic] = 0
            return self._queues[topic]
