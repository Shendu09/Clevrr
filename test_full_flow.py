import sys

import pytest
import yaml

sys.path.append('.')

from agents.orchestrator import Orchestrator


@pytest.mark.timeout(180)
def test_full_flow_open_notepad_and_type_bushu():
    with open("config/settings.yaml", "r") as f:
        config = yaml.safe_load(f)

    config['memory']['db_path'] = 'data/test_full_flow_memory.db'
    orchestrator = Orchestrator(config)
    result = orchestrator.run_task("open notepad and type bushu")

    assert isinstance(result, dict), "Orchestrator run_task must return a dictionary"
    assert "success" in result, "Result missing 'success' key"
    assert "steps_completed" in result, "Result missing 'steps_completed' key"
    assert "total_steps" in result, "Result missing 'total_steps' key"
    assert result["total_steps"] > 0, "Planner produced zero steps"
