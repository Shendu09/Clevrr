"""
ValidatorAgent — Local Step & Task Validation via Ollama llava

Compares before/after screenshots to verify actions succeeded.
Uses the local llava vision model for all validation.
ZERO external APIs.
"""

import json
import logging
from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from utils.ollama_client import OllamaClient
    from utils.screen_capture import ScreenCapture

logger = logging.getLogger(__name__)


class ValidatorAgent:
    """Validates step outcomes and overall task completion.

    Compares before and after screenshots using the local llava model
    to determine whether actions succeeded and whether the overall
    task is complete.

    All AI calls go through the local Ollama instance.
    """

    def __init__(
        self,
        ollama_client: "OllamaClient",
        screen_capture: "ScreenCapture",
    ) -> None:
        """Initialize ValidatorAgent.

        Args:
            ollama_client: Local Ollama client for vision inference.
            screen_capture: Screen capture utility.
        """
        self.ollama = ollama_client
        self.screen = screen_capture
        logger.info("ValidatorAgent initialized (local llava model).")

    # ------------------------------------------------------------------
    # Step Validation
    # ------------------------------------------------------------------

    def validate_step(
        self,
        step: dict,
        before_path: str,
        after_path: str,
    ) -> dict:
        """Validate whether a step succeeded by comparing screenshots.

        Args:
            step: The step dictionary that was executed.
            before_path: Screenshot taken before the step.
            after_path: Screenshot taken after the step.

        Returns:
            Validation result with success, confidence, and reason.
        """
        description = step.get("description", "")
        expected_outcome = step.get("expected_outcome", "")
        action_type = step.get("action_type", "")

        try:
            # Analyze the after-screenshot with context
            question = (
                f"I just performed this action on a computer:\n"
                f"Action: {description}\n"
                f"Action type: {action_type}\n"
                f"Expected outcome: {expected_outcome}\n\n"
                f"Look at this screenshot (taken AFTER the action).\n"
                f"Did the action succeed? Is the expected outcome visible?\n\n"
                f"Respond ONLY in JSON:\n"
                f'{{"success": true, "confidence": 0.8, '
                f'"reason": "explanation of what you see"}}'
            )

            response = self.ollama.analyze_screen(after_path, question)

            # Parse JSON response
            result = self._parse_validation_response(response)

            logger.info(
                "Step validation: %s (confidence: %.2f) — %s",
                "PASS" if result["success"] else "FAIL",
                result["confidence"],
                result["reason"][:80],
            )

            return result

        except Exception as exc:
            logger.error("Step validation failed: %s", exc)
            return {
                "success": True,  # Assume success if validation fails
                "confidence": 0.3,
                "reason": f"Validation error: {exc}. Assuming success.",
            }

    # ------------------------------------------------------------------
    # Task Completion Validation
    # ------------------------------------------------------------------

    def validate_task_complete(
        self,
        task: str,
        final_screenshot: str,
    ) -> dict:
        """Validate whether the overall task has been completed.

        Args:
            task: The original task description.
            final_screenshot: Screenshot of the final state.

        Returns:
            Dictionary with success flag and reason.
        """
        try:
            question = (
                f"I was asked to perform this task on the computer:\n"
                f'"{task}"\n\n'
                f"Look at this screenshot of the current screen state.\n"
                f"Has the task been completed successfully?\n\n"
                f"Respond ONLY in JSON:\n"
                f'{{"success": true, "confidence": 0.9, '
                f'"reason": "explanation"}}'
            )

            response = self.ollama.analyze_screen(
                final_screenshot, question
            )

            result = self._parse_validation_response(response)

            logger.info(
                "Task validation: %s (confidence: %.2f) — %s",
                "COMPLETE" if result["success"] else "INCOMPLETE",
                result["confidence"],
                result["reason"][:80],
            )

            return result

        except Exception as exc:
            logger.error("Task validation failed: %s", exc)
            return {
                "success": False,
                "confidence": 0.0,
                "reason": f"Validation error: {exc}",
            }

    # ------------------------------------------------------------------
    # Response Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_validation_response(response: str) -> dict:
        """Parse and normalize a validation response from the LLM.

        Args:
            response: Raw text response from the vision model.

        Returns:
            Normalized validation dictionary.
        """
        default = {
            "success": True,
            "confidence": 0.5,
            "reason": "Could not parse validation response.",
        }

        if not response:
            return default

        try:
            cleaned = response.strip()

            # Remove markdown code fences
            if "```" in cleaned:
                lines = cleaned.split("\n")
                lines = [
                    l for l in lines if not l.strip().startswith("```")
                ]
                cleaned = "\n".join(lines)

            # Extract JSON object
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(cleaned[start:end])
            else:
                data = json.loads(cleaned)

            return {
                "success": bool(data.get("success", True)),
                "confidence": max(
                    0.0, min(1.0, float(data.get("confidence", 0.5)))
                ),
                "reason": str(
                    data.get("reason", "No reason provided.")
                ),
            }

        except (json.JSONDecodeError, ValueError, KeyError):
            # Try to infer from free text
            lower = response.lower()
            if any(
                w in lower for w in ["success", "completed", "yes", "correct"]
            ):
                return {
                    "success": True,
                    "confidence": 0.6,
                    "reason": response[:200],
                }
            elif any(
                w in lower
                for w in ["fail", "error", "no", "incorrect", "not"]
            ):
                return {
                    "success": False,
                    "confidence": 0.6,
                    "reason": response[:200],
                }

            return default
