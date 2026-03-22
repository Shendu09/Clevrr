from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class ComputerUseConfig:
    ollama_host: str = "http://localhost:11434"
    vision_model: str = "qwen2-vl"
    action_model: str = "llama3"
    code_model: str = "codellama"
    max_steps: int = 10
    step_delay_ms: int = 500
    screenshot_quality: int = 85
    max_width: int = 1280
    confidence_threshold: float = 0.7
    dry_run: bool = False
    save_screenshots: bool = True
    screenshot_dir: str = "data/agent_steps"

    @classmethod
    def from_env(cls) -> "ComputerUseConfig":
        return cls(
            ollama_host=os.getenv("CU_OLLAMA_HOST", "http://localhost:11434"),
            vision_model=os.getenv("CU_VISION_MODEL", "qwen2-vl"),
            action_model=os.getenv("CU_ACTION_MODEL", "llama3"),
            code_model=os.getenv("CU_CODE_MODEL", "codellama"),
            max_steps=int(os.getenv("CU_MAX_STEPS", "10")),
            step_delay_ms=int(os.getenv("CU_STEP_DELAY_MS", "500")),
            screenshot_quality=int(os.getenv("CU_SCREENSHOT_QUALITY", "85")),
            max_width=int(os.getenv("CU_MAX_WIDTH", "1280")),
            confidence_threshold=float(os.getenv("CU_CONFIDENCE_THRESHOLD", "0.7")),
            dry_run=os.getenv("CU_DRY_RUN", "false").lower() in {"1", "true", "yes"},
            save_screenshots=os.getenv("CU_SAVE_SCREENSHOTS", "true").lower() in {"1", "true", "yes"},
            screenshot_dir=os.getenv("CU_SCREENSHOT_DIR", "data/agent_steps"),
        )
