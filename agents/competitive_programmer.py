"""
CompetitiveProgrammer — local competitive coding assistant.

Pipeline:
1) Read coding question from screen via local vision model
2) Generate solution code via local text/code models
3) Verify against extracted sample tests locally
4) Auto-fix for failed tests (up to max attempts)
5) Save solution under data/solutions/
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from typing import Any, Dict, List

from app_control.input_controller import InputController


class CompetitiveProgrammer:
    """Competitive programming helper using local Ollama + local execution."""

    def __init__(self, ollama_client, screen_capture):
        self.ollama = ollama_client
        self.screen = screen_capture
        self.input = InputController()

    def read_question_from_screen(self) -> str:
        return self.read_full_question_with_scroll()

    def read_full_question_with_scroll(
        self,
        max_scrolls: int = 8,
        scroll_amount: int = 18,
    ) -> str:
        layout = self._detect_workspace_layout()
        question_pos = layout.get("question_pos")

        if question_pos:
            self.input.click(question_pos[0], question_pos[1])
            time.sleep(0.15)

        chunks: List[str] = []
        last_norm = ""

        for step in range(max_scrolls):
            screenshot = self.screen.capture_primary()
            chunk = self.ollama.analyze_screen(
                screenshot,
                """You are reading a competitive programming problem shown on screen.
Extract ONLY the currently visible problem content.

Include if visible:
1. Problem statement
2. Input format
3. Output format
4. Constraints
5. Example test cases (input/output)

Rules:
- Do not invent missing parts
- Do not summarize
- Return raw plain text from what is visible now""",
            ).strip()

            norm = self._normalize_text(chunk)
            if norm and norm != last_norm:
                chunks.append(chunk)
                last_norm = norm

            if step < max_scrolls - 1:
                if question_pos:
                    self.input.scroll(question_pos[0], question_pos[1], "down", scroll_amount)
                else:
                    self.input.press_key("pagedown")
                time.sleep(0.2)

        if not chunks:
            screenshot = self.screen.capture_primary()
            return self.ollama.analyze_screen(
                screenshot,
                """Read this coding problem completely.
Extract:
1. Problem statement
2. Input format
3. Output format
4. Constraints
5. All example test cases with inputs and expected outputs
Return everything as plain text.""",
            ).strip()

        merged = self.ollama.generate(
            prompt=(
                "Merge these OCR chunks from scrolling screenshots into one complete problem statement. "
                "Preserve exact details, examples, constraints, and formats. "
                "Remove duplicates and keep order.\n\n"
                + "\n\n--- CHUNK ---\n\n".join(chunks)
            ),
            system_prompt=(
                "You reconstruct competitive programming statements from partial scroll captures. "
                "Return plain text only. No markdown."
            ),
        )
        return merged.strip()

    def solve_question(
        self,
        question: str,
        language: str = "python",
        test_cases: list = None,
    ) -> str:
        examples = ""
        if test_cases:
            examples = "\n\nExample test cases:\n"
            for i, tc in enumerate(test_cases[:3]):
                examples += (
                    f"\nExample {i + 1}:\n"
                    f"Input: {tc.get('input', '')}\n"
                    f"Output: {tc.get('output', '')}\n"
                )

        prompt = f"""Solve this competitive programming problem.

Language: {language}

Problem:
{question}
{examples}

STRICT REQUIREMENTS:
1. Return ONLY the complete working code
2. No markdown backticks
3. No explanations whatsoever
4. Read input from stdin exactly as specified
5. Print output to stdout exactly as specified
6. Handle ALL edge cases
7. Use optimal algorithm — best time complexity
8. Handle multiple test cases if problem requires it

