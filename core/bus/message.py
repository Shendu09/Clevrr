from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

try:
    import msgpack

    _USE_MSGPACK = True
except ImportError:
    import json

    _USE_MSGPACK = False


class MessageType(str, Enum):
    PUBLISH = "pub"
    REQUEST = "req"
    REPLY = "rep"
    SUBSCRIBE = "sub"
    UNSUBSCRIBE = "uns"
    HEARTBEAT = "hbt"
    ERROR = "err"


@dataclass(slots=True, frozen=False)
class BusMessage:
    id: str
    type: MessageType
    topic: str
    payload: dict[str, Any] = field(default_factory=dict)
    sender_id: str = ""
    reply_to: str = ""
    ts: float = field(default_factory=time.time)
    ttl: int = 30

    def reset(self) -> None:
        self.id = str(uuid.uuid4())[:8]
        self.type = MessageType.PUBLISH
        self.topic = ""
        self.payload = {}
        self.sender_id = ""
        self.reply_to = ""
        self.ts = time.time()
        self.ttl = 30

    def to_bytes(self) -> bytes:
        data = {
            "i": self.id,
            "t": self.type.value,
            "p": self.topic,
            "d": self.payload,
            "s": self.sender_id,
            "r": self.reply_to,
            "ts": self.ts,
            "ttl": self.ttl,
        }
        if _USE_MSGPACK:
            return msgpack.packb(data, use_bin_type=True)
        return json.dumps(data).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> BusMessage:
        if _USE_MSGPACK:
            decoded = msgpack.unpackb(data, raw=False)
        else:
            decoded = json.loads(data)
        return cls(
            id=decoded["i"],
            type=MessageType(decoded["t"]),
            topic=decoded["p"],
            payload=decoded["d"],
            sender_id=decoded["s"],
            reply_to=decoded["r"],
            ts=decoded["ts"],
            ttl=decoded["ttl"],
        )

    def is_expired(self) -> bool:
        return time.time() > self.ts + self.ttl

    def age_ms(self) -> float:
        return (time.time() - self.ts) * 1000

    @staticmethod
    def publish(
        topic: str,
        payload: Optional[dict[str, Any]] = None,
        sender: str = "",
    ) -> BusMessage:
        return BusMessage(
            id=str(uuid.uuid4())[:8],
            type=MessageType.PUBLISH,
            topic=topic,
            payload=payload or {},
            sender_id=sender,
            reply_to="",
            ts=time.time(),
            ttl=30,
        )

    @staticmethod
    def request(
        topic: str,
        payload: Optional[dict[str, Any]] = None,
        sender: str = "",
    ) -> BusMessage:
        return BusMessage(
            id=str(uuid.uuid4())[:8],
            type=MessageType.REQUEST,
            topic=topic,
            payload=payload or {},
            sender_id=sender,
            reply_to="",
            ts=time.time(),
            ttl=30,
        )

    @staticmethod
    def reply(
        original: BusMessage,
        payload: Optional[dict[str, Any]] = None,
        sender: str = "",
    ) -> BusMessage:
        return BusMessage(
            id=str(uuid.uuid4())[:8],
            type=MessageType.REPLY,
            topic=f"{original.topic}.reply",
            payload=payload or {},
            sender_id=sender,
            reply_to=original.id,
            ts=time.time(),
            ttl=30,
        )
