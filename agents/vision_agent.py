"""
VisionAgent — Local Screen Analysis via Ollama llava

Analyzes screenshots, finds UI elements, detects popups and errors.
ALL vision processing goes through the local llava model via Ollama.
ZERO external APIs.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from utils.ollama_client import OllamaClient
    from utils.screen_capture import ScreenCapture

logger = logging.getLogger(__name__)


class VisionAgent:
    """AI-powered screen understanding using local llava model.

    Provides high-level screen analysis including:
    - Full screen description
    - UI element identification
    - Element location finding
    - Popup and error detection
    - Screen change detection

    All AI calls go through the local Ollama instance.
    """

    def __init__(
        self,
        ollama_client: "OllamaClient",
        screen_capture: "ScreenCapture",
    ) -> None:
        """Initialize VisionAgent.

        Args:
            ollama_client: Local Ollama client for vision inference.
            screen_capture: Screen capture utility.
        """
        self.ollama = ollama_client
        self.screen_capture = screen_capture
        logger.info(
            "VisionAgent initialized (local %s model).",
            ollama_client.vision_model,
        )

    # ------------------------------------------------------------------
    # Full Screen Analysis
    # ------------------------------------------------------------------

    def analyze_screen(self) -> dict:
        """Take a screenshot and analyze its contents.

        Returns:
            Dictionary with structured screen information including
            active app, visible elements, text, and description.
        """
        screenshot_path = self.screen_capture.capture_primary()
        if not screenshot_path:
            return self._empty_analysis("Screenshot capture failed")

        try:
            question = (
                "Describe this computer screen in detail. List:\n"
                "1. What application is currently open/active\n"
                "2. All visible buttons and their approximate positions\n"
                "3. All text visible on screen\n"
                "4. What the user can click or interact with\n"
                "5. Any popups, dialogs, or error messages visible\n\n"
                "Be specific and thorough."
            )

            description = self.ollama.analyze_screen(screenshot_path, question)

            # Parse into structured format using llama3
            parse_prompt = (
                f"Given this screen description, extract structured info.\n\n"
                f"Description: {description}\n\n"
                f"Respond in JSON:\n"
                f'{{"active_app": "app name or unknown",'
                f' "open_windows": ["window1", "window2"],'
                f' "clickable_elements": ['
                f'   {{"name": "element", "description": "what it does"}}'
                f' ],'
                f' "visible_text": ["text1", "text2"],'
                f' "has_popup": false,'
                f' "has_error": false}}'
            )

            parsed = self.ollama.generate_json(parse_prompt)

            return {
                "screenshot_path": screenshot_path,
                "active_app": parsed.get("active_app", "unknown"),
                "open_windows": parsed.get("open_windows", []),
                "clickable_elements": parsed.get("clickable_elements", []),
                "visible_text": parsed.get("visible_text", []),
                "screen_description": description,
                "has_popup": parsed.get("has_popup", False),
                "has_error": parsed.get("has_error", False),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as exc:
            logger.error("Screen analysis failed: %s", exc)
            return self._empty_analysis(str(exc))

    # ------------------------------------------------------------------
    # Element Finding
    # ------------------------------------------------------------------

    def find_element(self, description: str) -> Optional[Tuple[int, int]]:
        """Find a UI element on screen by description.

        Uses the local llava model to locate the element and returns
        its pixel coordinates.

        Args:
            description: Text description of the element to find
                         (e.g. "the Submit button", "search bar").

        Returns:
            Tuple of (x, y) pixel coordinates, or None if not found.
        """
        screenshot_path = self.screen_capture.capture_primary()
        if not screenshot_path:
            return None

        try:
            question = (
                f"I need to find: '{description}'\n\n"
                f"Look at this screenshot and tell me where this element is.\n"
                f"Give me the approximate position as a percentage of the "
                f"screen width and height.\n\n"
                f"Respond ONLY in JSON:\n"
                f'{{"found": true, "x_percent": 0.5, "y_percent": 0.3, '
                f'"confidence": 0.8}}\n\n'
                f"If you cannot find it, respond:\n"
                f'{{"found": false, "x_percent": 0, "y_percent": 0, '
                f'"confidence": 0}}'
            )

            result = self.ollama.analyze_screen(screenshot_path, question)

            # Try to parse as JSON
            import json

            # Clean up the response
            cleaned = result.strip()
            if "```" in cleaned:
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                # Try to extract JSON from the response
                start = cleaned.find("{")
                end = cleaned.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(cleaned[start:end])
                else:
                    logger.warning("Could not parse element location response.")
                    return None

            if not data.get("found", False):
                logger.info("Element '%s' not found on screen.", description)
                return None

            x_pct = float(data.get("x_percent", 0))
            y_pct = float(data.get("y_percent", 0))

            # Convert percentages to pixels
            screen_w, screen_h = self.screen_capture.get_screen_resolution()
            x = int(x_pct * screen_w)
            y = int(y_pct * screen_h)

            # Sanity check
            if 0 <= x <= screen_w and 0 <= y <= screen_h:
                logger.info(
                    "Found '%s' at (%d, %d) [%.1f%%, %.1f%%]",
                    description,
                    x,
                    y,
                    x_pct * 100,
                    y_pct * 100,
                )
                return (x, y)
            else:
                logger.warning(
                    "Element coordinates out of bounds: (%d, %d)", x, y
                )
                return None

        except Exception as exc:
            logger.error("Element finding failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Popup & Error Detection
    # ------------------------------------------------------------------

    def detect_popup(self) -> Optional[dict]:
        """Detect if a popup or dialog is visible on screen.

        Returns:
            Dictionary with popup information, or None if no popup found.
        """
        screenshot_path = self.screen_capture.capture_primary()
        if not screenshot_path:
            return None

        try:
            question = (
                "Is there any popup window, dialog box, alert, notification, "
                "or modal visible on this screen?\n\n"
                "If YES, respond in JSON:\n"
                '{"has_popup": true, "title": "popup title", '
                '"message": "popup message", "buttons": ["OK", "Cancel"]}\n\n'
                "If NO popup is visible, respond:\n"
                '{"has_popup": false}'
            )

            result = self.ollama.analyze_screen(screenshot_path, question)

            import json

            try:
                cleaned = result.strip()
                start = cleaned.find("{")
                end = cleaned.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(cleaned[start:end])
                else:
                    data = json.loads(cleaned)

                if data.get("has_popup", False):
                    data["screenshot_path"] = screenshot_path
                    return data
                return None

            except json.JSONDecodeError:
                # If response mentions a popup in free text
                lower = result.lower()
                if any(
                    w in lower
                    for w in ["popup", "dialog", "alert", "modal"]
                ):
                    return {
                        "has_popup": True,
                        "description": result,
                        "screenshot_path": screenshot_path,
                    }
                return None

        except Exception as exc:
            logger.error("Popup detection failed: %s", exc)
            return None

    def detect_error_dialog(self) -> Optional[dict]:
        """Detect if an error message or error dialog is visible.

        Returns:
            Dictionary with error information, or None if no error found.
        """
        screenshot_path = self.screen_capture.capture_primary()
        if not screenshot_path:
            return None

        try:
            question = (
                "Is there any error message, error dialog, crash notification, "
                "or warning visible on this screen?\n\n"
                "If YES, respond in JSON:\n"
                '{"has_error": true, "error_text": "the error message", '
                '"severity": "critical|warning|info"}\n\n'
                "If NO error is visible, respond:\n"
                '{"has_error": false}'
            )

            result = self.ollama.analyze_screen(screenshot_path, question)

            import json

            try:
                cleaned = result.strip()
                start = cleaned.find("{")
                end = cleaned.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(cleaned[start:end])
                else:
                    data = json.loads(cleaned)

                if data.get("has_error", False):
                    data["screenshot_path"] = screenshot_path
                    return data
                return None

            except json.JSONDecodeError:
                lower = result.lower()
                if any(w in lower for w in ["error", "crash", "failed"]):
                    return {
                        "has_error": True,
                        "description": result,
                        "screenshot_path": screenshot_path,
                    }
                return None

        except Exception as exc:
            logger.error("Error detection failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Screen Change Detection
    # ------------------------------------------------------------------

    def has_screen_changed(
        self,
        before_path: str,
        after_path: str,
        threshold: float = 0.05,
    ) -> bool:
        """Compare two screenshots to detect significant change.

        Uses structural similarity (SSIM-like) comparison via OpenCV.

        Args:
            before_path: Path to the before screenshot.
            after_path: Path to the after screenshot.
            threshold: Minimum difference percentage to count as changed.

        Returns:
            True if the screen changed significantly.
        """
        try:
            before = cv2.imread(before_path, cv2.IMREAD_GRAYSCALE)
            after = cv2.imread(after_path, cv2.IMREAD_GRAYSCALE)

            if before is None or after is None:
                logger.warning("Could not read screenshots for comparison.")
                return True  # Assume changed if we can't compare

            # Resize to same dimensions if needed
            if before.shape != after.shape:
                after = cv2.resize(
                    after, (before.shape[1], before.shape[0])
                )

            # Compute absolute difference
            diff = cv2.absdiff(before, after)
            non_zero = np.count_nonzero(diff > 30)  # Ignore minor noise
            total_pixels = diff.shape[0] * diff.shape[1]
            change_pct = non_zero / total_pixels

            changed = change_pct > threshold
            logger.info(
                "Screen change: %.2f%% (threshold: %.2f%%) → %s",
                change_pct * 100,
                threshold * 100,
                "CHANGED" if changed else "SAME",
            )
            return changed

        except Exception as exc:
            logger.error("Screen comparison failed: %s", exc)
            return True  # Assume changed on error

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_analysis(reason: str) -> dict:
        """Return an empty analysis result."""
        return {
            "screenshot_path": "",
            "active_app": "unknown",
            "open_windows": [],
            "clickable_elements": [],
            "visible_text": [],
            "screen_description": f"Analysis failed: {reason}",
            "has_popup": False,
            "has_error": False,
            "timestamp": datetime.now().isoformat(),
        }
