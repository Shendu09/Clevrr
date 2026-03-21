from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass(slots=True)
class LatencySample:
    topic: str
    latency_ms: float
    timestamp: float


class BusMetrics:
    def __init__(self, enabled: bool = True, window: int = 1000) -> None:
        self.enabled = enabled
        self._samples: deque[LatencySample] = deque(maxlen=window)
        self._lock = threading.Lock()
        self._msg_count: int = 0
        self._start_time: float = time.time()
        self._per_topic: dict[str, int] = {}

    def record(self, topic: str, latency_ms: float) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._samples.append(
                LatencySample(
                    topic=topic,
                    latency_ms=latency_ms,
                    timestamp=time.time(),
                )
            )
            self._msg_count += 1
            self._per_topic[topic] = self._per_topic.get(topic, 0) + 1

    def summary(self) -> dict:
        with self._lock:
            if not self._samples:
                return {"status": "no data"}

            latencies = [sample.latency_ms for sample in self._samples]
            elapsed = time.time() - self._start_time
            ordered = sorted(latencies)
            p95_index = int(len(ordered) * 0.95)
            if p95_index >= len(ordered):
                p95_index = len(ordered) - 1

            return {
                "total_messages": self._msg_count,
                "throughput_per_s": round(self._msg_count / max(elapsed, 1), 1),
                "latency_ms": {
                    "min": round(min(latencies), 2),
                    "max": round(max(latencies), 2),
                    "avg": round(sum(latencies) / len(latencies), 2),
                    "p95": round(ordered[p95_index], 2),
                },
                "per_topic": dict(self._per_topic),
            }

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()
            self._msg_count = 0
            self._start_time = time.time()
            self._per_topic.clear()
