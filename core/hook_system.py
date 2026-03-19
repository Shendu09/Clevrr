"""Event hooks inspired by ECC hooks/ with non-blocking dispatch."""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class HookEvent:
    PRE_TASK = "pre_task"
    POST_TASK = "post_task"
    PRE_APP_LAUNCH = "pre_app_launch"
    POST_APP_LAUNCH = "post_app_launch"
    PRE_VOICE_COMMAND = "pre_voice_command"
    POST_VOICE_COMMAND = "post_voice_command"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    SCREEN_CHANGE = "screen_change"
    ERROR_DETECTED = "error_detected"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"


class HookSystem:
    """Simple event bus with lightweight asynchronous execution."""

    def __init__(self):
        self.hooks = {}
        self._register_builtin_hooks()

    def register(self, event: str, handler, name: str = None):
        if event not in self.hooks:
            self.hooks[event] = []
        self.hooks[event].append(
            {
                "handler": handler,
                "name": name or getattr(handler, "__name__", "anonymous_hook"),
            }
        )

    def _run_hook(self, hook: dict, data: dict):
        try:
            return hook["handler"](data or {})
        except Exception as exc:
            logger.error("Hook error [%s]: %s", hook["name"], exc)
            return None

    def fire(self, event: str, data: dict = None) -> list:
        """Fire hooks asynchronously so main execution remains fast."""
        results = []
        if event not in self.hooks:
            return results

        payload = data or {}
        for hook in self.hooks[event]:
            thread = threading.Thread(
                target=self._run_hook,
                args=(hook, payload),
                daemon=True,
            )
            thread.start()
            results.append(
                {
                    "hook": hook["name"],
                    "result": "queued",
                }
            )
        return results

    def _register_builtin_hooks(self):
        def log_task_start(data):
            logging.getLogger("hooks").info("Task started: %s", data.get("task", ""))

        self.register(HookEvent.PRE_TASK, log_task_start, "log_task_start")

        def save_session_summary(data):
            summary = {
                "ended_at": datetime.now().isoformat(),
                "tasks_completed": data.get("task_count", 0),
                "success_rate": data.get("success_rate", 0),
            }
            try:
                os.makedirs("data", exist_ok=True)
                with open("data/session_summary.json", "w", encoding="utf-8") as file:
                    json.dump(summary, file)
            except Exception:
                pass

        self.register(
            HookEvent.SESSION_END,
            save_session_summary,
            "save_session_summary",
        )

        def extract_instinct_hook(data):
            return None

        self.register(
            HookEvent.TASK_COMPLETE,
            extract_instinct_hook,
            "extract_instinct",
        )

        def screenshot_on_error(data):
            try:
                import mss

                os.makedirs("data/screenshots", exist_ok=True)
                filename = (
                    f"data/screenshots/error_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    f".png"
                )
                with mss.mss() as sct:
                    sct.shot(output=filename)
            except Exception:
                pass

        self.register(
            HookEvent.ERROR_DETECTED,
            screenshot_on_error,
            "screenshot_on_error",
        )
