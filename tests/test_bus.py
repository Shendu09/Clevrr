from __future__ import annotations

import json
import socket
import time
from pathlib import Path

import pytest

from core.bus.bus_client import BusClient
from core.bus.bus_server import BusServer
from core.bus.message import BusMessage, MessageType
from core.bus.metrics import BusMetrics
from core.bus.object_pool import ObjectPool
from core.bus.topic_queue import TopicQueueManager
from core.bus.topics import Topics
from core.bus.transport import frame, recv_framed


def test_topic_constants() -> None:
    all_topics = Topics.all()
    assert len(all_topics) == 16
    voice_topics = Topics.for_layer("voice")
    assert len(voice_topics) == 3
    assert "voice.transcript" in voice_topics


def test_message_serialization_msgpack() -> None:
    msg = BusMessage.publish("voice.transcript", {"text": "hello"}, "voice")
    raw = msg.to_bytes()
    parsed = BusMessage.from_bytes(raw)

    assert parsed.id == msg.id
    assert parsed.type == msg.type
    assert parsed.topic == msg.topic
    assert parsed.payload == msg.payload
    assert parsed.sender_id == msg.sender_id
    assert parsed.reply_to == msg.reply_to
    assert parsed.ttl == msg.ttl


def test_message_short_field_names() -> None:
    msg = BusMessage.publish("ai.command", {"k": "v"}, "ai")
    encoded = msg.to_bytes()

    try:
        import msgpack

        decoded = msgpack.unpackb(encoded, raw=False)
    except Exception:
        decoded = json.loads(encoded.decode("utf-8"))

    assert {"i", "t", "p", "d"}.issubset(set(decoded.keys()))

    full = json.dumps(
        {
            "id": msg.id,
            "type": msg.type.value,
            "topic": msg.topic,
            "payload": msg.payload,
            "sender_id": msg.sender_id,
            "reply_to": msg.reply_to,
            "timestamp": msg.ts,
            "ttl": msg.ttl,
        }
    ).encode("utf-8")
    assert len(encoded) < len(full)


def test_message_expiry() -> None:
    msg = BusMessage.publish("voice.transcript", {"t": 1}, "voice")
    msg.ttl = 0
    time.sleep(0.1)
    assert msg.is_expired()


def test_object_pool_reuse() -> None:
    pool = ObjectPool(factory=lambda: {"v": 1}, reset=lambda o: o.clear(), size=2)
    obj = pool.acquire()
    pool.release(obj)
    _ = pool.acquire()
    stats = pool.stats()
    reuse_rate = float(str(stats["reuse_rate"]).replace("%", ""))
    assert reuse_rate > 0.0


def test_object_pool_exhaustion() -> None:
    pool = ObjectPool(factory=lambda: object(), reset=lambda o: None, size=50)
    objs = [pool.acquire() for _ in range(50)]
    extra = pool.acquire()
    assert extra is not None
    stats = pool.stats()
    assert int(stats["exhausted"]) >= 1
    for obj in objs:
        pool.release(obj)


def test_per_topic_queue_isolation() -> None:
    manager = TopicQueueManager(default_maxsize=200, per_topic_maxsize={"vision.screenshot": 10})
    for _ in range(200):
        ok = manager.put(BusMessage.publish("voice.transcript", {"x": 1}))
        assert ok

    assert manager.get("vision.screenshot", timeout=0.01) is None


def test_queue_drops_expired() -> None:
    manager = TopicQueueManager(default_maxsize=5)
    msg = BusMessage.publish("voice.transcript", {"x": 1})
    msg.ttl = 0
    time.sleep(0.02)
    assert not manager.put(msg)
    dropped = manager.dropped()
    assert dropped["voice.transcript"] == 1


def test_queue_size_limit() -> None:
    manager = TopicQueueManager(default_maxsize=3)
    assert manager.put(BusMessage.publish("voice.transcript", {}))
    assert manager.put(BusMessage.publish("voice.transcript", {}))
    assert manager.put(BusMessage.publish("voice.transcript", {}))
    assert manager.put(BusMessage.publish("voice.transcript", {})) is False


def test_framing_roundtrip() -> None:
    for size in (1, 1024, 65536):
        data = b"x" * size
        s1, s2 = socket.socketpair()
        try:
            s1.sendall(frame(data))
            received = recv_framed(s2)
            assert received == data
        finally:
            s1.close()
            s2.close()


def test_metrics_tracking() -> None:
    metrics = BusMetrics(enabled=True, window=1000)
    for i in range(100):
        metrics.record("ai.command" if i % 2 == 0 else "voice.transcript", float(i) / 10)

    summary = metrics.summary()
    assert summary["total_messages"] == 100
    assert summary["latency_ms"]["min"] == 0.0
    assert summary["latency_ms"]["max"] == 9.9
    assert "p95" in summary["latency_ms"]
    assert summary["per_topic"]["ai.command"] == 50


def test_client_subscribe_and_publish(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from core.bus import bus_client as bus_client_mod
    from core.bus import transport as transport_mod

    sock_path = tmp_path / "bus_test.sock"
    monkeypatch.setattr(transport_mod, "UNIX_SOCKET_PATH", str(sock_path))
    monkeypatch.setattr(bus_client_mod, "UNIX_SOCKET_PATH", str(sock_path))
    monkeypatch.setattr(transport_mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(bus_client_mod.platform, "system", lambda: "Linux")

    server = BusServer()
    server.start()
    time.sleep(0.1)

    received = threading_event = __import__("threading").Event()
    payload_box: dict[str, str] = {}

    def handler(msg: BusMessage) -> None:
        payload_box["text"] = msg.payload.get("text", "")
        threading_event.set()

    a = BusClient("a")
    b = BusClient("b")

    try:
        a.connect()
        b.connect()
        a.subscribe("voice.*", handler)
        time.sleep(0.1)
        b.publish("voice.transcript", {"text": "hello"})

        assert threading_event.wait(0.5)
        assert payload_box.get("text") == "hello"
    finally:
        a.disconnect()
        b.disconnect()
        server.stop()
