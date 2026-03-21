from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ThreatLevel(str, Enum):
    SAFE = "SAFE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(slots=True)
class ThreatResult:
    safe: bool
    level: ThreatLevel
    threat_type: Optional[str]
    matched_rule: Optional[str]
    input_text: str
    sanitized: Optional[str]


class ThreatDetector:
    _FLAGS = re.IGNORECASE | re.DOTALL

    def __init__(self, custom_rules: Optional[dict] = None) -> None:
        self._rules: list[tuple[str, ThreatLevel, str, re.Pattern[str]]] = []
        self._load_defaults()
        if custom_rules:
            for name, pattern in custom_rules.items():
                self.add_rule(str(name), str(pattern))

    def _compile(self, patterns: list[str]) -> list[re.Pattern[str]]:
        return [re.compile(pattern, self._FLAGS) for pattern in patterns]

    def _load_defaults(self) -> None:
        categories: list[tuple[str, ThreatLevel, list[str]]] = [
            (
                "prompt_injection",
                ThreatLevel.HIGH,
                [
                    r"ignore\s+(all\s+)?(previous|prior|your|the)?\s*(instructions|rules|guidelines|constraints|system)",
                    r"you are now",
                    r"pretend (you are|to be|you're)",
                    r"your new (instructions|role|purpose|task) (is|are)",
                    r"forget (everything|all|your)",
                    r"act as (if )?you (have no|don't have) (restrictions|limits|rules)",
                    r"DAN mode",
                    r"jailbreak",
                    r"override (safety|security|restrictions|guidelines)",
                    r"system prompt",
                    r"\[\[.*?\]\]",
                    r"<\|.*?\|>",
                ],
            ),
            (
                "dangerous_command",
                ThreatLevel.CRITICAL,
                [
                    r"rm\s+-rf\s+[/~]",
                    r"rm\s+--no-preserve-root",
                    r":\(\)\{.*\};:",
                    r"dd\s+if=.*of=/dev/",
                    r"mkfs\.",
                    r"shred\s+",
                    r"wipefs",
                    r"chmod\s+-R\s+777\s+/",
                    r"curl.*\|\s*(bash|sh|python)",
                    r"wget.*\|\s*(bash|sh|python)",
                    r"nc\s+-e",
                    r"/dev/tcp/",
                    r"format\s+[a-zA-Z]:",
                    r"del\s+/[sq].*\*",
                    r"rd\s+/[sq]\s+[a-zA-Z]:\\",
                    r"reg\s+(delete|add).*HKLM\\SYSTEM",
                    r"bcdedit",
                    r"wmic\s+.*delete",
                    r"net\s+user\s+.*\s+/delete",
                    r"powershell.*-enc",
                    r"powershell.*bypass",
                    r"invoke-expression",
                    r"iex\(",
                ],
            ),
            (
                "data_exfiltration",
                ThreatLevel.CRITICAL,
                [
                    r"(curl|wget|nc|ncat)\s+.*\s+(passwd|shadow|\.ssh|credentials|secrets|\.env|api.?key)",
                    r"cat\s+.*(passwd|shadow|authorized_keys|\.ssh|\.aws|credentials)",
                    r"type\s+.*\.(env|credentials|config|key|pem|pfx)",
                    r"copy\s+.*\.(key|pem|pfx|p12)\s+",
                    r"base64.*\/etc\/(passwd|shadow)",
                    r"python.*socket.*send",
                ],
            ),
            (
                "privilege_escalation",
                ThreatLevel.HIGH,
                [
                    r"sudo\s+su",
                    r"sudo\s+bash",
                    r"sudo\s+python.*-c",
                    r"sudo\s+chmod.*\+s",
                    r"pkexec",
                    r"doas\s+",
                    r"runas\s+/user:.*administrator",
                    r"psexec.*-s",
                ],
            ),
        ]

        for threat_type, level, pattern_list in categories:
            compiled = self._compile(pattern_list)
            for pattern, compiled_pattern in zip(pattern_list, compiled):
                rule_name = pattern
                self._rules.append((threat_type, level, rule_name, compiled_pattern))

    def scan(self, text: str) -> ThreatResult:
        for threat_type, level, rule_name, compiled_pattern in self._rules:
            if compiled_pattern.search(text):
                return ThreatResult(
                    safe=False,
                    level=level,
                    threat_type=threat_type,
                    matched_rule=rule_name,
                    input_text=text,
                    sanitized=None,
                )

        return ThreatResult(
            safe=True,
            level=ThreatLevel.SAFE,
            threat_type=None,
            matched_rule=None,
            input_text=text,
            sanitized=text,
        )

    def scan_batch(self, texts: list[str]) -> list[ThreatResult]:
        return [self.scan(text) for text in texts]

    def add_rule(self, name: str, pattern: str) -> None:
        compiled = self._compile([pattern])[0]
        _ = name
        self._rules.append(("custom", ThreatLevel.MEDIUM, pattern, compiled))

    def explain(self, result: ThreatResult) -> str:
        if result.safe:
            return "Input is safe."
        return (
            f"Blocked [{result.level.value}] — {result.threat_type}: "
            f"matched rule `{result.matched_rule}`"
        )