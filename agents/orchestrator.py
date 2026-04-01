"""
Orchestrator — Master Agent Coordinator

Coordinates all sub-agents: Vision, Planner, Executor, Validator, SelfHealer.
Manages the full lifecycle of a task from input to completion.
ALL AI goes through local Ollama. ZERO external APIs.
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.ollama_client import OllamaClient
from utils.screen_capture import ScreenCapture
from utils.memory_system import MemorySystem
from utils.safety_guard import SafetyGuard
from utils.voice_controller import VoiceController
from utils.self_healer import SelfHealer
from agents.vision_agent import VisionAgent
from agents.planner_agent import PlannerAgent
from agents.executor_agent import ExecutorAgent
from agents.validator_agent import ValidatorAgent

logger = logging.getLogger(__name__)


class Orchestrator:
    """Master coordinator that runs the full task automation pipeline.

    Pipeline:
    1. **Safety Check** — block dangerous, confirm sensitive actions.
    2. **Memory Recall** — find similar past tasks and procedures.
    3. **Planning** — create a step-by-step plan via local llama3.
    4. **Execution Loop** — execute each step, validate, heal on failure.
    5. **Memory Save** — record the episode for future learning.

    All AI calls are routed through the local Ollama instance.
    """

    def __init__(self, config: dict) -> None:
        """Initialize the Orchestrator and all sub-components.

        Args:
            config: Full configuration dictionary from settings.yaml.
        """
        agent_config = config.get("agent", {})
        self.max_retries: int = agent_config.get("max_retries", 3)
        self.step_timeout: int = agent_config.get("step_timeout", 30)
        self.heal_attempts: int = agent_config.get("heal_attempts", 3)
        self.confidence_threshold: float = agent_config.get(
            "confidence_threshold", 0.7
        )

        # --- Initialize all components ---
        logger.info("Initializing Orchestrator components...")

        self.ollama = OllamaClient(config)
        self.screen = ScreenCapture(config)
        self.memory = MemorySystem(config)
        self.safety = SafetyGuard("config/safety_rules.yaml")

        self.vision = VisionAgent(self.ollama, self.screen)
        self.planner = PlannerAgent(self.ollama, self.memory)
        self.executor = ExecutorAgent(self.screen, self.vision)
        self.validator = ValidatorAgent(self.ollama, self.screen)
        self.healer = SelfHealer(self.ollama, self.vision)

        # --- Task state ---
        self.current_task: Optional[str] = None
        self.current_step: int = 0
        self.total_steps: int = 0
        self.is_running: bool = False
        self.task_history: List[dict] = []

        logger.info("Orchestrator ready. All systems local.")

    # ------------------------------------------------------------------
    # Main Task Runner
    # ------------------------------------------------------------------

    def run_task(self, task_text: str) -> dict:
        """Run a complete task through the full pipeline.

        Args:
            task_text: Natural language description of the task.

        Returns:
            Result dictionary with success, steps completed, duration, etc.
        """
        logger.info(f"Starting task: {task_text}")
        print(f"[ORCHESTRATOR] Task received: {task_text}")

        start_time = time.time()
        self.current_task = task_text
        self.current_step = 0
        self.is_running = True

        logger.info("=" * 60)
        logger.info("TASK: %s", task_text)
        logger.info("=" * 60)

        result: Dict[str, Any] = {
            "success": False,
            "task": task_text,
            "steps_completed": 0,
            "total_steps": 0,
            "duration_seconds": 0.0,
            "outcome": "",
        }

        try:
            # ── Step 1: Safety Check ──────────────────────────────
            safety_result = self.safety.check_action(task_text)

            if safety_result["decision"] == "BLOCKED":
                result["outcome"] = (
                    f"BLOCKED: {safety_result['reason']}"
                )
                logger.warning("Task BLOCKED: %s", safety_result["reason"])
                self._finish_task(result, start_time)
                return result

            if safety_result["decision"] == "CONFIRM":
                logger.info("Task requires confirmation: %s", task_text)
                approved = self.safety.request_confirmation(task_text)
                if not approved:
                    result["outcome"] = "Task denied by user."
                    logger.info("Task DENIED by user.")
                    self._finish_task(result, start_time)
                    return result

            # ── Step 2: Memory Recall ────────────────────────────
            similar_episodes = self.memory.find_similar_episodes(
                task_text, limit=3
            )
            procedure = self.memory.find_procedure(task_text)

            memory_context = []
            if procedure:
                memory_context.append(
                    {
                        "type": "procedure",
                        "goal": procedure.get("goal", "Unknown goal"),
                        "steps": procedure.get("steps", []),
                        "success_rate": procedure.get("success_rate", 0.0),
                    }
                )
                success_rate = procedure.get("success_rate", 0.0)
                if success_rate > 0:
                    logger.info(
                        "Found matching procedure (success rate: %.0f%%)",
                        success_rate * 100,
                    )

            for ep in similar_episodes:
                memory_context.append(
                    {
                        "type": "episode",
                        "task": ep["task"],
                        "outcome": ep.get("outcome", ""),
                        "success": ep["success"],
                    }
                )

            if memory_context:
                logger.info(
                    "Memory context: %d items found.", len(memory_context)
                )

            # ── Step 3: Analyze Screen & Create Plan ──────────────
            screen_info = self.vision.analyze_screen()
            screen_desc = screen_info.get("screen_description", "")

            plan = self.planner.create_plan(
                task_text,
                screen_description=screen_desc,
                memory_context=memory_context,
            )

            self.total_steps = len(plan.get("steps", []))
            self.current_step = 0
            print(f"[ORCHESTRATOR] Total steps set to: {self.total_steps}")
            result["total_steps"] = self.total_steps

            logger.info(
                "Plan created: %d steps.", self.total_steps
            )

            if self.total_steps == 0:
                logger.info("Plan creation failed. Attempting single-step recovery...")
                recovery = self.planner._create_single_step_recovery(task_text, screen_desc)
                if recovery and recovery.get("steps"):
                    plan = recovery
                    self.total_steps = len(plan["steps"])
                    result["total_steps"] = self.total_steps
                    logger.info("Recovery successful: using single-step fallback plan")
                else:
                    result["outcome"] = "Planner could not create a valid plan."
                    self._finish_task(result, start_time)
                    return result

            # ── Step 4: Execute Each Step ─────────────────────────
            steps = plan.get("steps", [])
            
            print(f"[ORCHESTRATOR] Plan created: {len(steps)} steps")
            for step in steps:
               print(f"  Step {step['step_number']}: {step['description']}")

            steps_completed = 0

            for i, step in enumerate(steps, 1):
                if not self.is_running:
                    result["outcome"] = "Task cancelled by user."
                    break

                step_num = step.get("step_number", steps_completed + 1)
                self.current_step = step_num
                
                print(f"[EXECUTOR] Running step {step_num}: {step['description']}")

                logger.info(
                    "── Step %d/%d: %s",
                    step_num,
                    self.total_steps,
                    step.get("description", "")[:60],
                )

                # Safety check the specific action
                step_desc = step.get("description", "")
                step_safety = self.safety.check_action(step_desc)

                if step_safety["decision"] == "BLOCKED":
                    logger.warning("Step BLOCKED: %s", step_desc)
                    result["outcome"] = (
                        f"Step {step_num} blocked: {step_safety['reason']}"
                    )
                    break

                if step_safety["decision"] == "CONFIRM":
                    approved = self.safety.request_confirmation(step_desc)
                    if not approved:
                        result["outcome"] = (
                            f"Step {step_num} denied by user."
                        )
                        break

                # Take before screenshot
                before_path = self.screen.capture_primary()

                # Execute the step
                exec_result = self.executor.execute_step(step)
                after_path = exec_result.get("screenshot_after", "")

                # Validate the step
                if after_path and before_path:
                    validation = self.validator.validate_step(
                        step, before_path, after_path
                    )
                else:
                    validation = {
                        "success": exec_result["success"],
                        "confidence": 0.5,
                        "reason": "No screenshots for validation.",
                    }

                step_passed = (
                    validation["success"]
                    and validation["confidence"] >= self.confidence_threshold
                )

                if not step_passed and exec_result["success"]:
                    # Executor said OK but validator disagrees — trust validator
                    # if confidence is high enough
                    if validation["confidence"] >= 0.8:
                        step_passed = False
                    else:
                        step_passed = True  # Low confidence, give benefit of doubt

                if step_passed:
                    steps_completed += 1
                    logger.info("Step %d: PASSED ✓", step_num)
                    print(f"[VALIDATOR] Step {step_num} result: True")
                    
                    # GAP 3 FIX: Re-read screen after step to know current state
                    fresh_screen = self.vision.analyze_screen()
                    fresh_desc = fresh_screen.get("screen_description", "")
                    logger.debug(
                        "Step %d completed. Fresh screen state: %s",
                        step_num,
                        fresh_desc[:200] if fresh_desc else "unknown",
                    )
                    
                else:
                    print(f"[VALIDATOR] Step {step_num} result: False")
                    # Try healing
                    error = exec_result.get("error") or validation.get(
                        "reason", "Unknown failure"
                    )
                    logger.warning(
                        "Step %d: FAILED ✗ — attempting healing...", step_num
                    )

                    healed = self.healer.heal(step, error)

                    if healed:
                        # Retry the step
                        retry_result = self.executor.execute_step(step)
                        if retry_result["success"]:
                            steps_completed += 1
                            logger.info(
                                "Step %d: HEALED & PASSED ✓", step_num
                            )
                        else:
                            logger.error(
                                "Step %d: HEALING FAILED ✗", step_num
                            )
                            result["outcome"] = (
                                f"Failed at step {step_num} even after "
                                f"healing: {error}"
                            )
                            break
                    else:
                        # Try adapting the plan
                        logger.info("Attempting plan adaptation...")
                        current_screen = self.vision.analyze_screen()
                        adapted_plan = self.planner.adapt_plan(
                            plan, step_num, current_screen
                        )
                        if adapted_plan.get("adapted"):
                            plan = adapted_plan
                            self.total_steps = plan["total_steps"]
                            # Continue with adapted plan
                            steps_completed += 1
                            logger.info("Plan adapted. Continuing...")
                        else:
                            result["outcome"] = (
                                f"Failed at step {step_num}: {error}. "
                                f"Could not heal or adapt."
                            )
                            break

                # Brief pause between steps
                time.sleep(0.5)

            result["steps_completed"] = steps_completed
            result["success"] = steps_completed == self.total_steps

            if result["success"]:
                # Final validation
                final_shot = self.screen.capture_primary()
                if final_shot:
                    final_val = self.validator.validate_task_complete(
                        task_text, final_shot
                    )
                    result["success"] = final_val["success"]
                    result["outcome"] = (
                        final_val.get("reason", "Task completed successfully.")
                    )
                else:
                    result["outcome"] = "All steps completed."

            # ── Step 5: Save to Memory ────────────────────────────
            duration = time.time() - start_time
            result["duration_seconds"] = round(duration, 2)

            self.memory.save_episode(
                task=task_text,
                steps=steps,
                outcome=result["outcome"],
                success=result["success"],
                duration=duration,
            )

            if result["success"]:
                self.memory.save_procedure(task_text, steps)
                if procedure:
                    self.memory.update_procedure_success(
                        procedure["id"], True
                    )

            logger.info("=" * 60)
            logger.info(
                "RESULT: %s (%d/%d steps, %.1fs)",
                "SUCCESS" if result["success"] else "FAILED",
                result["steps_completed"],
                result["total_steps"],
                result["duration_seconds"],
            )
            logger.info("=" * 60)

        except Exception as exc:
            result["outcome"] = f"Unexpected error: {exc}"
            result["duration_seconds"] = round(
                time.time() - start_time, 2
            )
            logger.error("Task failed with error: %s", exc, exc_info=True)

        self._finish_task(result, start_time)
        return result

    # ------------------------------------------------------------------
    # Status & Control
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return the current task execution status.

        Returns:
            Dictionary with running state, current step, and progress.
        """
        progress = 0.0
        if self.total_steps > 0:
            progress = round(
                (self.current_step / self.total_steps) * 100, 1
            )

        return {
            "is_running": self.is_running,
            "current_task": self.current_task or "",
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "progress_percent": progress,
        }

    def cancel_task(self) -> str:
        """Cancel the currently running task.

        Returns:
            Cancellation status message.
        """
        if not self.is_running:
            return "No task is currently running."

        self.is_running = False
        task_name = self.current_task or "Unknown"
        logger.info("Task cancelled: %s", task_name)
        return f"Task cancelled: {task_name}"

    def get_history(self, limit: int = 10) -> List[dict]:
        """Return recent task history from memory.

        Args:
            limit: Maximum number of episodes to return.

        Returns:
            List of episode dictionaries.
        """
        return self.memory.get_recent_episodes(limit)

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _finish_task(self, result: dict, start_time: float) -> None:
        """Clean up after task completion."""
        self.is_running = False
        if not result.get("duration_seconds"):
            result["duration_seconds"] = round(
                time.time() - start_time, 2
            )

        self.task_history.append(
            {
                **result,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self.current_task = None
        self.current_step = 0
        self.total_steps = 0
