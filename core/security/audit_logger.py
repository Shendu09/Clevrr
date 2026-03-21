from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class AuditEntry:
    seq: int
    timestamp: float
    user_id: str
    action: str
    target: Optional[str]
    allowed: bool
    reason: str
    prev_hash: str
    entry_hash: str = ""

    def compute_hash(self) -> str:
        payload = {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "action": self.action,
            "target": self.target,
            "allowed": self.allowed,
            "reason": self.reason,
            "prev_hash": self.prev_hash,
        }
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> AuditEntry:
        return cls(
            seq=int(d["seq"]),
            timestamp=float(d["timestamp"]),
            user_id=str(d["user_id"]),
            action=str(d["action"]),
            target=d.get("target"),
            allowed=bool(d["allowed"]),
            reason=str(d["reason"]),
            prev_hash=str(d["prev_hash"]),
            entry_hash=str(d.get("entry_hash", "")),
        )


class AuditLogger:
    GENESIS_HASH = "0" * 64

    def __init__(self, log_path: Path, max_bytes: int = 10 * 1024 * 1024) -> None:
        self._log_path = Path(log_path)
        self._max_bytes = max_bytes
        self._lock = threading.Lock()
        self._entries: list[AuditEntry] = []
        self._seq: int = 0

        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        if self._log_path.exists():
            self._load(self._log_path)

    def log(
        self,
        user_id: str,
        action: str,
        allowed: bool,
        reason: str,
        target: Optional[str] = None,
    ) -> AuditEntry:
        with self._lock:
            prev_hash = self._entries[-1].entry_hash if self._entries else self.GENESIS_HASH
            entry = AuditEntry(
                seq=self._seq,
                timestamp=time.time(),
                user_id=user_id,
                action=action,
                target=target,
                allowed=allowed,
                reason=reason,
                prev_hash=prev_hash,
            )
            entry.entry_hash = entry.compute_hash()
            self._entries.append(entry)
            self._seq += 1
            self._append_to_disk(entry)
            return entry

    def verify(self) -> tuple[bool, str]:
        if not self._entries:
            return True, "Empty log"

        prev_hash = self.GENESIS_HASH
        for entry in self._entries:
            recomputed = entry.compute_hash()
            if recomputed != entry.entry_hash:
                return False, f"Tampered at entry {entry.seq}: hash mismatch"
            if entry.prev_hash != prev_hash:
                return False, f"Chain broken at entry {entry.seq}: prev_hash mismatch"
            prev_hash = entry.entry_hash

        return True, f"Chain intact — {len(self._entries)} entries verified"

    def query(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        allowed: Optional[bool] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        results: list[AuditEntry] = []
        for entry in self._entries:
            if user_id is not None and entry.user_id != user_id:
                continue
            if action is not None and entry.action != action:
                continue
            if allowed is not None and entry.allowed != allowed:
                continue
            if since is not None and entry.timestamp < since:
                continue
            if until is not None and entry.timestamp > until:
                continue
            results.append(entry)

        return results[-limit:]

    def tail(self, n: int = 20) -> list[AuditEntry]:
        if n <= 0:
            return []
        return self._entries[-n:]

    def export_json(self, out_path: Path) -> None:
        destination = Path(out_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            payload = [entry.to_dict() for entry in self._entries]
            with destination.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)

    def _append_to_disk(self, entry: AuditEntry) -> None:
        line = json.dumps(entry.to_dict(), ensure_ascii=False)
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

        if self._log_path.stat().st_size > self._max_bytes:
            self._rotate()

    def _rotate(self) -> None:
        if not self._log_path.exists():
            return

        rotated_path = self._log_path.with_suffix(f".{int(time.time())}.log")
        self._log_path.rename(rotated_path)
        self._log_path.touch(exist_ok=True)

    def _load(self, path: Path) -> None:
        max_seq = -1
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw)
                    entry = AuditEntry.from_dict(parsed)
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    continue
                self._entries.append(entry)
                if entry.seq > max_seq:
                    max_seq = entry.seq

        self._seq = max_seq + 1