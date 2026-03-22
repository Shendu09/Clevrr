from __future__ import annotations

from core.computer_use import (
    ActionPlanner,
    ActionType,
    ComputerUseConfig,
    PlannedAction,
    ScreenUnderstanding,
)
from core.computer_use.action_executor import ActionExecutor
from core.computer_use.agent_registry import AgentRegistry
from core.computer_use.screen_reader import ScreenReader
from core.computer_use.task_agents.browser_agent import BrowserAgent
from core.computer_use.task_agents.coding_agent import CodingAgent
from core.computer_use.task_agents.whatsapp_agent import WhatsAppAgent
from core.security import SecurityGateway


def test_config_defaults() -> None:
    cfg = ComputerUseConfig()
    assert cfg.max_steps == 10
    assert cfg.vision_model == "qwen2-vl"
    assert cfg.code_model == "codellama"


def test_action_type_enum() -> None:
    assert ActionType.CLICK.value == "click"
    assert ActionType.DONE.value == "done"


def test_planned_action_is_final() -> None:
    done = PlannedAction(ActionType.DONE, "", "", "ok", 1.0)
    click = PlannedAction(ActionType.CLICK, "btn", "", "go", 0.8)
    assert done.is_final is True
    assert click.is_final is False


def test_planner_no_ollama() -> None:
    cfg = ComputerUseConfig(ollama_host="http://127.0.0.1:65534")
    planner = ActionPlanner(cfg)
    screen = ScreenUnderstanding("", "browser", "", "", [], [], "", "", "", 0.0)
    action = planner.plan_next_action("search docs", screen, 1)
    assert action.action_type == ActionType.FAILED


def test_screen_reader_no_mss(monkeypatch) -> None:
    import core.computer_use.screen_reader as module

    monkeypatch.setattr(module, "_HAS_CAPTURE", False)
    reader = ScreenReader(ComputerUseConfig())
    out = reader.capture_and_understand("anything")
    assert out.active_app == "unknown"
    assert out.raw_description


def test_executor_dry_run(tmp_path) -> None:
    gateway = SecurityGateway(data_dir=tmp_path / "cu_data", dry_run=True)
    cfg = ComputerUseConfig(dry_run=True)
    executor = ActionExecutor(cfg, gateway)
    action = PlannedAction(ActionType.CLICK, "send", "", "click send", 0.9)
    result = executor.execute(action, 1)
    assert result.success is True
    assert "[DRY RUN]" in result.output


def test_whatsapp_can_handle(tmp_path) -> None:
    gateway = SecurityGateway(data_dir=tmp_path / "cu_data", dry_run=True)
    agent = WhatsAppAgent(ComputerUseConfig(dry_run=True), gateway, "u1")
    assert agent.can_handle("send whatsapp to John") is True
    assert agent.can_handle("create github issue") is False


def test_coding_can_handle(tmp_path) -> None:
    gateway = SecurityGateway(data_dir=tmp_path / "cu_data", dry_run=True)
    agent = CodingAgent(ComputerUseConfig(dry_run=True), gateway, "u1")
    assert agent.can_handle("solve leetcode problem") is True
    assert agent.can_handle("send email") is False


def test_browser_can_handle(tmp_path) -> None:
    gateway = SecurityGateway(data_dir=tmp_path / "cu_data", dry_run=True)
    agent = BrowserAgent(ComputerUseConfig(dry_run=True), gateway, "u1")
    assert agent.can_handle("summarize this page") is True


def test_registry_routing(tmp_path) -> None:
    gateway = SecurityGateway(data_dir=tmp_path / "cu_data", dry_run=True)
    registry = AgentRegistry(ComputerUseConfig(dry_run=True), gateway, "u1")
    assert isinstance(registry.get_agent("send whatsapp to boss"), WhatsAppAgent)
    assert registry.get_agent("unknown random task") is None
