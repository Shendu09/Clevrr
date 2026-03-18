import os
import sys

import pytest

sys.path.append('.')


class TestOllamaClient:

    def setup_method(self):
        import yaml
        with open('config/settings.yaml') as f:
            self.config = yaml.safe_load(f)
        from utils.ollama_client import OllamaClient
        self.client = OllamaClient(self.config)

    def test_ollama_connection(self):
        assert self.client.is_running(), "Ollama is not running. Run: ollama serve"

    def test_basic_generation(self):
        response = self.client.generate("say hello")
        assert response is not None, "Basic generation returned None"
        assert len(response) > 0, "Basic generation returned empty response"

    def test_json_generation(self):
        response = self.client.generate_json(
            prompt="Return this exact JSON: {\"status\": \"ok\"}",
            system_prompt="Respond only in valid JSON."
        )
        assert isinstance(response, dict), "JSON generation did not return a dict"
        assert "status" in response, "JSON response missing 'status' key"

    def test_models_available(self):
        assert self.client.check_model_available("llava"), "llava model missing. Run: ollama pull llava"
        assert self.client.check_model_available("llama3"), "llama3 model missing. Run: ollama pull llama3"


class TestScreenCapture:

    def setup_method(self):
        import yaml
        with open('config/settings.yaml') as f:
            config = yaml.safe_load(f)
        from utils.screen_capture import ScreenCapture
        self.screen = ScreenCapture(config)

    def test_capture_primary(self):
        path = self.screen.capture_primary()
        assert path is not None, "Screen capture returned None path"
        assert os.path.exists(path), f"Screenshot file not found: {path}"
        assert path.endswith('.png'), "Screenshot file does not end with .png"

    def test_screenshot_has_content(self):
        path = self.screen.capture_primary()
        size = os.path.getsize(path)
        assert size > 1000, "Screenshot file too small"


class TestMemorySystem:

    def setup_method(self):
        import uuid
        import yaml
        with open('config/settings.yaml') as f:
            config = yaml.safe_load(f)
        self.test_db_path = f"data/test_memory_{uuid.uuid4().hex}.db"
        config['memory']['db_path'] = self.test_db_path
        from utils.memory_system import MemorySystem
        self.memory = MemorySystem(config)

    def test_save_and_retrieve_episode(self):
        self.memory.save_episode(
            task="test task",
            steps=[{"step": 1}],
            outcome="completed",
            success=True,
            duration=1.0
        )
        episodes = self.memory.get_recent_episodes(limit=1)
        assert len(episodes) > 0, "No episodes were saved"
        assert episodes[0]['task'] == "test task", "Saved task text mismatch"

    def test_stats_returns_dict(self):
        stats = self.memory.get_stats()
        assert isinstance(stats, dict), "Memory stats did not return dict"
        assert 'total_episodes' in stats, "Stats missing total_episodes"
        assert 'success_rate' in stats, "Stats missing success_rate"

    def teardown_method(self):
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except PermissionError:
                pass


class TestPlanner:

    def setup_method(self):
        import uuid
        import yaml
        with open('config/settings.yaml') as f:
            config = yaml.safe_load(f)
        self.test_db_path = f"data/test_planner_memory_{uuid.uuid4().hex}.db"
        config['memory']['db_path'] = self.test_db_path
        from utils.ollama_client import OllamaClient
        from utils.memory_system import MemorySystem
        from agents.planner_agent import PlannerAgent
        ollama = OllamaClient(config)
        memory = MemorySystem(config)
        self.planner = PlannerAgent(ollama, memory)

    def test_plan_has_steps(self):
        plan = self.planner.create_plan("open notepad")
        assert plan is not None, "Planner returned None"
        assert 'steps' in plan, "Planner response missing 'steps'"
        assert len(plan['steps']) > 0, "Planner returned zero steps"

    def test_plan_steps_have_required_fields(self):
        plan = self.planner.create_plan("open notepad")
        for step in plan['steps']:
            assert 'step_number' in step, "Step missing step_number"
            assert 'action_type' in step, "Step missing action_type"
            assert 'description' in step, "Step missing description"
            assert 'target' in step, "Step missing target"
            assert 'expected_outcome' in step, "Step missing expected_outcome"

    def test_plan_uses_valid_action_types(self):
        valid_actions = {
            'click', 'double_click', 'right_click',
            'type', 'type_text', 'press_key', 'press',
            'open_app', 'open', 'scroll_up', 'scroll_down',
            'close_window', 'close', 'save', 'save_and_close',
            'minimize', 'maximize', 'find_and_click',
            'wait', 'hotkey', 'select_all', 'copy',
            'paste', 'undo', 'new_file', 'screenshot'
        }
        plan = self.planner.create_plan("open notepad and type hello")
        for step in plan['steps']:
            assert step['action_type'] in valid_actions, f"Invalid action_type: {step['action_type']}"

    def teardown_method(self):
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except PermissionError:
                pass


class TestSafetyGuard:

    def setup_method(self):
        from utils.safety_guard import SafetyGuard
        self.safety = SafetyGuard('config/safety_rules.yaml')
        self.safety.log_path = 'data/test_safety_log.txt'

    def test_blocks_dangerous_commands(self):
        result = self.safety.check_action("rm -rf /")
        assert result['decision'] == 'BLOCKED', "Dangerous command should be BLOCKED"

    def test_confirms_risky_actions(self):
        result = self.safety.check_action("delete this file")
        assert result['decision'] in ['CONFIRM', 'BLOCKED'], "Risky action should require confirmation or be blocked"

    def test_allows_safe_actions(self):
        result = self.safety.check_action("open notepad")
        assert result['decision'] == 'SAFE', "Safe action should be allowed"

    def teardown_method(self):
        if os.path.exists('data/test_safety_log.txt'):
            os.remove('data/test_safety_log.txt')
