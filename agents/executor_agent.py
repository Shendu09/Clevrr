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
        coords = self._parse_coordinates(target) or self._parse_coordinates(
            description
        )

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
                if coords:
                    success = self.click(coords[0], coords[1])
                else:
                    success = self.find_and_click(target or description)
                result["action_performed"] = f"Clicked on '{target or description}'"

            elif action_type == "right_click":
                if coords:
                    success = self.right_click(coords[0], coords[1])
                else:
                    success = self.find_and_click(target or description)
                result["action_performed"] = (
                    f"Right-clicked on '{target or description}'"
                )

            elif action_type == "double_click":
                if coords:
                    success = self.double_click(coords[0], coords[1])
                else:
                    success = self.find_and_click(target or description)
                result["action_performed"] = (
                    f"Double-clicked on '{target or description}'"
                )

            elif action_type in ("type", "type_text"):
                success = self.type_text(value or target)
                result["action_performed"] = f"Typed: '{(value or target)[:50]}'"

            elif action_type in ("press", "press_key"):
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

            elif action_type == "scroll_up":
                x, y = coords if coords else (
                    self.screen_width // 2,
                    self.screen_height // 2,
                )
                success = self.scroll(x, y, "up", 3)
                result["action_performed"] = "Scrolled up"

            elif action_type == "scroll_down":
                x, y = coords if coords else (
                    self.screen_width // 2,
                    self.screen_height // 2,
                )
                success = self.scroll(x, y, "down", 3)
                result["action_performed"] = "Scrolled down"

            elif action_type in ("close", "close_window"):
                success = self.press_key("alt+f4")
                result["action_performed"] = "Closed window"

            elif action_type == "save":
                success = self.press_key("ctrl+s")
                result["action_performed"] = "Saved"

            elif action_type == "save_and_close":
                save_success = self.press_key("ctrl+s")
                time.sleep(1)
                close_success = self.press_key("alt+f4")
                success = save_success and close_success
                result["action_performed"] = "Saved and closed"

            elif action_type == "minimize":
                success = self.press_key("win+down")
                result["action_performed"] = "Minimized window"

            elif action_type == "maximize":
                success = self.press_key("win+up")
                result["action_performed"] = "Maximized window"

            elif action_type == "screenshot":
                success = bool(self.take_screenshot())
                result["action_performed"] = "Captured screenshot"

            elif action_type == "hotkey":
                if isinstance(value, str) and value.strip():
                    keys = [k.strip() for k in value.split("+") if k.strip()]
                    pyautogui.hotkey(*keys)
                    success = True
                    result["action_performed"] = f"Pressed hotkey: {value}"
                else:
                    success = False
                    result["action_performed"] = "Invalid hotkey value"

            elif action_type == "find_and_click":
                success = self.find_and_click(target or description)
                result["action_performed"] = (
                    f"Vision-click on '{target or description}'"
                )

            elif action_type == "drag":
                drag_coords = self._parse_drag_coordinates(target, value)
                if drag_coords:
                    success = self.drag(*drag_coords)
                    result["action_performed"] = (
                        f"Dragged from ({drag_coords[0]}, {drag_coords[1]}) "
                        f"to ({drag_coords[2]}, {drag_coords[3]})"
                    )
                else:
                    success = False
                    result["action_performed"] = "Invalid drag coordinates"

            elif action_type == "select_all":
                success = self.press_key("ctrl+a")
                result["action_performed"] = "Selected all"

            elif action_type == "copy":
                success = self.press_key("ctrl+c")
                result["action_performed"] = "Copied"

            elif action_type == "paste":
                success = self.press_key("ctrl+v")
                result["action_performed"] = "Pasted"

            elif action_type == "undo":
                success = self.press_key("ctrl+z")
                result["action_performed"] = "Undo"

            elif action_type == "new_file":
                success = self.press_key("ctrl+n")
                result["action_performed"] = "Created new file"

            elif action_type == "wait":
                wait_time = int(step.get("value", 2))
                time.sleep(wait_time)
                success = True
                result["action_performed"] = f"Waited {wait_time}s"

            else:
                logger.warning(
                    "Unknown action_type: %s, attempting find_and_click",
                    action_type,
                )
                success = self.find_and_click(description)
                result["action_performed"] = (
                    f"Vision-click on '{description}'"
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
            # Dismiss any overlays (Windows Search, profile picker, etc.)
            pyautogui.press("escape")
            time.sleep(0.4)
            
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

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        """Drag mouse from start coordinates to end coordinates."""
        try:
            x1 = max(0, min(x1, self.screen_width - 1))
            y1 = max(0, min(y1, self.screen_height - 1))
            x2 = max(0, min(x2, self.screen_width - 1))
            y2 = max(0, min(y2, self.screen_height - 1))
            pyautogui.moveTo(x1, y1, duration=0.2)
            pyautogui.dragTo(x2, y2, duration=0.4, button="left")
            logger.info("Dragged from (%d, %d) to (%d, %d)", x1, y1, x2, y2)
            return True
        except Exception as exc:
            logger.error("Drag failed: %s", exc)
            return False

    def take_screenshot(self) -> str:
        """Capture and return screenshot path."""
        return self.screen.capture_primary()

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
            # Special handling for Chrome to bypass profile picker
            if app_name.lower() == "chrome":
                subprocess.Popen([
                    "chrome.exe",
                    "--profile-directory=Default",
                    "--no-first-run",
                    "--start-maximized"
                ])
                time.sleep(3)  # Give Chrome more time to load with profile
                logger.info("Opened Chrome with Default profile (no picker)")
                return True
            else:
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
            # Shortcut for Chrome address bar — skip vision and use keyboard
            desc_lower = description.lower()
            if any(term in desc_lower for term in ["address bar", "url bar", "omnibox"]):
                logger.info("Found address bar reference, using Ctrl+L shortcut")
                pyautogui.hotkey("ctrl", "l")
                time.sleep(0.5)
                return True
            
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
    def _parse_drag_coordinates(target: str, value: object) -> Optional[Tuple[int, int, int, int]]:
        """Extract drag coordinates from value dict/list/tuple/string or target string."""
        if isinstance(value, dict):
            x1 = value.get("x1")
            y1 = value.get("y1")
            x2 = value.get("x2")
            y2 = value.get("y2")
            if all(isinstance(v, (int, float)) for v in (x1, y1, x2, y2)):
                return int(x1), int(y1), int(x2), int(y2)

        if isinstance(value, (list, tuple)) and len(value) == 4:
            if all(isinstance(v, (int, float)) for v in value):
                return int(value[0]), int(value[1]), int(value[2]), int(value[3])

        text = value if isinstance(value, str) else target
        if not isinstance(text, str):
            return None

        import re

        match = re.search(
            r"(\d+)\s*,\s*(\d+)\s*(?:->|to)\s*(\d+)\s*,\s*(\d+)",
            text,
            re.IGNORECASE,
        )
        if match:
            return (
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
                int(match.group(4)),
            )

        return None

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
