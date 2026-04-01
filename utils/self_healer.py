"""
SelfHealer — Automatic Failure Diagnosis & Recovery

Uses local Ollama (llama3) for intelligent failure analysis.
Attempts to recover from common problems automatically.
ZERO external APIs — all diagnosis runs through local LLM.
"""

import logging
import time
import random
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from utils.ollama_client import OllamaClient
    from agents.vision_agent import VisionAgent

logger = logging.getLogger(__name__)

# Known failure types
FAILURE_TYPES = [
    "element_not_found",
    "wrong_timing",
    "app_crashed",
    "unexpected_popup",
    "permission_denied",
    "network_error",
    "unknown",
]


def retry_with_backoff(func, max_attempts: int = 3, base_delay: float = 1.0):
    """Retry function with exponential backoff + jitter.
    
    Uses exponential backoff (base_delay * 2^attempt) with random jitter
    to avoid thundering herd problems. When Ollama is overloaded, this
    gives it time to recover gracefully.
    
    Args:
        func: Callable that may raise an exception.
        max_attempts: Maximum number of attempts (default 3).
        base_delay: Base delay in seconds (default 1.0).
        
    Returns:
        Result from func() on success.
        
    Raises:
        Final exception if all attempts fail.
    """
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            
            # Exponential backoff: 1s, 2s, 4s (base_delay=1.0)
            # + jitter (0-0.5s) to avoid synchronized retries
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            logger.warning(
                "[RETRY] Attempt %d/%d failed: %s. Waiting %.2fs before retry.",
                attempt + 1,
                max_attempts,
                type(e).__name__,
                delay
            )
            time.sleep(delay)


