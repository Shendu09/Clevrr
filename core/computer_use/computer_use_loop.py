from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .action_executor import ActionExecutor
from .action_planner import ActionPlanner, ActionType
from .agent_registry import AgentRegistry
from .config import ComputerUseConfig
from .screen_reader import ScreenReader


@dataclass(slots=True)
class TaskResult:
    goal: str
    success: bool
    steps_taken: int
    actions: list[str] = field(default_factory=list)
    final_output: str = ""
    error: Optional[str] = None
    duration_seconds: float = 0.0


class ComputerUseLoop:
    def __init__(
        self,
        config: ComputerUseConfig,
        gateway,
        user_id: str = "clevrr-agent",
        on_step: Optional[Callable] = None,
    ) -> None:
        self._config = config
        self._reader = ScreenReader(config)
        self._planner = ActionPlanner(config)
        self._executor = ActionExecutor(config, gateway, user_id)
        self._registry = AgentRegistry(config, gateway, user_id)
        self._on_step = on_step
        self.logger = logging.getLogger("clevrr.cu.loop")

    def run(self, goal: str, use_specialist: bool = True) -> TaskResult:
        self.logger.info("Starting task: '%s'", goal)
        start = time.monotonic()
        actions: list[str] = []
        self._planner.reset()

        if use_specialist:
            specialist = self._registry.get_agent(goal)
            if specialist:
                self.logger.info("Using specialist: %s", specialist.__class__.__name__)
                return specialist.run(goal)

        for step in range(1, self._config.max_steps + 1):
            screen = self._reader.capture_and_understand(goal)
            action = self._planner.plan_next_action(goal, screen, step)
            actions.append(f"{step}. {action.action_type.value}: {action.reason}")
            if self._on_step:
                self._on_step(step, action, screen)
            if action.action_type == ActionType.DONE:
                return TaskResult(goal, True, step, actions, "Task completed successfully", None, round(time.monotonic() - start, 1))
            if action.action_type == ActionType.FAILED:
                return TaskResult(goal, False, step, actions, "", action.reason, round(time.monotonic() - start, 1))
            result = self._executor.execute(action, step)
            if not result.success:
                self.logger.warning("Action failed: %s", result.error)
            time.sleep(self._config.step_delay_ms / 1000.0)

        return TaskResult(
            goal=goal,
            success=False,
            steps_taken=self._config.max_steps,
            actions=actions,
            final_output="",
            error=f"Max steps ({self._config.max_steps}) reached",
            duration_seconds=round(time.monotonic() - start, 1),
        )
