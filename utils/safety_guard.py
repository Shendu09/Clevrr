"""
SafetyGuard — Local Action Safety Filter

Blocks dangerous commands, requires confirmation for sensitive ones,
and logs all decisions. Uses ONLY local pattern matching — no AI needed.
"""

import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict

import yaml

logger = logging.getLogger(__name__)


class SafetyGuard:
    """Protects the system by filtering dangerous or sensitive actions.

    Three decision levels:
    - **BLOCKED**: Action matches a known dangerous pattern. Never executed.
    - **CONFIRM**: Action is sensitive and requires explicit user approval.
    - **SAFE**: Action is allowed to proceed without intervention.

    All decisions are logged locally to ``data/safety_log.txt``.
    """

    def __init__(self, config_path: str = "config/safety_rules.yaml") -> None:
        """Initialize SafetyGuard with rules from YAML config.

        Args:
            config_path: Path to the safety_rules.yaml file.
        """
        self.config_path = config_path
        self.always_block: list = []
        self.always_confirm: list = []
        self.log_path = "data/safety_log.txt"

        # Ensure log directory exists
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)

        self._load_rules()
        logger.info(
            "SafetyGuard loaded: %d block rules, %d confirm rules.",
            len(self.always_block),
            len(self.always_confirm),
        )

    def _load_rules(self) -> None:
        """Load safety rules from the YAML configuration file."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                rules = yaml.safe_load(f) or {}

            self.always_block = [
                r.lower() for r in rules.get("always_block", [])
            ]
            self.always_confirm = [
                r.lower() for r in rules.get("always_confirm", [])
            ]

        except FileNotFoundError:
            logger.warning(
                "Safety rules file not found at %s. Using defaults.",
                self.config_path,
            )
            self.always_block = [
                "rm -rf",
                "format c:",
                "del /f /s /q",
                "delete system32",
                "mkfs",
                "dd if=",
                ":(){:|:&};:",
            ]
            self.always_confirm = [
                "delete",
                "remove",
                "uninstall",
                "payment",
                "transfer",
                "password",
                "format",
                "wipe",
                "send email",
                "purchase",
                "download",
                "install",
            ]

        except Exception as exc:
            logger.error("Error loading safety rules: %s", exc)

    # ------------------------------------------------------------------
    # Action Checking
    # ------------------------------------------------------------------

    def check_action(self, action_text: str) -> Dict[str, str]:
        """Evaluate an action against safety rules.

        Args:
            action_text: Description or command of the proposed action.

        Returns:
            Dictionary with keys ``decision``, ``reason``, and ``action``.
            ``decision`` is one of ``"BLOCKED"``, ``"CONFIRM"``, ``"SAFE"``.
        """
        lower = action_text.lower().strip()

        # 1. Check always_block patterns
        for pattern in self.always_block:
            if pattern in lower:
                result = {
                    "decision": "BLOCKED",
                    "reason": (
                        f"Action matches blocked pattern: '{pattern}'. "
                        f"This operation is NEVER allowed."
                    ),
                    "action": action_text,
                }
                self.log_decision(
                    action_text, result["decision"], result["reason"]
                )
                return result

        # 2. Check always_confirm patterns
        for pattern in self.always_confirm:
            if pattern in lower:
                result = {
                    "decision": "CONFIRM",
                    "reason": (
                        f"Action matches sensitive pattern: '{pattern}'. "
                        f"User confirmation required."
                    ),
                    "action": action_text,
                }
                self.log_decision(
                    action_text, result["decision"], result["reason"]
                )
                return result

        # 3. Default — safe
        result = {
            "decision": "SAFE",
            "reason": "No dangerous or sensitive patterns detected.",
            "action": action_text,
        }
        self.log_decision(action_text, result["decision"], result["reason"])
        return result

    def check_for_injection(self, text: str) -> Dict[str, str]:
        """Detect command-injection style patterns in plain text."""
        lower = (text or "").lower().strip()
        suspicious_tokens = [
            "&&",
            "||",
            ";",
            "|",
            "`",
            "$(",
            "%comspec%",
            "powershell -enc",
            "cmd /c",
        ]

        for token in suspicious_tokens:
            if token in lower:
                return {
                    "is_injection": True,
                    "reason": f"Potential command injection token detected: '{token}'",
                }

        return {
            "is_injection": False,
            "reason": "No injection patterns detected",
        }

    def check_voice_command(
        self,
        command: str,
        auth_result: dict,
    ) -> dict:
        """Apply voice auth and injection gates before normal safety checks."""
        if not auth_result.get("verified", True):
            return {
                "decision": "BLOCKED",
                "reason": (
                    f"Voice not recognized: {auth_result.get('reason')}"
                ),
                "severity": "HIGH",
            }

        injection = self.check_for_injection(command)
        if injection["is_injection"]:
            return {
                "decision": "BLOCKED",
                "reason": injection["reason"],
                "severity": "CRITICAL",
            }

        return self.check_action(command)

    # ------------------------------------------------------------------
    # User Confirmation
    # ------------------------------------------------------------------

    def request_confirmation(self, action: str) -> bool:
        """Show a confirmation dialog for sensitive actions.

        Displays a tkinter popup with YES / NO buttons.
        Auto-denies if no response within 30 seconds.

        Args:
            action: Description of the action to confirm.

        Returns:
            True if user approves, False otherwise.
        """
        result = {"approved": False}

        def _show_dialog() -> None:
            try:
                import tkinter as tk
                from tkinter import messagebox

                root = tk.Tk()
                root.withdraw()  # Hide main window
                root.attributes("-topmost", True)

                answer = messagebox.askyesno(
                    title="⚠️ Action Confirmation Required",
                    message=(
                        f"The agent wants to perform:\n\n"
                        f"  {action}\n\n"
                        f"Allow this action?"
                    ),
                )
                result["approved"] = answer
                root.destroy()

            except Exception as exc:
                logger.warning(
                    "GUI confirmation failed: %s. Defaulting to DENY.", exc
                )
                result["approved"] = False

        # Run dialog in a thread with a timeout
        dialog_thread = threading.Thread(target=_show_dialog, daemon=True)
        dialog_thread.start()
        dialog_thread.join(timeout=30)

        if dialog_thread.is_alive():
            logger.warning(
                "Confirmation timed out after 30s. Auto-denying action."
            )
            result["approved"] = False

        decision = "APPROVED" if result["approved"] else "DENIED"
        self.log_decision(action, decision, "User confirmation response")

        return result["approved"]

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log_decision(self, action: str, decision: str, reason: str) -> None:
        """Log a safety decision to the local log file.

        Args:
            action: The action that was evaluated.
            decision: The decision made (BLOCKED, CONFIRM, SAFE, etc.).
            reason: Explanation for the decision.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"{timestamp} | {decision:10s} | {action[:100]:100s} | {reason}\n"

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as exc:
            logger.warning("Failed to write safety log: %s", exc)