{"For Python: start with 'import sys' and use sys.stdin.readline for fast input" if language.lower() == "python" else ""}
{"For Java: class name must be Main with public static void main(String[] args)" if language.lower() == "java" else ""}
{"For C++: include all necessary headers like bits/stdc++.h" if language.lower() in ["cpp", "c++"] else ""}
"""

        solution = self.ollama.generate_code(
            prompt=prompt,
            system_prompt=(
                f"You are an elite {language} competitive programmer. "
                "You write optimal solutions that pass all test cases. "
                "Return ONLY raw code. Zero explanations."
            ),
        )

        return self._clean_code(solution, language)

    def solve_with_chain_of_thought(
        self,
        question: str,
        language: str = "python",
    ) -> str:
        """
        Two-step approach:
        Step 1 — Analyze problem with text model
        Step 2 — Write code with code model
        """
        analysis = self.ollama.generate(
            prompt=f"""
Analyze this competitive programming problem briefly:

{question}

Give me:
1. Problem type (dp/greedy/graph/math/string/etc)
2. Optimal algorithm to use
3. Key observations
4. Edge cases to handle
5. Time complexity of solution

Be concise — 5-10 lines maximum.
""",
            system_prompt=(
                "Expert algorithm analyst. "
                "Brief and precise analysis only."
            ),
        )

        solution = self.ollama.generate_code(
            prompt=f"""
Problem:
{question}

Algorithm analysis:
{analysis}

Based on this analysis write the complete
{language} solution.
Follow the algorithm exactly.
Return ONLY the raw code.
""",
            system_prompt=(
                f"Expert {language} coder. "
                "Implement the given algorithm precisely. "
                "Return only working code."
            ),
        )

        return self._clean_code(solution, language)

    def verify_solution(
        self,
        solution: str,
        test_cases: List[Dict[str, Any]],
        language: str = "python",
    ) -> dict:
        results: List[Dict[str, Any]] = []
        all_passed = True

        language = language.lower()
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                run_target = self._prepare_runtime_artifact(solution, language, temp_dir)
            except Exception as exc:
                return {
                    "all_passed": False,
                    "results": [
                        {
                            "test_case": 0,
                            "passed": False,
                            "reason": f"Compilation/runtime setup failed: {exc}",
                        }
                    ],
                    "passed_count": 0,
                    "total": len(test_cases),
                }

            for i, test in enumerate(test_cases):
                input_data = str(test.get("input", ""))
                expected = str(test.get("output", "")).strip()

                try:
                    cmd = self._run_command_for_language(run_target, language, temp_dir)
                    result = subprocess.run(
                        cmd,
                        input=input_data,
                        capture_output=True,
                        text=True,
                        timeout=5,
                        cwd=temp_dir,
                    )

                    actual = result.stdout.strip()
                    passed = actual == expected and result.returncode == 0
                    if not passed:
                        all_passed = False

                    results.append(
                        {
                            "test_case": i + 1,
                            "input": input_data,
                            "expected": expected,
                            "actual": actual,
                            "stderr": (result.stderr or "").strip(),
                            "passed": passed,
                        }
                    )

                except subprocess.TimeoutExpired:
                    all_passed = False
                    results.append(
                        {
                            "test_case": i + 1,
                            "input": input_data,
                            "expected": expected,
                            "passed": False,
                            "reason": "Time limit exceeded",
                        }
                    )
                except Exception as exc:
                    all_passed = False
                    results.append(
                        {
                            "test_case": i + 1,
                            "input": input_data,
                            "expected": expected,
                            "passed": False,
                            "reason": str(exc),
                        }
                    )

        return {
            "all_passed": all_passed,
            "results": results,
            "passed_count": sum(1 for item in results if item.get("passed")),
            "total": len(results),
        }

    def fix_solution(self, solution: str, failed_tests: List[dict], question: str, language: str = "python") -> str:
        failed_info = "\n".join(
            [
                (
                    f"Test {test['test_case']}:\n"
                    f"  Input: {test.get('input', '')}\n"
                    f"  Expected: {test.get('expected', '')}\n"
                    f"  Got: {test.get('actual', test.get('reason', ''))}"
                )
                for test in failed_tests
                if not test.get("passed")
            ]
        )

        fixed = self.ollama.generate(
            prompt=f"""
Fix this code. It fails these test cases:

{failed_info}

Original problem:
{question}

Current code:
{solution}

Language: {language}

