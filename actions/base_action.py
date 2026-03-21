from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from core.auth.consent_manager import ConsentManager
from core.auth.step_up_auth import StepUpAuth
from core.auth.token_vault import TokenVault


@dataclass(slots=True)
class ActionResult:
    success: bool
    action: str
    service: str
    user_id: str
    output: Optional[str]
    error: Optional[str]
    duration_ms: float
    required_step_up: bool = False
    token_source: str = "auth0_token_vault"


class BaseAction(ABC):
    def __init__(
        self,
        user_id: str,
        vault: TokenVault,
        step_up: StepUpAuth,
        consent: ConsentManager,
    ) -> None:
        self._user_id = user_id
        self._vault = vault
        self._step_up = step_up
        self._consent = consent

    @property
    @abstractmethod
    def service_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def required_scopes(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def _execute(self, token: str, **kwargs) -> str:
        raise NotImplementedError

    def run(self, action_name: str, **kwargs) -> ActionResult:
        start = time.monotonic()

        if not self._consent.has_consent(self._user_id, self.service_name):
            return ActionResult(
                success=False,
                action=action_name,
                service=self.service_name,
                user_id=self._user_id,
                output=None,
                error=(
                    f"You haven't connected {self.service_name} yet. "
                    "Visit the Clevrr dashboard to connect it."
                ),
                duration_ms=0.0,
            )

        step_up_result = self._step_up.request(self._user_id, action_name, kwargs)
        if step_up_result.required and not step_up_result.approved:
            return ActionResult(
                success=False,
                action=action_name,
                service=self.service_name,
                user_id=self._user_id,
                output=None,
                error="Action denied — step-up auth not approved.",
                duration_ms=0.0,
                required_step_up=True,
            )

        token = self._vault.get_token(self._user_id, self.service_name, self.required_scopes)
        if not token:
            return ActionResult(
                success=False,
                action=action_name,
                service=self.service_name,
                user_id=self._user_id,
                output=None,
                error=(
                    f"Could not get token for {self.service_name}. "
                    "Token vault returned nothing. Check Auth0 connection."
                ),
                duration_ms=0.0,
            )

        try:
            output = self._execute(token, action_name=action_name, **kwargs)
            ms = (time.monotonic() - start) * 1000
            return ActionResult(
                success=True,
                action=action_name,
                service=self.service_name,
                user_id=self._user_id,
                output=output,
                error=None,
                duration_ms=round(ms, 1),
                required_step_up=step_up_result.required,
            )
        except Exception as exc:
            ms = (time.monotonic() - start) * 1000
            return ActionResult(
                success=False,
                action=action_name,
                service=self.service_name,
                user_id=self._user_id,
                output=None,
                error=str(exc),
                duration_ms=round(ms, 1),
            )
