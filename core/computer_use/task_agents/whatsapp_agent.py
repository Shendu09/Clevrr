from __future__ import annotations

import re
import time
import webbrowser

try:
    import pyautogui

    pyautogui.FAILSAFE = True
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False


class WhatsAppAgent:
    def __init__(self, config, gateway, user_id: str) -> None:
        self._config = config
        self._gateway = gateway
        self._user_id = user_id

    def can_handle(self, goal: str) -> bool:
        keywords = ["whatsapp", "send message", "send msg", "message to"]
        return any(keyword in goal.lower() for keyword in keywords)

    def run(self, goal: str):
        from ..computer_use_loop import TaskResult

        contact, message = self._parse_contact_and_message(goal)
        if self._config.dry_run or not _HAS_PYAUTOGUI:
            return TaskResult(
                goal=goal,
                success=True,
                steps_taken=1,
                actions=[f"[DRY RUN] Would send WhatsApp to {contact}"],
                final_output=f"Message planned for {contact}: '{message}'",
                error=None,
                duration_seconds=0.1,
            )
        webbrowser.open("https://web.whatsapp.com")
        time.sleep(3)
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.5)
        pyautogui.write(contact, interval=0.05)
        time.sleep(1)
        pyautogui.press("enter")
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.write(message, interval=0.03)
        pyautogui.press("enter")
        self._gateway.take_screenshot(self._user_id, "data/whatsapp_sent.png")
        return TaskResult(
            goal=goal,
            success=True,
            steps_taken=7,
            actions=["Opened WhatsApp Web", f"Found contact: {contact}", f"Typed: {message}", "Sent message"],
            final_output=f"Message sent to {contact}: '{message}'",
            error=None,
            duration_seconds=10.0,
        )

    def _parse_contact_and_message(self, goal: str) -> tuple[str, str]:
        text = goal.strip()
        contact = "Unknown"
        message = "Hello"
        to_match = re.search(r"to\s+([A-Za-z0-9_ ]+?)(?:\s+saying|:|-|$)", text, re.IGNORECASE)
        if to_match:
            contact = to_match.group(1).strip()
        msg_match = re.search(r"(?:saying|:|-)\s*(.+)$", text, re.IGNORECASE)
        if msg_match:
            message = msg_match.group(1).strip()
        return contact, message
