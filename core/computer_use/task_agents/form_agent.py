from __future__ import annotations

import time

try:
    import pyautogui

    pyautogui.FAILSAFE = True
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False

from ..screen_reader import ScreenReader


class FormAgent:
    def __init__(self, config, gateway, user_id: str) -> None:
        self._config = config
        self._gateway = gateway
        self._user_id = user_id
        self._reader = ScreenReader(config)

    def can_handle(self, goal: str) -> bool:
        keywords = ["fill form", "fill out", "complete form", "enter details"]
        return any(keyword in goal.lower() for keyword in keywords)

    def run(self, goal: str):
        from ..computer_use_loop import TaskResult

        started = time.monotonic()
        screen = self._reader.capture_and_understand("Identify form fields and labels")
        actions = ["Captured form", f"Detected fields: {screen.input_fields[:5]}"]
        if self._config.dry_run or not _HAS_PYAUTOGUI:
            return TaskResult(goal, True, 3, actions + ["Dry run only"], "Form plan prepared.", None, round(time.monotonic() - started, 1))
        for field in screen.input_fields[:5]:
            pyautogui.click()
            pyautogui.write(f"sample for {field}", interval=0.03)
            time.sleep(0.2)
        self._gateway.take_screenshot(self._user_id, "data/form_filled_preview.png")
        return TaskResult(goal, True, 5, actions + ["Filled fields", "Awaiting submit confirmation"], "Form filled; ready for user confirmation.", None, round(time.monotonic() - started, 1))
