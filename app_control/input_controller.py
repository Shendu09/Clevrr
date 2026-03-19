"""Universal keyboard and mouse input controller.

Works on all platforms via pyautogui.
Primary method for accessing physical input.
"""

import logging

logger = logging.getLogger(__name__)


class InputController:
    """Cross-platform keyboard and mouse automation."""

    def __init__(self):
        import pyautogui

        pyautogui.PAUSE = 0
        pyautogui.FAILSAFE = True
        self.pag = pyautogui

    def click(self, x: int, y: int) -> bool:
        """Click at coordinates."""
        try:
            self.pag.moveTo(x, y, duration=0)
            self.pag.click()
            return True
        except Exception as exc:
            logger.error(f"Click failed: {exc}")
            return False

    def double_click(self, x: int, y: int) -> bool:
        """Double-click at coordinates."""
        try:
            self.pag.moveTo(x, y, duration=0)
            self.pag.doubleClick()
            return True
        except Exception as exc:
            logger.error(f"Double-click failed: {exc}")
            return False

    def right_click(self, x: int, y: int) -> bool:
        """Right-click at coordinates."""
        try:
            self.pag.moveTo(x, y, duration=0)
            self.pag.rightClick()
            return True
        except Exception as exc:
            logger.error(f"Right-click failed: {exc}")
            return False

    def type_text(self, text: str) -> bool:
        """Type text using clipboard paste for reliability."""
        try:
            import pyperclip
            import time

            pyperclip.copy(text)
            time.sleep(0.05)
            self.pag.hotkey("ctrl", "v")
            time.sleep(0.05)
            return True
        except Exception:
            try:
                self.pag.write(text, interval=0)
                return True
            except Exception as exc:
                logger.error(f"Type text failed: {exc}")
                return False

    def press_key(self, key: str) -> bool:
        """Press a single key or key combination."""
        try:
            if "+" in key:
                keys = key.split("+")
                self.pag.hotkey(*keys)
            else:
                self.pag.press(key)
            return True
        except Exception as exc:
            logger.error(f"Press key failed: {exc}")
            return False

    def scroll(
        self, x: int, y: int, direction: str, amount: int = 3
    ) -> bool:
        """Scroll at coordinates."""
        try:
            clicks = amount if direction == "up" else -amount
            self.pag.scroll(clicks, x=x, y=y)
            return True
        except Exception as exc:
            logger.error(f"Scroll failed: {exc}")
            return False

    def move_mouse(self, x: int, y: int, duration: float = 0.5) -> bool:
        """Move mouse smoothly to coordinates."""
        try:
            self.pag.moveTo(x, y, duration=duration)
            return True
        except Exception as exc:
            logger.error(f"Move mouse failed: {exc}")
            return False

    def get_mouse_position(self) -> tuple:
        """Get current mouse position."""
        try:
            return self.pag.position()
        except Exception:
            return (0, 0)

    def get_screen_size(self) -> tuple:
        """Get screen size."""
        try:
            return self.pag.size()
        except Exception:
            return (0, 0)
