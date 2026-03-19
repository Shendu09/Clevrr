"""Verification loop inspired by ECC verification-loop."""

from __future__ import annotations

import json
import os
from datetime import datetime


class VerificationLoop:
    """Per-step verification and recovery checkpoint storage."""

    def __init__(self, ollama_client, screen_capture, hook_system):
        self.ollama = ollama_client
        self.screen = screen_capture
        self.hooks = hook_system
        self.checkpoints = []

    def save_checkpoint(
        self,
        step_number: int,
        task: str,
        completed_steps: list,
        screenshot_path: str,
    ):
        checkpoint = {
            "step": step_number,
            "task": task,
            "completed_steps": completed_steps,
            "screenshot": screenshot_path,
            "timestamp": datetime.now().isoformat(),
        }
        self.checkpoints.append(checkpoint)

        os.makedirs("data", exist_ok=True)
        with open("data/checkpoint.json", "w", encoding="utf-8") as file:
            json.dump(checkpoint, file)

    def verify_step(self, step: dict, before_screenshot: str, after_screenshot: str) -> dict:
        changed = self._screen_changed(before_screenshot, after_screenshot)
        if changed:
            try:
                from core.hook_system import HookEvent

                self.hooks.fire(HookEvent.SCREEN_CHANGE, {"step": step})
            except Exception:
                pass

        simple_actions = [
            "type",
            "type_text",
            "press_key",
            "hotkey",
            "wait",
            "scroll_up",
            "scroll_down",
            "select_all",
            "copy",
            "paste",
        ]

        if step.get("action_type") in simple_actions:
            return {
                "success": changed or step.get("action_type") == "wait",
                "method": "fast_check",
                "confidence": 0.9,
            }

        if changed:
            result = self.ollama.analyze_screen(
                after_screenshot,
                (
                    f"Did this action succeed: '{step.get('expected_outcome')}'? "
                    "Reply JSON: {success: bool, confidence: 0.0-1.0}"
                ),
            )
            try:
                parsed = self.ollama.extract_json(result)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                return {
                    "success": bool(parsed.get("success", changed)),
                    "method": "vision_check",
                    "confidence": float(parsed.get("confidence", 0.7)),
                }
            return {
                "success": changed,
                "method": "vision_check",
                "confidence": 0.7,
            }

        try:
            from core.hook_system import HookEvent

            self.hooks.fire(HookEvent.ERROR_DETECTED, {"step": step, "reason": "no_change"})
        except Exception:
            pass

        return {
            "success": False,
            "method": "no_change",
            "confidence": 0.8,
        }

    def _screen_changed(self, before: str, after: str) -> bool:
        try:
            import cv2
            import numpy as np

            img1 = cv2.imread(before)
            img2 = cv2.imread(after)

            if img1 is None or img2 is None:
                return True

            if img1.shape != img2.shape:
                img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))

            diff = cv2.absdiff(img1, img2)
            change = float(np.sum(diff) / max(diff.size, 1))
            return change > 5.0
        except Exception:
            return True

    def get_last_checkpoint(self) -> dict | None:
        if self.checkpoints:
            return self.checkpoints[-1]
        try:
            with open("data/checkpoint.json", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            return None
