from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .config import BrainConfig
from .prompts import INTENT_SYSTEM_PROMPT, INTENT_USER_TEMPLATE


@dataclass(slots=True)
class ParsedIntent:
    intent: str
    service: str
    confidence: float
    parameters: dict = field(default_factory=dict)
    response: str = ""
    raw_text: str = ""

    def is_confident(self, threshold: float = 0.7) -> bool:
        return self.confidence >= threshold


class IntentParser:
    def __init__(self, config: BrainConfig) -> None:
        self._config = config
        self._available: bool | None = None
        self._last_check: float = 0.0
        self.logger = logging.getLogger("clevrr.brain.intent")

    def parse(self, command: str, context: str = "") -> ParsedIntent:
        if not self._check_ollama():
            return self._rule_based_parse(command)

        prompt = INTENT_USER_TEMPLATE.format(
            command=command,
            context=context or "No previous context",
        )
        try:
            payload = json.dumps(
                {
                    "model": self._config.ollama_model,
                    "system": INTENT_SYSTEM_PROMPT,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                }
            ).encode()
            req = urllib.request.Request(
                f"{self._config.ollama_host}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._config.ollama_timeout) as resp:
                result = json.loads(resp.read())
            raw = result.get("response", "{}")
            data = json.loads(raw)
            return ParsedIntent(
                intent=data.get("intent", "unknown"),
                service=data.get("service", "none"),
                confidence=float(data.get("confidence", 0.5)),
                parameters=data.get("parameters", {}),
                response=data.get("response", ""),
                raw_text=raw,
            )
        except Exception as exc:
            self.logger.warning(f"Ollama parse failed: {exc}. Using rule-based fallback.")
            return self._rule_based_parse(command)

    def _rule_based_parse(self, command: str) -> ParsedIntent:
        cmd = command.lower()
        if any(word in cmd for word in ["email", "mail", "send"]):
            to = ""
            words = cmd.split()
            if "to" in words:
                idx = words.index("to")
                if idx + 1 < len(words):
                    to = words[idx + 1]
            return ParsedIntent("send_email", "gmail", 0.8, {"to": to, "body": command}, f"Sending email to {to}")

        if any(word in cmd for word in ["issue", "github", "bug"]):
            return ParsedIntent("create_issue", "github", 0.8, {"title": command}, "Creating GitHub issue")

        if any(word in cmd for word in ["calendar", "meeting", "appointment", "event"]):
            return ParsedIntent("create_event", "calendar", 0.75, {"title": command}, "Creating calendar event")

        if any(word in cmd for word in ["open", "launch", "start"]):
            app = cmd.replace("open", "").replace("launch", "").replace("start", "").strip()
            return ParsedIntent("open_app", "os", 0.85, {"app": app}, f"Opening {app}")

        if any(word in cmd for word in ["screenshot", "screen", "capture"]):
            return ParsedIntent("take_screenshot", "os", 0.9, {}, "Taking screenshot")

        return ParsedIntent(
            "unknown",
            "none",
            0.1,
            {"raw": command},
            "I'm not sure what you want. Could you rephrase that?",
        )

    def _check_ollama(self) -> bool:
        now = time.time()
        if self._available is not None and (now - self._last_check) < 60:
            return self._available

        self._last_check = now
        try:
            urllib.request.urlopen(self._config.ollama_host, timeout=2)
            self._available = True
            return True
        except Exception:
            if self._available is None:
                self.logger.warning(
                    "Ollama not running. Using rule-based intent parsing. Start with: ollama serve"
                )
            self._available = False
            return False
