from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from .config import AuthConfig


@dataclass(slots=True)
class StepUpResult:
    required: bool
    approved: bool
    action: str
    user_id: str
    timestamp: float
    method: str


class StepUpAuth:
    def __init__(self, config: AuthConfig) -> None:
        self._config = config
        self.logger = logging.getLogger("clevrr.auth.stepup")

    def is_high_risk(self, action: str) -> bool:
        return action in self._config.high_risk_actions

    def request(
        self,
        user_id: str,
        action: str,
        context: Optional[dict] = None,
    ) -> StepUpResult:
        if not self.is_high_risk(action):
            return StepUpResult(
                required=False,
                approved=True,
                action=action,
                user_id=user_id,
                timestamp=time.time(),
                method="not_required",
            )

        self.logger.warning(f"STEP-UP REQUIRED: {action} by {user_id}")
        print(f"\n{'=' * 50}")
        print("CLEVRR SECURITY — High Risk Action")
        print(f"{'=' * 50}")
        print(f"User:    {user_id}")
        print(f"Action:  {action}")
        if context:
            print(f"Context: {context}")
        print(f"{'=' * 50}")

        try:
            answer = input("Approve this action? (yes/no): ")
            approved = answer.strip().lower() in ("yes", "y")
        except (EOFError, KeyboardInterrupt):
            approved = False

        state = "APPROVED" if approved else "DENIED"
        self.logger.info(f"Step-up {state}: {action}")
        return StepUpResult(
            required=True,
            approved=approved,
            action=action,
            user_id=user_id,
            timestamp=time.time(),
            method="console_confirmation",
        )
