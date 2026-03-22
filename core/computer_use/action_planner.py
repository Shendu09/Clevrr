from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass, field
from enum import Enum

from .config import ComputerUseConfig
from .screen_reader import ScreenUnderstanding


class ActionType(str, Enum):
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    HOTKEY = "hotkey"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    OPEN_APP = "open_app"
    NAVIGATE = "navigate"
    DONE = "done"
    FAILED = "failed"


@dataclass(slots=True)
class PlannedAction:
    action_type: ActionType
    target: str
    value: str
    reason: str
    confidence: float
    is_final: bool = field(init=False)

    def __post_init__(self) -> None:
        self.is_final = self.action_type in {ActionType.DONE, ActionType.FAILED}


class ActionPlanner:
    def __init__(self, config: ComputerUseConfig) -> None:
        self._config = config
        self.logger = logging.getLogger("clevrr.cu.planner")
        self._step_history: list[str] = []

    def plan_next_action(self, goal: str, screen: ScreenUnderstanding, step_number: int) -> PlannedAction:
        history_text = "\n".join(self._step_history[-5:]) or "No steps taken yet"
        prompt = (
            "You are controlling a computer to achieve a goal.\n"
            "Analyze the current screen and decide the SINGLE next action.\n\n"
            f"GOAL: {goal}\nSTEP: {step_number} of {self._config.max_steps}\n"
            f"STEPS TAKEN SO FAR:\n{history_text}\n\n"
            f"CURRENT SCREEN:\n- Active app: {screen.active_app}\n"
            f"- Page title: {screen.page_title}\n"
            f"- Visible text: {screen.visible_text[:500]}\n"
            f"- Clickable elements: {screen.clickable_elements[:10]}\n"
            f"- Input fields: {screen.input_fields[:5]}\n"
            f"- Current URL: {screen.current_url}\n"
            f"- Task relevant: {screen.task_relevant}\n"
            "Choose one action: click,type,scroll,hotkey,wait,navigate,open_app,done,failed.\n"
            "Return ONLY JSON with action_type,target,value,reason,confidence."
        )
        try:
            payload = json.dumps(
                {
                    "model": self._config.action_model,
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
            with urllib.request.urlopen(req, timeout=20) as response:
                result = json.loads(response.read())
            data = json.loads(result.get("response", "{}"))
            action = PlannedAction(
                action_type=ActionType(data.get("action_type", "failed")),
                target=data.get("target", ""),
                value=data.get("value", ""),
                reason=data.get("reason", ""),
                confidence=float(data.get("confidence", 0.5)),
            )
            self._step_history.append(
                f"Step {step_number}: {action.action_type.value} — {action.reason}"
            )
            return action
        except Exception as exc:
            self.logger.error("Planning failed: %s", exc)
            return PlannedAction(
                action_type=ActionType.FAILED,
                target="",
                value="",
                reason=f"Planning error: {exc}",
                confidence=0.0,
            )

    def reset(self) -> None:
        self._step_history.clear()
