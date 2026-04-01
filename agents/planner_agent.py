"""
PlannerAgent — Local Task Planning via Ollama llama3

Breaks user tasks into executable step-by-step plans.
Leverages memory for similar past tasks.
ALL reasoning goes through the local llama3 model via Ollama.
ZERO external APIs.
"""

import json
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from utils.ollama_client import OllamaClient
    from utils.memory_system import MemorySystem

logger = logging.getLogger(__name__)


class PlannerAgent:
    """Creates and adapts step-by-step execution plans using local LLM.

    Queries memory for similar past procedures and uses them as context
    to improve plan quality. All reasoning is done by the local llama3
    model through Ollama.
    """

    SYSTEM_PROMPT = (
        "You are a computer automation planner. "
        "You MUST respond with ONLY valid JSON. "
        "You MUST only use these action_type values: "
        "click, double_click, right_click, type, press_key, "
        "open_app, scroll_up, scroll_down, close_window, "
        "save, save_and_close, minimize, maximize, "
        "find_and_click, wait, hotkey, select_all, "
        "copy, paste, undo, new_file. "
        "Never invent new action types not in this list. "
        "CRITICAL: ALWAYS COMPLETE THE TASK. Do NOT stop after opening an app. "
        "Every task MUST end with a result-producing action like: click equals, take photo, press enter. "
        "For calculator tasks: 1) open_app calculator, 2) wait 1, 3) type numbers, 4) find_and_click equals. "
        "For camera tasks: 1) open_app camera, 2) wait 2, 3) find_and_click take photo. "
        "When opening Chrome to search: ALWAYS use exactly these 5 steps in order: "
        "1) open_app chrome, "
        "2) wait 2 seconds, "
        "3) find_and_click address bar, "
        "4) type the search query, "
        "5) press_key enter. "
        "Never put a type step directly after open_app without waiting first."
    )

    def __init__(
        self,
        ollama_client: "OllamaClient",
        memory_system: "MemorySystem",
    ) -> None:
        """Initialize PlannerAgent.

        Args:
            ollama_client: Local Ollama client for LLM reasoning.
            memory_system: Memory system for past task lookup.
        """
        self.ollama = ollama_client
        self.memory = memory_system
        logger.info("PlannerAgent initialized (local llama3 model).")

    # ------------------------------------------------------------------
    # Plan Creation
    # ------------------------------------------------------------------

    def create_plan(
        self,
        task: str,
        screen_description: str = "",
        memory_context: Optional[List[dict]] = None,
    ) -> dict:
        """Create a step-by-step plan for the given task.

        Args:
            task: User's task description (e.g. "Open Notepad and type Hello").
            screen_description: Current screen state description.
            memory_context: Optional list of similar past episodes/procedures.

        Returns:
            Plan dictionary with task, total_steps, and steps list.
        """
        # Look up memory if not provided
        if memory_context is None:
            memory_context = self._gather_memory_context(task)

        prompt = self._build_plan_prompt(task, screen_description, memory_context)

        # Try 1: parse response directly
        try:
            raw_response = self.ollama.generate(
                prompt,
                system_prompt=self.SYSTEM_PROMPT,
                max_tokens=2048,
            )
            logger.info("Raw llama3 response: %s", raw_response)
            parsed = json.loads(raw_response)
            plan = self._normalize_plan(task, parsed)
            logger.info("Parsed plan steps: %d", len(plan["steps"]))
            if plan["steps"]:
                return plan
        except Exception as exc:
            logger.warning("Planner parse attempt 1 failed: %s", exc)

        # Try 2: strip everything before first { and after last }
        try:
            raw_response = self.ollama.generate(
                prompt,
                system_prompt=self.SYSTEM_PROMPT,
                max_tokens=2048,
            )
            logger.info("Raw llama3 response: %s", raw_response)
            start = raw_response.index("{")
            end = raw_response.rindex("}") + 1
            parsed = json.loads(raw_response[start:end])
            plan = self._normalize_plan(task, parsed)
            logger.info("Parsed plan steps: %d", len(plan["steps"]))
            if plan["steps"]:
                return plan
        except Exception as exc:
            logger.warning("Planner parse attempt 2 failed: %s", exc)

        # Try 3: ask llama3 again with a simpler prompt
        try:
            simpler_prompt = (
                f"Task: {task}\n"
                "Return only JSON with keys: task, total_steps, steps. "
                "Each step must include step_number, action_type, description, "
                "target, value, expected_outcome, timeout."
            )
            raw_response = self.ollama.generate(
                simpler_prompt,
                system_prompt=self.SYSTEM_PROMPT,
            )
            logger.info("Raw llama3 response: %s", raw_response)

            try:
                parsed = json.loads(raw_response)
            except Exception:
                start = raw_response.index("{")
                end = raw_response.rindex("}") + 1
                parsed = json.loads(raw_response[start:end])

            plan = self._normalize_plan(task, parsed)
            logger.info("Parsed plan steps: %d", len(plan["steps"]))
            if plan["steps"]:
                return plan
        except Exception as exc:
            logger.warning("Planner parse attempt 3 failed: %s", exc)

        # GAP 4 FIX: Recovery with simpler single-step fallback
        logger.info("Attempting single-step recovery plan...")
        recovery_plan = self._create_single_step_recovery(task, screen_description)
        if recovery_plan and recovery_plan.get("steps"):
            logger.info("Recovery plan created with %d step(s)", len(recovery_plan["steps"]))
            return recovery_plan

        logger.error("All plan generation attempts failed. Using basic fallback plan.")
        return self.create_fallback_plan(task)

    # ------------------------------------------------------------------
    # Plan Adaptation
    # ------------------------------------------------------------------

    def adapt_plan(
        self,
        original_plan: dict,
        failed_at_step: int,
        current_screen: dict,
    ) -> dict:
        """Adapt a plan after a step fails.

        Keeps completed steps and regenerates from the failure point.

        Args:
            original_plan: The original plan dictionary.
            failed_at_step: Step number where failure occurred (1-indexed).
            current_screen: Current screen analysis from VisionAgent.

        Returns:
            Adapted plan dictionary.
        """
        task = original_plan.get("task", "unknown task")
        completed_steps = [
            s
            for s in original_plan.get("steps", [])
            if s.get("step_number", 0) < failed_at_step
        ]
        failed_step = None
        for s in original_plan.get("steps", []):
            if s.get("step_number", 0) == failed_at_step:
                failed_step = s
                break

        screen_desc = current_screen.get("screen_description", "")

        prompt = (
            f"I was automating this task: {task}\n\n"
            f"Steps completed so far:\n"
            f"{self._format_steps(completed_steps)}\n\n"
            f"Step {failed_at_step} FAILED:\n"
            f"{failed_step}\n\n"
            f"Current screen state:\n{screen_desc}\n\n"
            f"Create NEW remaining steps to complete the task from "
            f"the current state. Number them starting from "
            f"{failed_at_step}.\n\n"
            f"Respond in JSON:\n"
            f'{{"steps": [{{"step_number": N, "action_type": "...", '
            f'"description": "...", "target": "...", '
            f'"value": null, "expected_outcome": "...", '
            f'"timeout": 10}}]}}'
        )

        try:
            result = self.ollama.generate_json(prompt)
            new_steps = result.get("steps", [])

            # Merge completed + new steps
            all_steps = completed_steps + new_steps
            return {
                "task": task,
                "total_steps": len(all_steps),
                "steps": all_steps,
                "adapted": True,
                "adapted_from_step": failed_at_step,
            }

        except Exception as exc:
            logger.error("Plan adaptation failed: %s", exc)
            return original_plan

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _gather_memory_context(self, task: str) -> List[dict]:
        """Retrieve relevant memory context for a task."""
        context: List[dict] = []

        try:
            # Check for similar past procedures
            procedure = self.memory.find_procedure(task)
            if procedure:
                context.append(
                    {
                        "type": "procedure",
                        "goal": procedure["goal"],
                        "steps": procedure["steps"],
                        "success_rate": procedure["success_rate"],
                    }
                )

            # Check for similar past episodes
            episodes = self.memory.find_similar_episodes(task, limit=2)
            for ep in episodes:
                context.append(
                    {
                        "type": "episode",
                        "task": ep["task"],
                        "outcome": ep.get("outcome", ""),
                        "success": ep["success"],
                    }
                )

        except Exception as exc:
            logger.warning("Memory context retrieval failed: %s", exc)

        return context

    def _build_plan_prompt(
        self,
        task: str,
        screen_desc: str,
        memory_ctx: List[dict],
    ) -> str:
        """Build the full planning prompt."""

        memory_section = ""
        if memory_ctx:
            memory_section = (
                f"\nPast similar tasks for context:\n"
                f"{json.dumps(memory_ctx, indent=2)}\n"
            )

        screen_section = ""
        if screen_desc:
            screen_section = f"\nCurrent screen state:\n{screen_desc}\n"

        return (
            f"Create a step by step plan to accomplish this task: {task}\n"
            f"{screen_section}"
            f"{memory_section}"
            "Respond with ONLY this JSON structure, no extra text, "
            "no markdown, no code blocks, just raw JSON:\n"
            "{\n"
            "  \"task\": \"task description\",\n"
            "  \"total_steps\": 2,\n"
            "  \"steps\": [\n"
            "    {\n"
            "      \"step_number\": 1,\n"
            "      \"action_type\": \"open_app\",\n"
            "      \"description\": \"Open Notepad application\",\n"
            "      \"target\": \"notepad\",\n"
            "      \"value\": null,\n"
            "      \"expected_outcome\": \"Notepad opens on screen\",\n"
            "      \"timeout\": 10\n"
            "    },\n"
            "    {\n"
            "      \"step_number\": 2,\n"
            "      \"action_type\": \"type\",\n"
            "      \"description\": \"Type hello world\",\n"
            "      \"target\": \"notepad text area\",\n"
            "      \"value\": \"hello world\",\n"
            "      \"expected_outcome\": \"Text appears in notepad\",\n"
            "      \"timeout\": 5\n"
            "    }\n"
            "  ]\n"
            "}"
        )

    @staticmethod
    def _normalize_plan(task: str, raw_result: dict) -> dict:
        """Normalize the LLM response into a consistent plan format."""
        steps = raw_result.get("steps", [])

        # Ensure each step has required fields
        normalized_steps: List[dict] = []
        for i, step in enumerate(steps, start=1):
            normalized_steps.append(
                {
                    "step_number": step.get("step_number", i),
                    "action_type": step.get("action_type", "click"),
                    "description": step.get("description", ""),
                    "target": step.get("target", ""),
                    "value": step.get("value"),
                    "expected_outcome": step.get("expected_outcome", ""),
                    "timeout": step.get("timeout", 10),
                }
            )

        return {
            "task": task,
            "total_steps": len(normalized_steps),
            "steps": normalized_steps,
        }

    @staticmethod
    def _fallback_plan(task: str) -> dict:
        """Return a minimal fallback plan when planning fails."""
        return PlannerAgent.create_fallback_plan(task)

    def _create_single_step_recovery(self, task: str, screen_description: str) -> dict:
        """Create a single-step recovery plan when multi-step planning fails.

        Uses a much simpler prompt to get one action from the LLM.

        Args:
            task: The user task.
            screen_description: Current screen state.

        Returns:
            Plan with a single step, or None if recovery fails.
        """
        try:
            recovery_prompt = (
                f"Current screen: {screen_description}\n"
                f"Task: {task}\n\n"
                f"Generate ONE single next action to take.\n"
                f"Format your response as:\n"
                f"action_type|target|value\n\n"
                f"Example: click|search button|null\n"
                f"Example: type|search box|python tutorial\n"
                f"Example: open_app|chrome|null\n\n"
                f"Valid actions: click, type, press_key, open_app, wait, "
                f"scroll_up, scroll_down, find_and_click, double_click, hotkey"
            )

            response = self.ollama.generate(recovery_prompt)
            logger.debug("Recovery response: %s", response)

            # Parse pipe-separated format: action_type|target|value
            parts = response.strip().split("|")
            if len(parts) < 2:
                return None

            action_type = parts[0].strip().lower()
            target = parts[1].strip() if len(parts) > 1 else ""
            value = parts[2].strip() if len(parts) > 2 else None

            # Validate action type
            valid_actions = {
                "click", "type", "press_key", "open_app", "wait",
                "scroll_up", "scroll_down", "find_and_click", "double_click",
                "hotkey", "new_file", "save", "copy", "paste",
            }
            if action_type not in valid_actions:
                logger.warning("Invalid action type in recovery: %s", action_type)
                return None

            step = {
                "step_number": 1,
                "action_type": action_type,
                "description": f"{action_type} on {target}" if target else action_type,
                "target": target,
                "value": value if value != "null" else None,
                "expected_outcome": "One step of task completed",
                "timeout": 15,
            }

            return {
                "task": task,
                "total_steps": 1,
                "steps": [step],
                "recovery_mode": True,
            }

        except Exception as exc:
            logger.warning("Single-step recovery failed: %s", exc)
            return None

    @staticmethod
    def _create_fallback_plan(task: str) -> dict:
        """Create a very basic plan when LLM fails."""
        # Very basic plan when LLM fails
        return {
            "task": task,
            "total_steps": 1,
            "steps": [
                {
                    "step_number": 1,
                    "action_type": "open_app",
                    "description": f"Execute task: {task}",
                    "target": task,
                    "value": None,
                    "expected_outcome": "Task completed",
                    "timeout": 30,
                }
            ],
        }

    @staticmethod
    def _format_steps(steps: List[dict]) -> str:
        """Format steps into a readable string."""
        lines = []
        for s in steps:
            n = s.get("step_number", "?")
            desc = s.get("description", "?")
            lines.append(f"  {n}. {desc}")
        return "\n".join(lines) if lines else "  (none)"
