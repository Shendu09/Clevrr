from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .audit_logger import AuditLogger
from .permissions import ActionCategory, PermissionEngine, PermissionResult
from .threat_detector import ThreatDetector, ThreatResult


@dataclass(slots=True)
class ExecutionResult:
    success: bool
    output: Optional[str]
    error: Optional[str]
    exit_code: Optional[int]
    perm_result: Optional[PermissionResult] = None
    threat_result: Optional[ThreatResult] = None


class ActionSandbox:
    def __init__(
        self,
        permission_engine: PermissionEngine,
        threat_detector: ThreatDetector,
        audit_logger: AuditLogger,
        dry_run: bool = False,
    ) -> None:
        self._perms = permission_engine
        self._detector = threat_detector
        self._audit = audit_logger
        self._dry_run = dry_run
        self._os_name = platform.system()

    def read_file(self, user_id: str, path: str) -> ExecutionResult:
        action = ActionCategory.FILE_READ
        command = lambda: Path(path).read_text(errors="replace")
        return self._execute(user_id=user_id, action=action, target=path, command=command)

    def write_file(self, user_id: str, path: str, content: str) -> ExecutionResult:
        action = ActionCategory.FILE_WRITE

        def _write() -> str:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            return f"Written {len(content)} bytes to {path}"

        return self._execute(
            user_id=user_id,
            action=action,
            target=path,
            command=_write,
            scan_text=content,
        )

    def delete_file(self, user_id: str, path: str) -> ExecutionResult:
        action = ActionCategory.FILE_DELETE
        command = lambda: os.remove(path) or f"Deleted {path}"
        return self._execute(user_id=user_id, action=action, target=path, command=command)

    def run_command(
        self,
        user_id: str,
        command: list[str],
        cwd: str | os.PathLike[str] | None = None,
        timeout: int = 30,
    ) -> ExecutionResult:
        cmd_str = " ".join(command)
        threat = self._detector.scan(cmd_str)
        if not threat.safe:
            self._audit.log(
                user_id,
                ActionCategory.PROCESS_SPAWN.value,
                False,
                f"Threat: {threat.threat_type}",
                cmd_str,
            )
            return ExecutionResult(
                success=False,
                output=None,
                error=self._detector.explain(threat),
                exit_code=-1,
                threat_result=threat,
            )

        def _run() -> tuple[str, int]:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
            )
            return result.stdout or result.stderr, result.returncode

        return self._execute(
            user_id=user_id,
            action=ActionCategory.PROCESS_SPAWN,
            target=cmd_str,
            command=_run,
            threat_result=threat,
        )

    def take_screenshot(self, user_id: str, out_path: str) -> ExecutionResult:
        action = ActionCategory.SCREENSHOT

        def _screenshot() -> str:
            try:
                import pyautogui

                image = pyautogui.screenshot()
                image.save(out_path)
                return f"Screenshot saved to {out_path}"
            except ImportError:
                return "pyautogui not installed"

        return self._execute(
            user_id=user_id,
            action=action,
            target=out_path,
            command=_screenshot,
        )

    def type_text(self, user_id: str, text: str) -> ExecutionResult:
        action = ActionCategory.KEYBOARD_INPUT

        def _type() -> str:
            try:
                import pyautogui

                pyautogui.typewrite(text, interval=0.05)
                return f"Typed {len(text)} characters"
            except ImportError:
                return "pyautogui not installed"

        return self._execute(
            user_id=user_id,
            action=action,
            target=None,
            command=_type,
            scan_text=text,
        )

    def _execute(
        self,
        user_id: str,
        action: ActionCategory,
        target: Optional[str],
        command: Callable[[], object],
        scan_text: Optional[str] = None,
        threat_result: Optional[ThreatResult] = None,
    ) -> ExecutionResult:
        if scan_text is not None and threat_result is None:
            threat_result = self._detector.scan(scan_text)
            if not threat_result.safe:
                self._audit.log(
                    user_id,
                    action.value,
                    False,
                    f"Threat: {threat_result.threat_type}",
                    target,
                )
                return ExecutionResult(
                    success=False,
                    output=None,
                    error=self._detector.explain(threat_result),
                    exit_code=-1,
                    threat_result=threat_result,
                )

        perm = self._perms.check(user_id, action, target)
        if not perm.allowed:
            self._audit.log(user_id, action.value, False, perm.reason, target)
            return ExecutionResult(
                success=False,
                output=None,
                error=f"Permission denied: {perm.reason}",
                exit_code=-1,
                perm_result=perm,
            )

        if self._dry_run:
            self._audit.log(user_id, action.value, True, "DRY RUN", target)
            return ExecutionResult(
                success=True,
                output="[DRY RUN] Would have executed.",
                error=None,
                exit_code=0,
                perm_result=perm,
            )

        try:
            raw = command()
            if isinstance(raw, tuple):
                output, exit_code = raw
            else:
                output, exit_code = str(raw), 0

            self._audit.log(user_id, action.value, True, "Executed successfully", target)
            return ExecutionResult(
                success=True,
                output=output,
                error=None,
                exit_code=exit_code,
                perm_result=perm,
                threat_result=threat_result,
            )
        except Exception as exc:
            self._audit.log(user_id, action.value, True, f"Execution error: {exc}", target)
            return ExecutionResult(
                success=False,
                output=None,
                error=str(exc),
                exit_code=-1,
                perm_result=perm,
            )