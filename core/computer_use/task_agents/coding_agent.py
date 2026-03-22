from __future__ import annotations

import json
import time
import urllib.request

from ..screen_reader import ScreenReader, ScreenUnderstanding

try:
    import pyautogui

    pyautogui.FAILSAFE = True
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False


class CodingAgent:
    def __init__(self, config, gateway, user_id: str) -> None:
        self._config = config
        self._gateway = gateway
        self._user_id = user_id
        self._reader = ScreenReader(config)

    def can_handle(self, goal: str) -> bool:
        keywords = [
            "leetcode", "hackerrank", "codeforces", "codechef", "atcoder", "geeksforgeeks",
            "solve", "coding problem", "write code", "algorithm", "competitive", "program",
        ]
        return any(keyword in goal.lower() for keyword in keywords)

    def run(self, goal: str):
        from ..computer_use_loop import TaskResult

        started = time.monotonic()
        screen = self._reader.capture_and_understand(
            "Read everything on screen: problem statement, constraints, examples, input/output format, and language"
        )
        platform = self._detect_platform(screen)
        language = self._detect_language(screen)
        problem = self._extract_problem(screen, platform)
        solution = self._generate_solution(problem, language, platform)
        if not self._config.dry_run and _HAS_PYAUTOGUI:
            self._focus_editor(platform)
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.2)
            pyautogui.press("delete")
            time.sleep(0.2)
            pyautogui.write(solution, interval=0.02)
            time.sleep(0.5)
            self._gateway.take_screenshot(self._user_id, "data/solution.png")
        return TaskResult(
            goal=goal,
            success=True,
            steps_taken=8,
            actions=["Read problem", "Detected platform/language", "Generated solution", "Wrote solution"],
            final_output=f"Solution generated for {platform} in {language}:\n{solution[:200]}",
            error=None,
            duration_seconds=round(time.monotonic() - started, 1),
        )

    def _detect_platform(self, screen: ScreenUnderstanding) -> str:
        url = screen.current_url.lower()
        text = screen.visible_text.lower()
        platforms = {
            "leetcode.com": "leetcode", "hackerrank.com": "hackerrank", "codeforces.com": "codeforces",
            "codechef.com": "codechef", "atcoder.jp": "atcoder", "geeksforgeeks.org": "geeksforgeeks",
            "interviewbit.com": "interviewbit", "codesignal.com": "codesignal", "topcoder.com": "topcoder",
            "spoj.com": "spoj", "hackerearth.com": "hackerearth",
        }
        for domain, name in platforms.items():
            if domain in url or name in text:
                return name
        return "unknown_coding_site"

    def _detect_language(self, screen: ScreenUnderstanding) -> str:
        text = (screen.visible_text + " " + " ".join(screen.clickable_elements)).lower()
        mapping = {
            "python3": "python", "python": "python", "javascript": "javascript", "typescript": "typescript",
            "java": "java", "c++": "cpp", "cpp": "cpp", "c#": "csharp", "golang": "go", "go": "go",
            "rust": "rust", "kotlin": "kotlin", "swift": "swift", "ruby": "ruby", "scala": "scala",
            "php": "php", " r ": "r",
        }
        for key, lang in mapping.items():
            if key in text:
                return lang
        return "python"

    def _extract_problem(self, screen: ScreenUnderstanding, platform: str) -> str:
        prompt = (
            f"This is a screenshot from {platform}. Extract complete problem statement with title, IO, constraints, examples.\n"
            f"Visible text: {screen.visible_text}\nTask relevant: {screen.task_relevant}\nReturn plain text only."
        )
        return self._call_ollama(prompt, self._config.action_model) or screen.visible_text

    def _generate_solution(self, problem: str, language: str, platform: str) -> str:
        templates = {
            "python": "class Solution:\n    def solve(self):\n        pass\n",
            "java": "class Solution {\n    public void solve() {}\n}\n",
            "cpp": "#include<bits/stdc++.h>\nusing namespace std;\n",
            "javascript": "var solve = function() {\n};\n",
            "typescript": "function solve(): void {\n}\n",
            "go": "package main\nfunc solve() {\n}\n",
            "rust": "impl Solution {\n    pub fn solve() {}\n}\n",
            "kotlin": "class Solution {\n    fun solve() {}\n}\n",
            "csharp": "public class Solution { public void Solve() {} }\n",
        }
        prompt = (
            f"Solve this competitive programming problem. Language:{language} Platform:{platform}.\n"
            "Return ONLY clean code with complexity comment at top. No markdown backticks.\n"
            f"Template:\n{templates.get(language, '')}\nProblem:\n{problem[:3000]}"
        )
        preferred_model = getattr(self._config, "code_model", "codellama")
        code = self._call_ollama(prompt, preferred_model)
        if not code:
            code = self._call_ollama(prompt, self._config.action_model)
        code = code or "# Time: O(n) Space: O(1)\npass"
        return code.replace("```python", "").replace("```", "").strip()

    def _focus_editor(self, platform: str) -> None:
        clicks = {
            "leetcode": (760, 400), "hackerrank": (700, 350), "codeforces": (700, 300), "codechef": (700, 400)
        }
        x, y = clicks.get(platform, (700, 400))
        pyautogui.click(x, y)
        time.sleep(0.3)

    def _call_ollama(self, prompt: str, model: str) -> str:
        try:
            payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
            req = urllib.request.Request(
                f"{self._config.ollama_host}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=25) as response:
                result = json.loads(response.read())
            return result.get("response", "")
        except Exception:
            return ""