Return ONLY the fixed code. Nothing else.
""",
            system_prompt="""You are an expert
programmer. Fix the code to pass all test cases.
Return ONLY the corrected code.""",
        )
        return fixed.strip()

    def solve_from_screen(
        self,
        language: str = "python",
        max_attempts: int = 3,
        write_in_editor: bool = True,
    ) -> dict:
        print("[CP Agent] Reading question from screen...")
        question = self.read_question_from_screen()
        print(f"[CP Agent] Question read: {question[:100]}...")

        test_cases = self._extract_test_cases(question)
        print(f"[CP Agent] Found {len(test_cases)} test cases")

        print(f"[CP Agent] Generating {language} solution...")
        solution = self.solve_with_chain_of_thought(question, language)

        solution2 = self.solve_question(question, language, test_cases)

        if test_cases:
            result1 = self.verify_solution(solution, test_cases, language)
            result2 = self.verify_solution(solution2, test_cases, language)

            if result2["passed_count"] > result1["passed_count"]:
                solution = solution2
                print(
                    "[CP Agent] Standard solution better: "
                    f"{result2['passed_count']} passed"
                )
            else:
                print(
                    "[CP Agent] CoT solution better: "
                    f"{result1['passed_count']} passed"
                )

        verification = {
            "all_passed": True,
            "results": [],
            "passed_count": 0,
            "total": 0,
        }

        for attempt in range(max_attempts):
            print(f"[CP Agent] Testing solution (attempt {attempt + 1})...")

            if test_cases:
                verification = self.verify_solution(solution, test_cases, language)
                print(
                    f"[CP Agent] Passed: "
                    f"{verification['passed_count']}/{verification['total']}"
                )

                if verification["all_passed"]:
                    print("[CP Agent] All test cases passed!")
                    break

                if attempt < max_attempts - 1:
                    print("[CP Agent] Fixing solution...")
                    failed = [item for item in verification["results"] if not item.get("passed")]
                    solution = self.fix_solution(solution, failed, question, language)
            else:
                break

        saved_path = self._save_solution(solution, language)
        write_result = {
            "attempted": False,
            "success": False,
            "reason": "Skipped",
        }

        if write_in_editor:
            write_result = self.write_solution_to_editor(solution)

        return {
            "question": question,
            "solution": solution,
            "language": language,
            "verification": verification,
            "success": bool(verification.get("all_passed", True)),
            "saved_path": saved_path,
            "test_cases_found": len(test_cases),
            "editor_write": write_result,
        }

    def write_solution_to_editor(self, solution: str) -> dict:
        layout = self._detect_workspace_layout()
        editor_pos = layout.get("editor_pos")

        if editor_pos:
            self.input.click(editor_pos[0], editor_pos[1])
            time.sleep(0.1)

        self.input.press_key("ctrl+a")
        ok = self.input.type_text(solution)

        if ok:
            return {
                "attempted": True,
                "success": True,
                "clicked": bool(editor_pos),
                "editor_pos": editor_pos,
            }

        return {
            "attempted": True,
            "success": False,
            "clicked": bool(editor_pos),
            "editor_pos": editor_pos,
            "reason": "Could not type/paste in editor",
        }

    def _clean_code(self, solution: str, language: str = "python") -> str:
        cleaned = (solution or "").strip()

        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z0-9_+\-]*\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned).strip()

        return cleaned

    def _extract_test_cases(self, question: str) -> List[dict]:
        response = self.ollama.generate_json(
            prompt=f"""
Extract ALL example test cases from this problem.

Problem:
{question}

Return JSON array:
[
  {{
    "input": "exact input here",
    "output": "exact expected output here"
  }}
]

