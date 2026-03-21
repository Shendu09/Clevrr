from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass(slots=True)
class MemoryTurn:
    command: str
    intent: str
    result: str
    timestamp: float
    success: bool


class BrainMemory:
    def __init__(self, max_turns: int = 10) -> None:
        self._turns: deque[MemoryTurn] = deque(maxlen=max_turns)
        self._lock = threading.Lock()

    def add(self, command: str, intent: str, result: str, success: bool) -> None:
        with self._lock:
            self._turns.append(
                MemoryTurn(
                    command=command,
                    intent=intent,
                    result=result,
                    timestamp=time.time(),
                    success=success,
                )
            )

    def get_context(self, n: int = 3) -> str:
        with self._lock:
            recent = list(self._turns)[-n:]
        if not recent:
            return ""
        lines: list[str] = []
        for turn in recent:
            status = "✓" if turn.success else "✗"
            lines.append(f"{status} User said: '{turn.command}' → {turn.intent}")
        return "\n".join(lines)

    def clear(self) -> None:
        with self._lock:
            self._turns.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._turns)
