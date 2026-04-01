# Adapted from OpenClaw (https://github.com/openclaw/openclaw)
# Production-ready voice wake configuration management

import json
import threading
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class VoiceWakeConfig:
    """Direct adaptation of OpenClaw's VoiceWakeConfig"""
    triggers: list[str]
    updated_at_ms: int


class VoiceWakeConfigManager:
    """
    Exact adaptation of OpenClaw's loadVoiceWakeConfig + setVoiceWakeTriggers
    From: src/infra/voicewake.ts
    """
    
    DEFAULT_TRIGGERS = ["v", "be", "we", "b"]
    
    def __init__(self, config_dir: str):
        self.config_path = Path(config_dir) / "settings" / "voicewake.json"
        self.lock = threading.RLock()
        self.config = self._load()
    
    def _sanitize_triggers(self, triggers: Optional[list]) -> list[str]:
        """Sanitize and validate trigger words"""
        if not triggers:
            triggers = []
        
        cleaned = []
        for w in triggers:
            if isinstance(w, str):
                w = w.strip()
                if w:
                    cleaned.append(w)
        
        return cleaned if cleaned else self.DEFAULT_TRIGGERS.copy()
    
    def _load(self) -> VoiceWakeConfig:
        """Load config from disk or create default"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    triggers = self._sanitize_triggers(data.get('triggers'))
                    return VoiceWakeConfig(
                        triggers=triggers,
                        updated_at_ms=data.get('updated_at_ms', 0)
                    )
        except Exception as e:
            logger.warning(f"Failed to load voice wake config: {e}")
        
        return VoiceWakeConfig(
            triggers=self.DEFAULT_TRIGGERS.copy(),
            updated_at_ms=0
        )
    
    def get(self) -> VoiceWakeConfig:
        """Get current config (threadsafe)"""
        with self.lock:
            return VoiceWakeConfig(
                triggers=self.config.triggers.copy(),
                updated_at_ms=self.config.updated_at_ms
            )
    
    def set(self, triggers: list[str]) -> VoiceWakeConfig:
        """
        Atomically set triggers and persist to disk
        Exact pattern from OpenClaw's setVoiceWakeTriggers
        """
        with self.lock:
            sanitized = self._sanitize_triggers(triggers)
            self.config = VoiceWakeConfig(
                triggers=sanitized,
                updated_at_ms=int(time.time() * 1000)
            )
            self._save_atomic()
            return VoiceWakeConfig(
                triggers=self.config.triggers.copy(),
                updated_at_ms=self.config.updated_at_ms
            )
    
    def _save_atomic(self):
        """Atomic write to disk (temp file + rename)"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temp file
        temp_path = self.config_path.with_suffix(".tmp")
        with open(temp_path, 'w') as f:
            json.dump(asdict(self.config), f, indent=2)
        
        # Atomic rename
        temp_path.replace(self.config_path)