If no test cases found return: []
""",
            system_prompt="Return only valid JSON array.",
        )

        if isinstance(response, list):
            return [item for item in response if isinstance(item, dict)]

        if isinstance(response, dict) and isinstance(response.get("test_cases"), list):
            return [item for item in response["test_cases"] if isinstance(item, dict)]

        return []

    def _save_solution(self, solution: str, language: str) -> str:
        ext_map = {
            "python": "py",
            "java": "java",
            "cpp": "cpp",
            "c": "c",
            "javascript": "js",
        }

        ext = ext_map.get(language.lower(), "txt")
        filename = f"solution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        output_dir = os.path.join("data", "solutions")
        os.makedirs(output_dir, exist_ok=True)

        path = os.path.join(output_dir, filename)
        with open(path, "w", encoding="utf-8") as file:
            file.write(solution)

        print(f"[CP Agent] Solution saved: {path}")
        return path

    def _run_command_for_language(self, source_path: str, language: str, temp_dir: str) -> List[str]:
        lang = language.lower()
        if lang == "python":
            return ["python", source_path]
        if lang == "java":
            return ["java", "-cp", temp_dir, "Main"]
        if lang == "cpp":
            return [source_path]
        return ["python", source_path]

    def _prepare_runtime_artifact(self, solution: str, language: str, temp_dir: str) -> str:
        lang = language.lower()
        if lang == "python":
            path = os.path.join(temp_dir, "solution.py")
            with open(path, "w", encoding="utf-8") as file:
                file.write(solution)
            return path

        if lang == "java":
            if shutil.which("javac") is None or shutil.which("java") is None:
                raise RuntimeError("Java runtime/compiler not found (javac/java)")

            java_path = os.path.join(temp_dir, "Main.java")
            with open(java_path, "w", encoding="utf-8") as file:
                file.write(solution)

            compile_result = subprocess.run(
                ["javac", java_path],
                capture_output=True,
                text=True,
                cwd=temp_dir,
                timeout=10,
            )
            if compile_result.returncode != 0:
                raise RuntimeError((compile_result.stderr or "Java compilation failed").strip())
            return java_path

        if lang == "cpp":
            if shutil.which("g++") is None:
                raise RuntimeError("C++ compiler not found (g++)")

            cpp_path = os.path.join(temp_dir, "main.cpp")
            exe_path = os.path.join(temp_dir, "main.exe")
            with open(cpp_path, "w", encoding="utf-8") as file:
                file.write(solution)

            compile_result = subprocess.run(
                ["g++", "-O2", "-std=c++17", cpp_path, "-o", exe_path],
                capture_output=True,
                text=True,
                cwd=temp_dir,
                timeout=15,
            )
            if compile_result.returncode != 0:
                raise RuntimeError((compile_result.stderr or "C++ compilation failed").strip())
            return exe_path

        path = os.path.join(temp_dir, "solution.py")
        with open(path, "w", encoding="utf-8") as file:
            file.write(solution)
        return path

    def _detect_workspace_layout(self) -> Dict[str, Any]:
        screenshot = self.screen.capture_primary()
        grid_path, coord_map = self.screen.add_coordinate_grid(screenshot, grid_size=6)

        response = self.ollama.analyze_screen(
            grid_path,
            """Identify two regions in this coding workspace:
1) The problem/question pane
2) The code editor/compiler pane

Return strict JSON only:
{
  "question_cell": "A1",
  "editor_cell": "A2"
}

If uncertain, choose best guess cells.""",
        )

        parsed = self._safe_extract_json(response)
        question_cell = str(parsed.get("question_cell", "")).strip().upper()
        editor_cell = str(parsed.get("editor_cell", "")).strip().upper()

        return {
            "question_cell": question_cell,
            "editor_cell": editor_cell,
            "question_pos": coord_map.get(question_cell),
            "editor_pos": coord_map.get(editor_cell),
        }

    def _safe_extract_json(self, text: str) -> Dict[str, Any]:
        try:
            data = self.ollama.extract_json(text)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

        matches = re.findall(r"[A-F][1-6]", text.upper())
        if len(matches) >= 2:
            return {"question_cell": matches[0], "editor_cell": matches[1]}
        if len(matches) == 1:
            return {"question_cell": matches[0], "editor_cell": matches[0]}
        return {}

    def _normalize_text(self, text: str) -> str:
        compact = " ".join((text or "").split())
        return compact[:1000]
