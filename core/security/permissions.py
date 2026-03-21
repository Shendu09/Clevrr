from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path


class Role(str, Enum):
    ADMIN = "ADMIN"
    USER = "USER"
    RESTRICTED = "RESTRICTED"
    GUEST = "GUEST"


class ActionCategory(str, Enum):
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    PROCESS_SPAWN = "process_spawn"
    PROCESS_KILL = "process_kill"
    NETWORK_REQUEST = "network_request"
    SYSTEM_CONFIG = "system_config"
    CLIPBOARD = "clipboard"
    SCREENSHOT = "screenshot"
    KEYBOARD_INPUT = "keyboard_input"
    MOUSE_INPUT = "mouse_input"
    REGISTRY_READ = "registry_read"
    REGISTRY_WRITE = "registry_write"
    SERVICE_CONTROL = "service_control"
    PACKAGE_INSTALL = "package_install"
    SUDO_ESCALATE = "sudo_escalate"


ALL_ACTIONS: set[ActionCategory] = set(ActionCategory)

ROLE_PERMISSIONS: dict[Role, set[ActionCategory]] = {
    Role.ADMIN: ALL_ACTIONS,
    Role.USER: {
        ActionCategory.FILE_READ,
        ActionCategory.FILE_WRITE,
        ActionCategory.FILE_DELETE,
        ActionCategory.PROCESS_SPAWN,
        ActionCategory.NETWORK_REQUEST,
        ActionCategory.CLIPBOARD,
        ActionCategory.SCREENSHOT,
        ActionCategory.KEYBOARD_INPUT,
        ActionCategory.MOUSE_INPUT,
        ActionCategory.REGISTRY_READ,
    },
    Role.RESTRICTED: {
        ActionCategory.FILE_READ,
        ActionCategory.CLIPBOARD,
        ActionCategory.SCREENSHOT,
        ActionCategory.KEYBOARD_INPUT,
        ActionCategory.MOUSE_INPUT,
    },
    Role.GUEST: {
        ActionCategory.FILE_READ,
        ActionCategory.SCREENSHOT,
    },
}


@dataclass(slots=True)
class User:
    user_id: str
    username: str
    role: Role
    created_at: float
    active: bool = True
    allowed_paths: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PermissionResult:
    allowed: bool
    action: ActionCategory
    user_id: str
    role: Role
    reason: str
    timestamp: float


class PermissionEngine:
    def __init__(self, storage_path: Path) -> None:
        self._storage_path = Path(storage_path)
        self._users: dict[str, User] = {}
        self._lock = threading.RLock()
        self._load(self._storage_path)

    def add_user(self, user: User) -> None:
        with self._lock:
            self._users[user.user_id] = user
            self._persist()

    def remove_user(self, user_id: str) -> None:
        with self._lock:
            self._users.pop(user_id, None)
            self._persist()

    def update_role(self, user_id: str, new_role: Role) -> None:
        with self._lock:
            user = self._users.get(user_id)
            if user is None:
                raise KeyError(f"Unknown user: {user_id}")
            user.role = new_role
            self._persist()

    def deactivate_user(self, user_id: str) -> None:
        with self._lock:
            user = self._users.get(user_id)
            if user is None:
                raise KeyError(f"Unknown user: {user_id}")
            user.active = False
            self._persist()

    def get_user(self, user_id: str) -> User:
        with self._lock:
            user = self._users.get(user_id)
            if user is None:
                raise KeyError(f"Unknown user: {user_id}")
            return User(
                user_id=user.user_id,
                username=user.username,
                role=user.role,
                created_at=user.created_at,
                active=user.active,
                allowed_paths=list(user.allowed_paths),
            )

    def list_permissions(self, user_id: str) -> set[ActionCategory]:
        with self._lock:
            user = self._users.get(user_id)
            if user is None:
                raise KeyError(f"Unknown user: {user_id}")
            return set(ROLE_PERMISSIONS[user.role])

    def check(
        self,
        user_id: str,
        action: ActionCategory,
        target: str | os.PathLike[str] | None = None,
    ) -> PermissionResult:
        with self._lock:
            user = self._users.get(user_id)
            now = time.time()

            if user is None:
                return PermissionResult(
                    allowed=False,
                    action=action,
                    user_id=user_id,
                    role=Role.GUEST,
                    reason="Unknown user",
                    timestamp=now,
                )

            if not user.active:
                return PermissionResult(
                    allowed=False,
                    action=action,
                    user_id=user.user_id,
                    role=user.role,
                    reason="User deactivated",
                    timestamp=now,
                )

            if action not in ROLE_PERMISSIONS[user.role]:
                return PermissionResult(
                    allowed=False,
                    action=action,
                    user_id=user.user_id,
                    role=user.role,
                    reason=(
                        f"Role {user.role.value} does not permit {action.value}"
                    ),
                    timestamp=now,
                )

            if target is not None and user.allowed_paths:
                target_str = os.fspath(target)
                if not self._target_in_allowed_paths(target_str, user.allowed_paths):
                    return PermissionResult(
                        allowed=False,
                        action=action,
                        user_id=user.user_id,
                        role=user.role,
                        reason="Target path outside allowed paths",
                        timestamp=now,
                    )

            return PermissionResult(
                allowed=True,
                action=action,
                user_id=user.user_id,
                role=user.role,
                reason="Permitted",
                timestamp=now,
            )

    def _persist(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [self._serialize_user(user) for user in self._users.values()]

        temp_path = self._storage_path.with_suffix(self._storage_path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(temp_path, self._storage_path)

    def _load(self, path: Path) -> None:
        if not path.exists():
            return

        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        with self._lock:
            self._users.clear()
            for raw_user in data:
                user = User(
                    user_id=raw_user["user_id"],
                    username=raw_user["username"],
                    role=Role(raw_user["role"]),
                    created_at=float(raw_user["created_at"]),
                    active=bool(raw_user.get("active", True)),
                    allowed_paths=list(raw_user.get("allowed_paths", [])),
                )
                self._users[user.user_id] = user

    @staticmethod
    def _serialize_user(user: User) -> dict[str, object]:
        payload = asdict(user)
        payload["role"] = user.role.value
        return payload

    @staticmethod
    def _target_in_allowed_paths(target: str, allowed_paths: list[str]) -> bool:
        normalized_target = PermissionEngine._normalize_path(target)
        for allowed_path in allowed_paths:
            normalized_allowed = PermissionEngine._normalize_path(allowed_path)
            try:
                if os.path.commonpath([normalized_target, normalized_allowed]) == normalized_allowed:
                    return True
            except ValueError:
                continue
        return False

    @staticmethod
    def _normalize_path(path: str) -> str:
        expanded = os.path.expanduser(path)
        return os.path.normcase(os.path.abspath(os.path.normpath(expanded)))
