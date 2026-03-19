"""Vision-based app control using llava for universal fallback.

Uses screenshot + image analysis when direct control APIs are unavailable.
Slowest but most universally compatible method.
"""

import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class VisionController:
    """Universal fallback controller using vision AI."""

    def __init__(self, ollama_client):
        self.ollama = ollama_client
        self.input = None

    def perform_action(
        self, action: str, target: str = None, value: str = None
    ) -> dict:
        """Perform action by analyzing screen and clicking/typing."""
        from app_control.input_controller import InputController

        if not self.input:
            self.input = InputController()

        import mss
        from PIL import Image

        # Take screenshot
        os.makedirs("data/screenshots", exist_ok=True)
        screenshot_path = (
            f"data/screenshots/"
            f"vision_{datetime.now().strftime('%H%M%S%f')}"
            f".png"
        )

        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                img = sct.grab(monitor)
                Image.frombytes(
                    "RGB", img.size, img.bgra, "raw", "BGRX"
                ).save(screenshot_path)
        except Exception as exc:
            logger.error(f"Screenshot failed: {exc}")
            return {"success": False, "reason": "Screenshot failed"}

        # Ask llava where the element is
        if target and action in ["click", "type"]:
            try:
                coords = self.ollama.analyze_screen(
                    screenshot_path,
                    (
                        f"Find '{target}' on screen. "
                        f"Reply ONLY in JSON: "
                        f"{{x_percent: 0.5, y_percent: 0.5, "
                        f"found: true}}"
                    ),
                )

                data = self.ollama.extract_json(coords)
                if data.get("found"):
                    import pyautogui

                    w, h = pyautogui.size()
                    x = int(data["x_percent"] * w)
                    y = int(data["y_percent"] * h)

                    if action == "click":
                        self.input.click(x, y)
                        return {"success": True, "method": "vision"}

                    elif action == "type":
                        self.input.click(x, y)
                        import time

                        time.sleep(0.2)
                        self.input.type_text(value or "")
                        return {"success": True, "method": "vision"}

            except Exception as exc:
                logger.error(f"Vision action failed: {exc}")

        return {"success": False, "reason": "Could not locate element"}
