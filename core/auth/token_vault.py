from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

from .config import AuthConfig


@dataclass(slots=True)
class TokenInfo:
    service: str
    user_id: str
    scopes: list[str]
    obtained_at: float

    def age_seconds(self) -> float:
        return time.time() - self.obtained_at


class TokenVault:
    def __init__(self, config: AuthConfig) -> None:
        self._config = config
        self._mgmt_token: Optional[str] = None
        self._mgmt_expires: float = 0.0
        self._access_log: list[dict] = []
        self.logger = logging.getLogger("clevrr.auth.vault")

    def get_token(
        self,
        user_id: str,
        service: str,
        scopes: Optional[list[str]] = None,
    ) -> Optional[str]:
        scope_list = scopes or []
        self.logger.info(f"Token requested: user={user_id} service={service}")
        self._access_log.append(
            {
                "user_id": user_id,
                "service": service,
                "timestamp": time.time(),
                "scopes": scope_list,
            }
        )

        try:
            mgmt = self._get_mgmt_token()
            response = requests.get(
                f"{self._config.mgmt_url}/users/{user_id}",
                headers={"Authorization": f"Bearer {mgmt}"},
                timeout=10,
            )
            if response.status_code != 200:
                self.logger.warning(f"User not found in Auth0: {user_id}")
                return None

            identities = response.json().get("identities", [])
            for identity in identities:
                if identity.get("provider") == service:
                    token = identity.get("access_token")
                    if token:
                        self.logger.info(f"Token obtained for {service} (user={user_id})")
                        return token

            self.logger.warning(
                f"No token found for {service} (user={user_id} not connected)"
            )
            return None
        except Exception as exc:
            self.logger.error(f"Token vault error: {exc}")
            return None

    def revoke_token(self, user_id: str, service: str) -> bool:
        try:
            mgmt = self._get_mgmt_token()
            response = requests.delete(
                f"{self._config.mgmt_url}/users/{user_id}/identities/{service}/{user_id}",
                headers={"Authorization": f"Bearer {mgmt}"},
                timeout=10,
            )
            success = response.status_code in (200, 204)
            state = "success" if success else "failed"
            self.logger.info(f"Token revoked for {service}: {state}")
            return success
        except Exception as exc:
            self.logger.error(f"Revoke error: {exc}")
            return False

    def has_connection(self, user_id: str, service: str) -> bool:
        return self.get_token(user_id, service) is not None

    def list_connections(self, user_id: str) -> list[dict]:
        try:
            mgmt = self._get_mgmt_token()
            response = requests.get(
                f"{self._config.mgmt_url}/users/{user_id}",
                headers={"Authorization": f"Bearer {mgmt}"},
                timeout=10,
            )
            if response.status_code != 200:
                return []
            identities = response.json().get("identities", [])
            return [
                {
                    "service": identity.get("provider", ""),
                    "user_id": identity.get("user_id", ""),
                    "connected": "access_token" in identity,
                    "social": identity.get("isSocial", False),
                }
                for identity in identities
            ]
        except Exception:
            return []

    def get_access_log(self) -> list[dict]:
        return list(self._access_log)

    def _get_mgmt_token(self) -> str:
        if self._mgmt_token and time.time() < self._mgmt_expires:
            return self._mgmt_token

        response = requests.post(
            self._config.token_url,
            json={
                "grant_type": "client_credentials",
                "client_id": self._config.client_id,
                "client_secret": self._config.client_secret,
                "audience": self._config.audience,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        self._mgmt_token = data["access_token"]
        self._mgmt_expires = time.time() + data.get("expires_in", 86400) - 300
        self.logger.debug("Management token refreshed")
        return self._mgmt_token
