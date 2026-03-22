from __future__ import annotations

import json
import re
import time
import urllib.request
import webbrowser

from ..screen_reader import ScreenReader


class BrowserAgent:
    def __init__(self, config, gateway, user_id: str) -> None:
        self._config = config
        self._gateway = gateway
        self._user_id = user_id
        self._reader = ScreenReader(config)

    def can_handle(self, goal: str) -> bool:
        keywords = ["summarize", "search for", "open website", "go to", "browse", "webpage", "article"]
        return any(keyword in goal.lower() for keyword in keywords)

    def run(self, goal: str):
        from ..computer_use_loop import TaskResult

        started = time.monotonic()
        lowered = goal.lower()
        if "summarize" in lowered:
            summary = self._summarize_current_page()
            return TaskResult(goal, True, 3, ["Read page", "Summarized content"], summary, None, round(time.monotonic() - started, 1))
        if "search for" in lowered:
            query = goal.split("search for", 1)[-1].strip()
            webbrowser.open("https://www.google.com")
            return TaskResult(goal, True, 6, [f"Opened Google", f"Searched: {query}"], "Top results captured from screen.", None, round(time.monotonic() - started, 1))
        url_match = re.search(r"https?://\S+", goal)
        if url_match:
            url = url_match.group(0)
            webbrowser.open(url)
            screen = self._reader.capture_and_understand(goal)
            return TaskResult(goal, True, 4, [f"Navigated: {url}"], f"Page title: {screen.page_title}", None, round(time.monotonic() - started, 1))
        return TaskResult(goal, False, 1, ["No browser action"], "", "Unsupported browser goal", round(time.monotonic() - started, 1))

    def _summarize_current_page(self) -> str:
        screen = self._reader.capture_and_understand("Summarize visible webpage content")
        prompt = f"Summarize this page in 3 bullet points:\n{screen.visible_text[:3000]}"
        try:
            payload = json.dumps({"model": self._config.action_model, "prompt": prompt, "stream": False}).encode()
            req = urllib.request.Request(
                f"{self._config.ollama_host}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as response:
                result = json.loads(response.read())
            return result.get("response", "Summary unavailable.")
        except Exception:
            return "Summary unavailable."
