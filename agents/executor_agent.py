"""
ExecutorAgent — Computer Control via pyautogui

Executes mouse clicks, keyboard input, scrolling, and app launching.
Pure action execution — no AI needed. Uses pyautogui for automation.
"""

import logging
import random
import sys
import time
from typing import Dict, Optional, Tuple, TYPE_CHECKING

import pyautogui

if TYPE_CHECKING:
    from utils.screen_capture import ScreenCapture
    from agents.vision_agent import VisionAgent

logger = logging.getLogger(__name__)

# Safety: pyautogui failsafe (move mouse to corner to abort)
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1  # Small default pause between actions


class ExecutorAgent:
    """Executes computer control actions — clicks, typing, keys, scrolling.

    Routes each step to the appropriate action handler based on
    ``action_type``. No AI is needed here — this is pure automation.
    """

    def __init__(
        self,
        screen_capture: "ScreenCapture",
        vision_agent: "VisionAgent",
    ) -> None:
        """Initialize ExecutorAgent.

        Args:
            screen_capture: Screen capture utility for before/after shots.
            vision_agent: Vision agent for finding elements when needed.
        """
        self.screen = screen_capture
        self.vision = vision_agent
        self.screen_width, self.screen_height = (
            self.screen.get_screen_resolution()
        )
        logger.info(
            "ExecutorAgent initialized. Screen: %dx%d",
            self.screen_width,
            self.screen_height,
        )

    # ------------------------------------------------------------------
    # Step Router
    # ------------------------------------------------------------------

    def execute_step(self, step: dict) -> dict:
        """Execute a single plan step.

        Routes to the correct action handler based on ``step["action_type"]``.

        Args:
            step: Step dictionary with action_type, target, value, etc.

        Returns:
            Result dictionary with success, action_performed, screenshot,
            and error (if any).
        """
        action_type = str(step.get("action_type", "") or "").lower().strip()
        target = str(step.get("target", "") or "")
        value = step.get("value")
        description = str(step.get("description", "") or "")

        logger.info(
            "Executing step: [%s] %s (target=%s, value=%s)",
            action_type,
            description[:60],
            target[:40],
            str(value)[:40] if value else "None",
        )

        result = {
            "success": False,
            "action_performed": "",
            "screenshot_after": "",
            "error": None,
        }

        try:
            if action_type == "click":
                success = self._handle_click(target, description)
                result["action_performed"] = f"Clicked on '{target}'"

            elif action_type == "type":
                success = self.type_text(value or target)
                result["action_performed"] = f"Typed: '{(value or target)[:50]}'"

            elif action_type == "press":
                success = self.press_key(value or target)
                result["action_performed"] = f"Pressed key: '{value or target}'"

            elif action_type in ("open", "open_app"):
                success = self.open_app(target)
                result["action_performed"] = f"Opened: '{target}'"

            elif action_type == "scroll":
                direction = "down"
                if value and isinstance(value, str):
                    direction = value.lower()
                success = self.scroll(
                    self.screen_width // 2,
                    self.screen_height // 2,
                    direction,
                    5,
                )
                result["action_performed"] = f"Scrolled {direction}"

            elif action_type == "wait":
                wait_time = 2
                if value:
                    try:
                        wait_time = int(value)
                    except (ValueError, TypeError):
                        wait_time = 2
                time.sleep(wait_time)
                success = True
                result["action_performed"] = f"Waited {wait_time}s"

            else:
                # Try to interpret as a click with vision
                fallback_target = description or target or action_type
                success = self.find_and_click(fallback_target)
                result["action_performed"] = (
                    f"Vision-click on '{fallback_target}'"
                )

            result["success"] = success

        except Exception as exc:
            result["error"] = str(exc)
            logger.error("Step execution error: %s", exc)

        # Take after-screenshot
        try:
            result["screenshot_after"] = self.screen.capture_primary()
        except Exception:
            pass

        return result

    # ------------------------------------------------------------------
    # Mouse Actions
    # ------------------------------------------------------------------

    def click(self, x: int, y: int) -> bool:
        """Left-click at the specified coordinates.

        Args:
            x: X pixel coordinate.
            y: Y pixel coordinate.

        Returns:
            True if click was performed.
        """
        try:
            # Clamp to screen bounds
            x = max(0, min(x, self.screen_width - 1))
            y = max(0, min(y, self.screen_height - 1))

            pyautogui.moveTo(x, y, duration=0.3)
            time.sleep(random.uniform(0.05, 0.15))
            pyautogui.click(x, y)

            logger.info("Clicked at (%d, %d)", x, y)
            return True

        except Exception as exc:
            logger.error("Click failed at (%d, %d): %s", x, y, exc)
            return False

    def right_click(self, x: int, y: int) -> bool:
        """Right-click at the specified coordinates.

        Args:
            x: X pixel coordinate.
            y: Y pixel coordinate.

        Returns:
            True if click was performed.
        """
        try:
            x = max(0, min(x, self.screen_width - 1))
            y = max(0, min(y, self.screen_height - 1))

            pyautogui.moveTo(x, y, duration=0.3)
            time.sleep(random.uniform(0.05, 0.15))
            pyautogui.rightClick(x, y)

            logger.info("Right-clicked at (%d, %d)", x, y)
            return True

        except Exception as exc:
            logger.error("Right-click failed: %s", exc)
            return False

    def double_click(self, x: int, y: int) -> bool:
        """Double-click at the specified coordinates.

        Args:
            x: X pixel coordinate.
            y: Y pixel coordinate.

        Returns:
            True if click was performed.
        """
        try:
            x = max(0, min(x, self.screen_width - 1))
            y = max(0, min(y, self.screen_height - 1))

            pyautogui.moveTo(x, y, duration=0.3)
            time.sleep(random.uniform(0.05, 0.15))
            pyautogui.doubleClick(x, y)

            logger.info("Double-clicked at (%d, %d)", x, y)
            return True

        except Exception as exc:
            logger.error("Double-click failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Keyboard Actions
    # ------------------------------------------------------------------

    def type_text(self, text: str) -> bool:
        if not text:
            return False
        try:
            time.sleep(0.5)
            pyautogui.write(text, interval=0.05)
            logger.info("Typed: '%s'", text[:50])
            return True
        except Exception as e:
            logger.error("Failed to type text: %s", e)
            return False

    def press_key(self, key: str) -> bool:
        """Press a keyboard key or key combination.

        Supports single keys (enter, tab, escape) and combinations
        (ctrl+c, alt+f4, ctrl+shift+s).

        Args:
            key: Key name or combination (e.g. 'enter', 'ctrl+c').

        Returns:
            True if key press was performed.
        """
        if not key:
            return False

        try:
            key = key.strip().lower()

            if "+" in key:
                # Key combination
                keys = [k.strip() for k in key.split("+")]
                pyautogui.hotkey(*keys)
                logger.info("Pressed hotkey: %s", key)
            else:
                pyautogui.press(key)
                logger.info("Pressed key: %s", key)

            return True

        except Exception as exc:
            logger.error("Key press failed ('%s'): %s", key, exc)
            return False

    # ------------------------------------------------------------------
    # Scroll
    # ------------------------------------------------------------------

    def scroll(
        self,
        x: int,
        y: int,
        direction: str = "down",
        amount: int = 5,
    ) -> bool:
        """Scroll at the specified coordinates.

        Args:
            x: X pixel coordinate.
            y: Y pixel coordinate.
            direction: 'up' or 'down'.
            amount: Number of scroll clicks.

        Returns:
            True if scrolling was performed.
        """
        try:
            pyautogui.moveTo(x, y, duration=0.2)

            clicks = amount if direction == "up" else -amount
            pyautogui.scroll(clicks, x, y)

            logger.info("Scrolled %s by %d at (%d, %d)", direction, amount, x, y)
            return True

        except Exception as exc:
            logger.error("Scroll failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Application Control
    # ------------------------------------------------------------------

    def open_app(self, app_name: str) -> bool:
        """Open an application by name."""
        import subprocess

        app_commands = {
            "notepad": "notepad.exe",
            "chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "explorer": "explorer.exe",
            "calculator": "calc.exe",
            "paint": "mspaint.exe",
            "word": "winword.exe",
            "excel": "excel.exe",
            "vscode": "code",
            "terminal": "cmd.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
        }

        command = app_commands.get(app_name.lower(), app_name)

        try:
            subprocess.Popen(command)
            time.sleep(2)
            logger.info("Opened app via command: %s", command)
            return True
        except Exception:
            pass

        try:
            pyautogui.hotkey("win", "s")
            time.sleep(1)
            pyautogui.write(app_name, interval=0.05)
            time.sleep(1)
            pyautogui.press("enter")
            time.sleep(2)
            logger.info("Opened app via Windows search: %s", app_name)
            return True
        except Exception as e:
            logger.error("Failed to open %s: %s", app_name, e)
            return False

    # ------------------------------------------------------------------
    # Vision-Assisted Click
    # ------------------------------------------------------------------

    def find_and_click(self, description: str) -> bool:
        """Use the vision agent to find an element and click it.

        Args:
            description: Text description of what to click.

        Returns:
            True if the element was found and clicked.
        """
        try:
            location = self.vision.find_element(description)
            if location:
                return self.click(location[0], location[1])
            else:
                logger.warning(
                    "Could not find element: '%s'", description[:60]
                )
                return False

        except Exception as exc:
            logger.error("Find-and-click failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _handle_click(self, target: str, description: str) -> bool:
        """Handle a click action — try parsed coordinates, then vision.

        Args:
            target: Target description or coordinates.
            description: Step description for context.

        Returns:
            True if click succeeded.
        """
        # Try parsing coordinates from target
        coords = self._parse_coordinates(target)
        if coords:
            return self.click(coords[0], coords[1])

        # Fall back to vision-based finding
        return self.find_and_click(target or description)

    @staticmethod
    def _parse_coordinates(text: str) -> Optional[Tuple[int, int]]:
        """Try to extract (x, y) coordinates from text.

        Args:
            text: Text that might contain coordinates.

        Returns:
            Tuple of (x, y) or None.
        """
        import re

        # Match patterns like (100, 200), 100,200, x=100 y=200
        patterns = [
            r"\((\d+)\s*,\s*(\d+)\)",
            r"(\d+)\s*,\s*(\d+)",
            r"x\s*=?\s*(\d+)\s*y\s*=?\s*(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1)), int(match.group(2))

        return None
