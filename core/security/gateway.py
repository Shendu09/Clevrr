from __future__ import annotations

from pathlib import Path
from typing import Optional

from .audit_logger import AuditLogger
from .permissions import ActionCategory, PermissionEngine, Role, User
from .sandbox import ActionSandbox, ExecutionResult
from .threat_detector import ThreatDetector, ThreatResult


class SecurityGateway:
    """Single security entry point that wires threat detection, RBAC, audit, and sandbox execution."""

    def __init__(
        self,
        data_dir: Path = Path("./clevrr_data"),
        dry_run: bool = False,
        custom_rules: Optional[dict] = None,
    ) -> None:
        data_dir = Path(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        self._perms = PermissionEngine(data_dir / "users.json")
        self._detector = ThreatDetector(custom_rules)
        self._audit = AuditLogger(data_dir / "audit.log")
        self._sandbox = ActionSandbox(
            permission_engine=self._perms,
            threat_detector=self._detector,
            audit_logger=self._audit,
            dry_run=dry_run,
        )

    def add_user(self, user: User) -> None: self._perms.add_user(user)
    def remove_user(self, user_id: str) -> None: self._perms.remove_user(user_id)
    def update_role(self, user_id: str, role: Role) -> None: self._perms.update_role(user_id, role)
    def deactivate_user(self, user_id: str) -> None: self._perms.deactivate_user(user_id)
    def get_user(self, user_id: str) -> User: return self._perms.get_user(user_id)
    def list_permissions(self, user_id: str) -> set[ActionCategory]: return self._perms.list_permissions(user_id)

    def read_file(self, user_id: str, path: str) -> ExecutionResult: return self._sandbox.read_file(user_id, path)
    def write_file(self, user_id: str, path: str, content: str) -> ExecutionResult: return self._sandbox.write_file(user_id, path, content)
    def delete_file(self, user_id: str, path: str) -> ExecutionResult: return self._sandbox.delete_file(user_id, path)
    def run_command(self, user_id: str, command: list[str], cwd: Optional[str] = None, timeout: int = 30) -> ExecutionResult: return self._sandbox.run_command(user_id, command, cwd=cwd, timeout=timeout)
    def take_screenshot(self, user_id: str, out_path: str) -> ExecutionResult: return self._sandbox.take_screenshot(user_id, out_path)
    def type_text(self, user_id: str, text: str) -> ExecutionResult: return self._sandbox.type_text(user_id, text)

    def verify_audit_chain(self) -> tuple[bool, str]: return self._audit.verify()
    def get_audit_log(self, user_id: Optional[str] = None, limit: int = 100) -> list: return self._audit.query(user_id=user_id, limit=limit)
    def export_audit(self, out_path: Path) -> None: self._audit.export_json(out_path)
    def scan_text(self, text: str) -> ThreatResult: return self._detector.scan(text)