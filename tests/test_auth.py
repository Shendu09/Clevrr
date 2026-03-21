from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from actions.base_action import BaseAction
from core.auth.config import AuthConfig
from core.auth.consent_manager import ConsentManager
from core.auth.step_up_auth import StepUpAuth
from core.auth.token_vault import TokenVault


class DummyAction(BaseAction):
    @property
    def service_name(self) -> str:
        return "github"

    @property
    def required_scopes(self) -> list[str]:
        return ["repo"]

    def _execute(self, token: str, **kwargs) -> str:
        return f"ok:{token}"


def test_config_from_env_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH0_DOMAIN", "x.us.auth0.com")
    monkeypatch.setenv("AUTH0_CLIENT_ID", "id")
    monkeypatch.setenv("AUTH0_CLIENT_SECRET", "secret")
    monkeypatch.setenv("AUTH0_AUDIENCE", "aud")
    cfg = AuthConfig.from_env()
    assert cfg.domain == "x.us.auth0.com"


def test_config_missing_vars_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch("dotenv.load_dotenv", return_value=None):
        monkeypatch.delenv("AUTH0_DOMAIN", raising=False)
        monkeypatch.delenv("AUTH0_CLIENT_ID", raising=False)
        monkeypatch.delenv("AUTH0_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("AUTH0_AUDIENCE", raising=False)
        with pytest.raises(RuntimeError):
            AuthConfig.from_env()


def test_token_vault_no_network() -> None:
    cfg = AuthConfig("x", "id", "secret", "aud")
    vault = TokenVault(cfg)
    with patch("core.auth.token_vault.requests.post", side_effect=Exception("down")):
        token = vault.get_token("u1", "github")
    assert token is None


def test_step_up_not_required() -> None:
    step = StepUpAuth(AuthConfig(high_risk_actions=["delete_file"]))
    result = step.request("u1", "read_inbox")
    assert not result.required and result.approved


def test_step_up_required_approved() -> None:
    step = StepUpAuth(AuthConfig(high_risk_actions=["delete_file"]))
    with patch("builtins.input", return_value="yes"):
        result = step.request("u1", "delete_file")
    assert result.required and result.approved


def test_step_up_required_denied() -> None:
    step = StepUpAuth(AuthConfig(high_risk_actions=["delete_file"]))
    with patch("builtins.input", return_value="no"):
        result = step.request("u1", "delete_file")
    assert result.required and not result.approved


def test_consent_grant_and_check() -> None:
    mgr = ConsentManager()
    mgr.grant("u1", "github", ["repo"])
    assert mgr.has_consent("u1", "github")


def test_consent_revoke() -> None:
    mgr = ConsentManager()
    mgr.grant("u1", "github", ["repo"])
    assert mgr.revoke("u1", "github")
    assert not mgr.has_consent("u1", "github")


def test_consent_scope_check() -> None:
    mgr = ConsentManager()
    mgr.grant("u1", "github", ["repo"])
    assert mgr.has_consent("u1", "github", ["repo"])
    assert not mgr.has_consent("u1", "github", ["issues"])


def test_action_no_consent_fails() -> None:
    consent = ConsentManager()
    step_up = StepUpAuth(AuthConfig())
    vault = TokenVault(AuthConfig())
    action = DummyAction("u1", vault, step_up, consent)
    result = action.run("create_issue")
    assert not result.success
    assert "haven't connected" in (result.error or "")
