from __future__ import annotations

import logging
import platform
import time
import webbrowser
from dataclasses import dataclass
from typing import Optional

from .action_planner import ActionType, PlannedAction
from .config import ComputerUseConfig

try:
    import pyautogui

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.3
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False


@dataclass(slots=True)
class ExecutionResult:
    success: bool
    action: str
    output: str
    error: Optional[str]
    screenshot_saved: Optional[str] = None


class ActionExecutor:
    def __init__(self, config: ComputerUseConfig, gateway, user_id: str = "clevrr-agent") -> None:
        self._config = config
        self._gateway = gateway
        self._user_id = user_id
        self.logger = logging.getLogger("clevrr.cu.executor")

    def execute(self, action: PlannedAction, step: int) -> ExecutionResult:
        self.logger.info("Step %s: %s — %s", step, action.action_type.value, action.reason)
        if self._config.dry_run:
            return ExecutionResult(
                success=True,
                action=action.action_type.value,
                output=(
                    f"[DRY RUN] Would: {action.action_type.value} "
                    f"target='{action.target}' value='{action.value}'"
                ),
                error=None,
            )
        if not _HAS_PYAUTOGUI:
            return ExecutionResult(False, action.action_type.value, "", "pyautogui not installed")
        try:
            if action.action_type == ActionType.CLICK:
                return self._click(action)
            if action.action_type == ActionType.TYPE:
                return self._type(action)
            if action.action_type == ActionType.SCROLL:
                return self._scroll(action)
            if action.action_type == ActionType.HOTKEY:
                return self._hotkey(action)
            if action.action_type == ActionType.WAIT:
                delay_ms = int(action.value) if action.value.isdigit() else 1000
                time.sleep(delay_ms / 1000.0)
                return ExecutionResult(True, "wait", f"Waited {delay_ms}ms", None)
            if action.action_type == ActionType.NAVIGATE:
                return self._navigate(action)
            if action.action_type == ActionType.OPEN_APP:
                return self._open_app(action)
            if action.action_type == ActionType.DONE:
                return ExecutionResult(True, "done", "Task completed successfully", None)
            if action.action_type == ActionType.FAILED:
                return ExecutionResult(False, "failed", "", f"Agent failed: {action.reason}")
            return ExecutionResult(False, "unknown", "", f"Unknown action: {action.action_type}")
        except Exception as exc:
            return ExecutionResult(False, action.action_type.value, "", str(exc))

    def _click(self, action: PlannedAction) -> ExecutionResult:
        try:
            pyautogui.click(action.target)
            return ExecutionResult(True, "click", f"Clicked: {action.target}", None)
        except Exception:
            pyautogui.click()
            return ExecutionResult(True, "click", "Clicked at current position", None)

    def _type(self, action: PlannedAction) -> ExecutionResult:
        pyautogui.click()
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.write(action.value, interval=0.05)
        return ExecutionResult(True, "type", f"Typed: {action.value[:50]}", None)

    def _scroll(self, action: PlannedAction) -> ExecutionResult:
        amount = -3 if action.value.lower() == "up" else 3
        pyautogui.scroll(amount)
        return ExecutionResult(True, "scroll", f"Scrolled {action.value or 'down'}", None)

    def _hotkey(self, action: PlannedAction) -> ExecutionResult:
        pyautogui.hotkey(*action.value.split("+"))
        return ExecutionResult(True, "hotkey", f"Pressed: {action.value}", None)

    def _navigate(self, action: PlannedAction) -> ExecutionResult:
        webbrowser.open(action.value)
        time.sleep(2)
        return ExecutionResult(True, "navigate", f"Navigated to: {action.value}", None)

    def _open_app(self, action: PlannedAction) -> ExecutionResult:
        command = ["cmd", "/c", "start", "", action.value] if platform.system() == "Windows" else ["xdg-open", action.value]
        result = self._gateway.run_command(self._user_id, command)
        return ExecutionResult(result.success, "open_app", f"Opened: {action.value}", result.error)
