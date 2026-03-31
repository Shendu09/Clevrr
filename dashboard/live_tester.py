from __future__ import annotations
import json, logging, threading, time, urllib.request, sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.brain.config import BrainConfig
from core.brain.intent_parser import IntentParser
from core.computer_use import AgentRegistry, ComputerUseConfig, ComputerUseLoop
from core.security import SecurityGateway
@dataclass(slots=True)
class LiveTestResult:
    feature: str
    success: bool
    output: str
    error: Optional[str]
    duration_ms: float
    timestamp: float = field(default_factory=time.time)
    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 1),
            "timestamp": self.timestamp,
        }
class LiveTester:
    def __init__(self, gateway: SecurityGateway, brain_config: BrainConfig, cu_config: ComputerUseConfig) -> None:
        self._gateway = gateway
        self._brain_config = brain_config
        self._cu_config = cu_config
        self._parser = IntentParser(brain_config)
        self._test_history: list[LiveTestResult] = []
        self._lock = threading.Lock()
        self.logger = logging.getLogger("clevrr.tester")
    def test_threat_detection(self, text: str) -> dict[str, Any]:
        start = time.monotonic()
        try:
            result = self._gateway.scan_text(text)
            ms = (time.monotonic() - start) * 1000
            output = f"SAFE — No threats detected in: '{text[:50]}'" if result.safe else f"BLOCKED [{result.level.value}] — Type: {result.threat_type} | Rule: {result.matched_rule}"
            self._gateway._audit.log("dashboard", "threat_scan", result.safe, f"Live test: {output[:80]}", text[:50])
            test = LiveTestResult("Threat Detection", True, output, None, ms)
            self._save(test)
            return test.to_dict()
        except Exception as exc:
            return self._error("Threat Detection", exc, start)
    def test_brain_parsing(self, command: str) -> dict[str, Any]:
        start = time.monotonic()
        try:
            intent = self._parser.parse(command)
            ms = (time.monotonic() - start) * 1000
            output = f"Intent: {intent.intent} | Service: {intent.service} | Confidence: {intent.confidence:.0%} | Params: {intent.parameters} | Response: {intent.response}"
            self._gateway._audit.log("dashboard", f"brain_test:{intent.intent}", intent.confidence > 0.5, f"Live brain test (conf={intent.confidence:.2f})", command[:50])
            test = LiveTestResult("AI Brain", True, output, None, ms)
            self._save(test)
            return {
                **test.to_dict(),
                "intent": intent.intent,
                "service": intent.service,
                "confidence": round(intent.confidence * 100),
                "parameters": intent.parameters,
                "response": intent.response,
                "ollama_used": intent.raw_text != "",
            }
        except Exception as exc:
            return self._error("AI Brain", exc, start)
    def test_audit_chain(self) -> dict[str, Any]:
        start = time.monotonic()
        try:
            entries_before = len(self._gateway._audit._entries)
            self._gateway._audit.log("dashboard", "chain_integrity_test", True, "Live test: verifying chain integrity", "dashboard")
            ok, message = self._gateway.verify_audit_chain()
            ms = (time.monotonic() - start) * 1000
            entries_after = len(self._gateway._audit._entries)
            output = f"{'INTACT' if ok else 'COMPROMISED'} — {message} | Entries verified: {entries_after} | New entry added and chain still valid: {ok}"
            test = LiveTestResult("Audit Chain", ok, output, None if ok else message, ms)
            self._save(test)
            return {**test.to_dict(), "intact": ok, "message": message, "entries_before": entries_before, "entries_after": entries_after}
        except Exception as exc:
            return self._error("Audit Chain", exc, start)
    def test_rbac(self, user_id: str, action: str) -> dict[str, Any]:
        start = time.monotonic()
        try:
            from core.security.permissions import ActionCategory
            try:
                action_cat = ActionCategory(action)
            except ValueError:
                action_cat = ActionCategory.FILE_READ
            result = self._gateway._perms.check(user_id, action_cat)
            ms = (time.monotonic() - start) * 1000
            output = f"{'ALLOWED' if result.allowed else 'DENIED'} — User: {user_id} | Action: {action} | Role: {result.role.value} | Reason: {result.reason}"
            self._gateway._audit.log("dashboard", f"rbac_test:{action}", result.allowed, f"Live RBAC test: {output[:80]}", user_id)
            test = LiveTestResult("RBAC", True, output, None, ms)
            self._save(test)
            return {**test.to_dict(), "allowed": result.allowed, "role": result.role.value, "reason": result.reason}
        except Exception as exc:
            return self._error("RBAC", exc, start)
    def test_voice(self, audio_text: str = "") -> dict[str, Any]:
        _ = audio_text
        start = time.monotonic()
        try:
            results: dict[str, str] = {}
            try:
                import sounddevice as sd
                devices = sd.query_devices()
                input_devices = [d for d in devices if d["max_input_channels"] > 0]
                results["sounddevice"] = f"OK — {len(input_devices)} input devices found"
            except ImportError:
                results["sounddevice"] = "NOT INSTALLED"
            except Exception as exc:
                results["sounddevice"] = f"ERROR: {exc}"
            try:
                from faster_whisper import WhisperModel
                _ = WhisperModel
                results["faster_whisper"] = "OK — installed"
            except ImportError:
                results["faster_whisper"] = "NOT INSTALLED"
            try:
                import openwakeword
                _ = openwakeword
                results["openwakeword"] = "OK — installed"
            except ImportError:
                results["openwakeword"] = "NOT INSTALLED"
            try:
                urllib.request.urlopen(self._brain_config.ollama_host, timeout=2)
                results["ollama"] = "OK — running"
            except Exception:
                results["ollama"] = "NOT RUNNING — start with: ollama serve"
            try:
                req = urllib.request.Request(f"{self._brain_config.ollama_host}/api/tags")
                with urllib.request.urlopen(req, timeout=3) as response:
                    data = json.loads(response.read())
                models = [model["name"] for model in data.get("models", [])]
                qwen = any("qwen" in model for model in models)
                llama = any("llama" in model for model in models)
                results["qwen2_vl"] = "OK — available" if qwen else "NOT PULLED — run: ollama pull qwen2-vl"
                results["llama3"] = "OK — available" if llama else "NOT PULLED — run: ollama pull llama3"
            except Exception as exc:
                results["qwen2_vl"] = f"Cannot check: {exc}"
            ms = (time.monotonic() - start) * 1000
            all_ok = all("OK" in value for value in results.values())
            output = " | ".join(f"{name}: {value}" for name, value in results.items())
            self._gateway._audit.log("dashboard", "system_check", all_ok, f"Live system check: {len(results)} components", "dashboard")
            test = LiveTestResult("Voice + Vision System", all_ok, output, None, ms)
            self._save(test)
            return {**test.to_dict(), "components": results, "all_ready": all_ok}
        except Exception as exc:
            return self._error("Voice System", exc, start)
    def test_agent(self, goal: str, dry_run: bool = True) -> dict[str, Any]:
        start = time.monotonic()
        try:
            config = ComputerUseConfig(dry_run=dry_run, max_steps=3)
            registry = AgentRegistry(config, self._gateway, "dashboard-test")
            specialist = registry.get_agent(goal)
            agent_name = specialist.__class__.__name__ if specialist else "GeneralLoop"
            if dry_run:
                output = f"DRY RUN — Agent: {agent_name} | Goal: '{goal}' | Would use: {agent_name} specialist | Steps planned: up to {config.max_steps}"
                ms = (time.monotonic() - start) * 1000
            else:
                loop = ComputerUseLoop(config, self._gateway, "dashboard-test")
                result = loop.run(goal, use_specialist=True)
                ms = (time.monotonic() - start) * 1000
                output = f"Agent: {agent_name} | {'SUCCESS' if result.success else 'FAILED'} | Steps: {result.steps_taken} | Output: {result.final_output[:100]}"
            self._gateway._audit.log("dashboard", f"agent_test:{agent_name}", True, f"Live agent test: {goal[:50]}", goal[:50])
            test = LiveTestResult(f"Computer Use Agent ({agent_name})", True, output, None, ms)
            self._save(test)
            return {**test.to_dict(), "agent": agent_name, "dry_run": dry_run, "goal": goal}
        except Exception as exc:
            return self._error("Computer Use Agent", exc, start)
    def test_all(self) -> list[dict[str, Any]]:
        return [
            self.test_threat_detection("rm -rf /home"),
            self.test_threat_detection("open chrome and search python"),
            self.test_brain_parsing("send email to my boss"),
            self.test_brain_parsing("take a screenshot"),
            self.test_audit_chain(),
            self.test_rbac("alice", "file_read"),
            self.test_rbac("carol", "file_write"),
            self.test_voice(),
            self.test_agent("solve this leetcode problem", dry_run=True),
        ]
    def get_history(self) -> list[dict[str, Any]]:
        with self._lock:
            return [test.to_dict() for test in self._test_history]
    def _save(self, test: LiveTestResult) -> None:
        with self._lock:
            self._test_history.append(test)
            if len(self._test_history) > 100:
                self._test_history = self._test_history[-100:]
    def _error(self, feature: str, exc: Exception, start: float) -> dict[str, Any]:
        ms = (time.monotonic() - start) * 1000
        msg = str(exc)
        self.logger.error(f"{feature} test failed: {msg}")
        test = LiveTestResult(feature=feature, success=False, output="", error=msg, duration_ms=ms)
        self._save(test)
        return test.to_dict()
