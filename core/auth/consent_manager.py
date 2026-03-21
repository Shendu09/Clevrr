from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ConsentRecord:
    user_id: str
    service: str
    scopes: list[str]
    granted_at: float
    granted_by: str
    active: bool = True


class ConsentManager:
    def __init__(self) -> None:
        self._records: list[ConsentRecord] = []
        self._lock = threading.Lock()
        self.logger = logging.getLogger("clevrr.auth.consent")

    def grant(
        self,
        user_id: str,
        service: str,
        scopes: list[str],
        granted_by: str = "user",
    ) -> ConsentRecord:
        with self._lock:
            existing = self._find(user_id, service)
            if existing:
                existing.scopes = scopes
                existing.granted_at = time.time()
                existing.active = True
                self.logger.info(f"Consent updated: {user_id} → {service}")
                return existing

            record = ConsentRecord(
                user_id=user_id,
                service=service,
                scopes=scopes,
                granted_at=time.time(),
                granted_by=granted_by,
                active=True,
            )
            self._records.append(record)
            self.logger.info(f"Consent granted: {user_id} → {service} scopes={scopes}")
            return record

    def revoke(self, user_id: str, service: str) -> bool:
        with self._lock:
            record = self._find(user_id, service)
            if record:
                record.active = False
                self.logger.info(f"Consent revoked: {user_id} → {service}")
                return True
            return False

    def has_consent(
        self,
        user_id: str,
        service: str,
        required_scopes: Optional[list[str]] = None,
    ) -> bool:
        with self._lock:
            record = self._find(user_id, service)
            if not record or not record.active:
                return False
            needed = required_scopes or []
            if not needed:
                return True
            return all(scope in record.scopes for scope in needed)

    def list_for_user(self, user_id: str) -> list[ConsentRecord]:
        with self._lock:
            return [r for r in self._records if r.user_id == user_id and r.active]

    def list_all(self) -> list[ConsentRecord]:
        with self._lock:
            return [r for r in self._records if r.active]

    def _find(self, user_id: str, service: str) -> Optional[ConsentRecord]:
        for record in self._records:
            if record.user_id == user_id and record.service == service:
                return record
        return None
