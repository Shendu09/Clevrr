from __future__ import annotations

import logging
import platform
import time
from dataclasses import dataclass
from typing import Optional

from actions.calendar_action import CalendarAction
from actions.github_action import GitHubAction
from actions.gmail_action import GmailAction
from core.auth.consent_manager import ConsentManager
from core.auth.step_up_auth import StepUpAuth
from core.auth.token_vault import TokenVault
from core.security import SecurityGateway

from .intent_parser import ParsedIntent


@dataclass(slots=True)
class RouteResult:
    success: bool
    output: str
    error: Optional[str]
    intent: str
    service: str


class ActionRouter:
    def __init__(
        self,
        gateway: SecurityGateway,
        vault: TokenVault,
        step_up: StepUpAuth,
        consent: ConsentManager,
    ) -> None:
        self._gateway = gateway
        self._vault = vault
        self._step_up = step_up
        self._consent = consent
        self.logger = logging.getLogger("clevrr.brain.router")

    def route(self, user_id: str, intent: ParsedIntent) -> RouteResult:
        self.logger.info(
            f"Routing: intent={intent.intent} service={intent.service} confidence={intent.confidence:.2f}"
        )
        handlers = {
            "send_email": self._handle_gmail,
            "read_email": self._handle_gmail,
            "create_issue": self._handle_github,
            "create_event": self._handle_calendar,
            "open_app": self._handle_os_open,
            "take_screenshot": self._handle_screenshot,
            "unknown": self._handle_unknown,
        }
        return handlers.get(intent.intent, self._handle_unknown)(user_id, intent)

    def _handle_gmail(self, user_id: str, intent: ParsedIntent) -> RouteResult:
        action = GmailAction(user_id=user_id, vault=self._vault, step_up=self._step_up, consent=self._consent)
        params = intent.parameters
        result = (
            action.send_email(params.get("to", ""), params.get("subject", "Message from Clevrr"), params.get("body", ""))
            if intent.intent == "send_email"
            else action.read_inbox()
        )
        return RouteResult(result.success, result.output or result.error or "", result.error, intent.intent, "gmail")

    def _handle_github(self, user_id: str, intent: ParsedIntent) -> RouteResult:
        action = GitHubAction(user_id=user_id, vault=self._vault, step_up=self._step_up, consent=self._consent)
        params = intent.parameters
        result = action.create_issue(params.get("repo", ""), params.get("title", ""), params.get("body", ""))
        return RouteResult(result.success, result.output or result.error or "", result.error, intent.intent, "github")

    def _handle_calendar(self, user_id: str, intent: ParsedIntent) -> RouteResult:
        action = CalendarAction(user_id=user_id, vault=self._vault, step_up=self._step_up, consent=self._consent)
        params = intent.parameters
        result = action.create_event(params.get("title", ""), params.get("start", ""), params.get("end", ""), params.get("description", ""))
        return RouteResult(result.success, result.output or result.error or "", result.error, intent.intent, "calendar")

    def _handle_os_open(self, user_id: str, intent: ParsedIntent) -> RouteResult:
        app = intent.parameters.get("app", "")
        command = ["start", app] if platform.system() == "Windows" else ["xdg-open", app]
        result = self._gateway.run_command(user_id=user_id, command=command)
        output = f"Opened {app}" if result.success else (result.error or "")
        return RouteResult(result.success, output, result.error, intent.intent, "os")

    def _handle_screenshot(self, user_id: str, intent: ParsedIntent) -> RouteResult:
        out = f"data/screenshots/clevrr_{int(time.time())}.png"
        result = self._gateway.take_screenshot(user_id, out)
        output = f"Screenshot saved: {out}" if result.success else (result.error or "")
        return RouteResult(result.success, output, result.error, intent.intent, "os")

    def _handle_unknown(self, _user_id: str, _intent: ParsedIntent) -> RouteResult:
        return RouteResult(False, "I didn't understand that command.", "Unknown intent", "unknown", "none")
