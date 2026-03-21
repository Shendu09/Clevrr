from __future__ import annotations

import threading
import time
import uuid
from typing import Callable, Generic, TypeVar

from .message import BusMessage, MessageType

T = TypeVar("T")


class ObjectPool(Generic[T]):
    def __init__(
        self,
        factory: Callable[[], T],
        reset: Callable[[T], None],
        size: int = 50,
    ) -> None:
        self._factory = factory
        self._reset = reset
        self._max_size = size
        self._pool: list[T] = [factory() for _ in range(size)]
        self._lock = threading.Lock()
        self._created = size
        self._reused = 0
        self._exhausted = 0

    def acquire(self) -> T:
        with self._lock:
            if self._pool:
                obj = self._pool.pop()
                self._reused += 1
                return obj

        self._exhausted += 1
        self._created += 1
        return self._factory()

    def release(self, obj: T) -> None:
        self._reset(obj)
        with self._lock:
            if len(self._pool) < self._max_size:
                self._pool.append(obj)

    def stats(self) -> dict[str, str | int]:
        return {
            "pool_size": len(self._pool),
            "created": self._created,
            "reused": self._reused,
            "exhausted": self._exhausted,
            "reuse_rate": f"{self._reused / (self._created or 1) * 100:.1f}%",
        }


def _make_message() -> BusMessage:
    return BusMessage(
        id=str(uuid.uuid4())[:8],
        type=MessageType.PUBLISH,
        topic="",
        payload={},
        sender_id="",
        reply_to="",
        ts=time.time(),
        ttl=30,
    )


def _reset_message(msg: BusMessage) -> None:
    msg.reset()


message_pool = ObjectPool(
    factory=_make_message,
    reset=_reset_message,
    size=50,
)