class SelfHealer:
    """Automatically diagnoses and attempts to fix failures.

    When a step fails, the healer:
    1. Takes a screenshot of the current state.
    2. Sends the failure context to the local llama3 model.
    3. Applies a recovery strategy based on the diagnosed failure type.
    4. Retries the failed step.

    All AI calls go through the local Ollama instance.
    """

    def __init__(
        self,
        ollama_client: "OllamaClient",
        vision_agent: "VisionAgent",
    ) -> None:
        """Initialize SelfHealer.

        Args:
            ollama_client: Local Ollama client for AI reasoning.
            vision_agent: Vision agent for screen analysis.
        """
        self.ollama = ollama_client
        self.vision = vision_agent
        self.healing_log: List[Dict[str, Any]] = []
        logger.info("SelfHealer initialized.")

    # ------------------------------------------------------------------
    # Diagnosis
    # ------------------------------------------------------------------

    def diagnose_failure(
        self,
        step: dict,
        error: str,
        screen_path: str,
    ) -> dict:
        """Diagnose why a step failed using the local LLM.

        Args:
            step: The step dictionary that failed.
            error: Error message or description.
            screen_path: Path to screenshot at time of failure.

        Returns:
            Dictionary with ``failure_type``, ``confidence``,
            and ``suggested_fix``.
        """
        try:
            # Ask llava to analyze the screen at failure time
            screen_analysis = ""
            if screen_path:
                screen_analysis = self.ollama.analyze_screen(
                    screen_path,
                    "Describe what is visible on this screen. "
                    "Note any error messages, popups, or unusual states.",
                )

            # Ask llama3 to diagnose
            prompt = (
                f"A computer automation step failed.\n\n"
                f"Step: {step}\n"
                f"Error: {error}\n"
                f"Screen state: {screen_analysis}\n\n"
                f"Classify the failure into one of these types:\n"
                f"- element_not_found: The UI element couldn't be located\n"
                f"- wrong_timing: Action was too fast/slow\n"
                f"- app_crashed: Application crashed or became unresponsive\n"
                f"- unexpected_popup: A popup/dialog blocked the action\n"
                f"- permission_denied: Insufficient permissions\n"
                f"- network_error: Network/connectivity issue\n"
                f"- unknown: Cannot determine\n\n"
                f"Respond in JSON:\n"
                f'{{"failure_type": "...", "confidence": 0.0-1.0, '
                f'"suggested_fix": "..."}}'
            )

            result = self.ollama.generate_json(prompt)

            # Validate failure_type
            ft = result.get("failure_type", "unknown")
            if ft not in FAILURE_TYPES:
                result["failure_type"] = "unknown"

            # Clamp confidence
            conf = result.get("confidence", 0.5)
            result["confidence"] = max(0.0, min(1.0, float(conf)))

            return result

        except Exception as exc:
            logger.error("Diagnosis failed: %s", exc)
            return {
                "failure_type": "unknown",
                "confidence": 0.0,
                "suggested_fix": f"Diagnosis error: {exc}",
            }

    # ------------------------------------------------------------------
    # Healing
    # ------------------------------------------------------------------

    def heal(
        self,
        failed_step: dict,
        error: str,
        attempt: int = 1,
    ) -> bool:
        """Attempt to heal a failure and retry the step.

        Args:
            failed_step: The step dictionary that failed.
            error: Error message or description.
            attempt: Current healing attempt number (max 3).

        Returns:
            True if healing succeeded, False if it failed.
        """
        import pyautogui

        if attempt > 3:
            logger.warning("Max healing attempts (3) reached. Giving up.")
            self._log_attempt(failed_step, error, "max_attempts", False)
            return False

        logger.info(
            "Healing attempt %d/3 for step: %s",
            attempt,
            str(failed_step)[:100],
        )

        # Take current screenshot
        screen_path = self.vision.screen_capture.capture_primary()

        # Diagnose the failure
        diagnosis = self.diagnose_failure(failed_step, error, screen_path)
        failure_type = diagnosis.get("failure_type", "unknown")
        suggested_fix = diagnosis.get("suggested_fix", "")

        logger.info(
            "Diagnosis: %s (confidence: %.2f) — %s",
            failure_type,
            diagnosis.get("confidence", 0),
            suggested_fix,
        )

        healed = False

        try:
            if failure_type == "element_not_found":
                healed = self._heal_element_not_found(failed_step)

            elif failure_type == "wrong_timing":
                healed = self._heal_wrong_timing(failed_step)

            elif failure_type == "app_crashed":
                healed = self._heal_app_crashed(failed_step)

            elif failure_type == "unexpected_popup":
                healed = self._heal_unexpected_popup(screen_path)

            elif failure_type == "permission_denied":
                logger.warning(
                    "Permission denied — requires human intervention."
                )
                healed = False

            elif failure_type == "network_error":
                logger.info("Waiting 5s for network recovery...")
                time.sleep(5)
                healed = True  # Retry the step

            else:
                logger.warning("Unknown failure type. Retrying after delay.")
                # Use exponential backoff for unknown failures
                delay = 1.0 * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                time.sleep(delay)
                healed = self.heal(failed_step, error, attempt + 1)

        except Exception as exc:
            logger.error("Healing action failed: %s", exc)
            healed = False

        self._log_attempt(failed_step, error, failure_type, healed)

        if not healed and attempt < 3:
            return self.heal(failed_step, error, attempt + 1)

        return healed

    # ------------------------------------------------------------------
    # Healing Strategies
    # ------------------------------------------------------------------

    def _heal_element_not_found(self, step: dict) -> bool:
        """Try to find the element by scrolling and re-searching."""
        import pyautogui

        target = step.get("target", step.get("description", ""))
        logger.info("Healing element_not_found: scrolling to find '%s'", target)

        # Try scrolling down
        pyautogui.scroll(-5)
        time.sleep(1)

        # Try to find element with vision
        location = self.vision.find_element(target)
        if location:
            logger.info("Element found after scrolling at %s", location)
            return True

        # Try scrolling up
        pyautogui.scroll(10)
        time.sleep(1)

        location = self.vision.find_element(target)
        if location:
            logger.info("Element found after scrolling up at %s", location)
            return True

        return False

    def _heal_wrong_timing(self, step: dict) -> bool:
        """Wait and retry for timing issues with adaptive backoff.
        
        Timing issues often indicate race conditions where operations
        are happening too fast. Use adaptive delay with jitter.
        """
        # Adaptive delay: 1.0s + random jitter (0-1.0s)
        delay = 1.0 + random.uniform(0, 1.0)
        logger.info("Healing wrong_timing: waiting %.2f seconds before retry.", delay)
        time.sleep(delay)
        return True  # Signal to retry the step

    def _heal_app_crashed(self, step: dict) -> bool:
        """Attempt to detect and reopen a crashed application."""
        import pyautogui

        logger.info("Healing app_crashed: analyzing screen...")

        screen_path = self.vision.screen_capture.capture_primary()

        # Ask llava what happened
        analysis = self.ollama.analyze_screen(
            screen_path,
            "Has an application crashed? What application was it? "
            "Is there a crash dialog visible?",
        )

        # Try pressing Escape to dismiss crash dialogs
        pyautogui.press("escape")
        time.sleep(1)

        # Ask LLM what app to reopen
        app_prompt = (
            f"An application crashed. Screen analysis: {analysis}\n"
            f"Original step was: {step}\n"
            f"What application should be reopened? "
            f"Respond with just the application name."
        )
        app_name = self.ollama.generate(app_prompt).strip()

        if app_name:
            logger.info("Attempting to reopen: %s", app_name)
            # Try to open via Windows search
            pyautogui.hotkey("win", "s")
            time.sleep(1)
            pyautogui.typewrite(app_name, interval=0.05)
            time.sleep(1)
            pyautogui.press("enter")
            time.sleep(3)
            return True

        return False

    def _heal_unexpected_popup(self, screen_path: str) -> bool:
        """Dismiss an unexpected popup."""
        import pyautogui

        logger.info("Healing unexpected_popup: analyzing popup...")

        # Ask llava what the popup is
        popup_info = self.ollama.analyze_screen(
            screen_path,
            "There is a popup or dialog on screen. "
            "What does it say? What button should I click to dismiss it?",
        )

        logger.info("Popup analysis: %s", popup_info[:200])

        # Try pressing Escape first
        pyautogui.press("escape")
        time.sleep(1)

        # Check if popup is gone
        new_screen = self.vision.screen_capture.capture_primary()
        if self.vision.has_screen_changed(screen_path, new_screen):
            logger.info("Popup dismissed with Escape.")
            return True

        # Try clicking common dismiss buttons
        for button_text in ["OK", "Close", "Cancel", "Dismiss", "No"]:
            location = self.vision.find_element(button_text)
            if location:
                pyautogui.click(location[0], location[1])
                time.sleep(1)
                logger.info("Clicked '%s' to dismiss popup.", button_text)
                return True

        # Try Alt+F4 as last resort
        pyautogui.hotkey("alt", "F4")
        time.sleep(1)
        return True

    # ------------------------------------------------------------------
    # Logging & Stats
    # ------------------------------------------------------------------

    def _log_attempt(
        self,
        step: dict,
        error: str,
        failure_type: str,
        success: bool,
    ) -> None:
        """Log a healing attempt."""
        self.healing_log.append(
            {
                "step": str(step)[:200],
                "error": error[:200],
                "failure_type": failure_type,
                "success": success,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def get_healing_stats(self) -> dict:
        """Return statistics on healing attempts.

        Returns:
            Dictionary with attempt counts and common failure types.
        """
        total = len(self.healing_log)
        successes = sum(1 for e in self.healing_log if e["success"])
        failures = total - successes

        # Count failure types
        type_counts: Dict[str, int] = {}
        for entry in self.healing_log:
            ft = entry.get("failure_type", "unknown")
            type_counts[ft] = type_counts.get(ft, 0) + 1

        return {
            "total_attempts": total,
            "successful_heals": successes,
            "failed_heals": failures,
            "success_rate": (
                round(successes / total * 100, 1) if total > 0 else 0.0
            ),
            "failure_type_counts": type_counts,
        }
