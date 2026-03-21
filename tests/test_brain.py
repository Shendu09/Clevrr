from __future__ import annotations

from core.auth.config import AuthConfig
from core.brain import BrainConfig, BrainEngine
from core.brain.intent_parser import IntentParser, ParsedIntent
from core.brain.memory import BrainMemory
from core.security import SecurityGateway


def test_brain_config_defaults() -> None:
    cfg = BrainConfig()
    assert cfg.ollama_model == "llama3"
    assert cfg.max_memory_turns == 10


def test_intent_parser_rule_based_email() -> None:
    parser = IntentParser(BrainConfig())
    result = parser._rule_based_parse("send email to john")
    assert result.intent == "send_email"
    assert result.service == "gmail"
    assert result.confidence >= 0.7


def test_intent_parser_rule_based_github() -> None:
    parser = IntentParser(BrainConfig())
    result = parser._rule_based_parse("create github issue")
    assert result.intent == "create_issue"


def test_intent_parser_rule_based_screenshot() -> None:
    parser = IntentParser(BrainConfig())
    result = parser._rule_based_parse("take a screenshot")
    assert result.intent == "take_screenshot"
    assert result.confidence >= 0.8


def test_intent_parser_unknown() -> None:
    parser = IntentParser(BrainConfig())
    result = parser._rule_based_parse("xyzzy unknown gibberish")
    assert result.intent == "unknown"
    assert result.confidence < 0.5


def test_intent_parser_no_ollama() -> None:
    parser = IntentParser(BrainConfig(ollama_host="http://127.0.0.1:65534"))
    result = parser.parse("send email to jane")
    assert isinstance(result, ParsedIntent)
    assert result.intent == "send_email"


def test_parsed_intent_confidence() -> None:
    parsed = ParsedIntent("send_email", "gmail", 0.8, {}, "ok")
    assert parsed.is_confident(0.7)
    assert not parsed.is_confident(0.9)


def test_memory_add_and_context() -> None:
    memory = BrainMemory(max_turns=10)
    memory.add("send email", "send_email", "Done", True)
    assert "send email" in memory.get_context()
    assert memory.size() == 1


def test_memory_max_turns() -> None:
    memory = BrainMemory(max_turns=10)
    for index in range(15):
        memory.add(f"cmd {index}", "unknown", "x", True)
    assert memory.size() == 10


def test_brain_engine_direct_command(tmp_path) -> None:
    gateway = SecurityGateway(data_dir=tmp_path / "brain_data", dry_run=True)
    engine = BrainEngine(BrainConfig(), AuthConfig(), gateway)
    response = engine.process_command("take a screenshot")
    assert isinstance(response, str)
    assert len(response) > 0
