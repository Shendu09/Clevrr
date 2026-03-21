from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class BrainConfig:
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    ollama_timeout: int = 30
    max_memory_turns: int = 10
    confidence_threshold: float = 0.7
    fallback_to_os: bool = True
    bus_socket_path: str = "/tmp/clevrr_bus.sock"
    default_user_id: str = "default_user"
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "BrainConfig":
        return cls(
            ollama_host=os.getenv("BRAIN_OLLAMA_HOST", "http://localhost:11434"),
            ollama_model=os.getenv("BRAIN_OLLAMA_MODEL", "llama3"),
            ollama_timeout=int(os.getenv("BRAIN_OLLAMA_TIMEOUT", "30")),
            max_memory_turns=int(os.getenv("BRAIN_MAX_MEMORY_TURNS", "10")),
            confidence_threshold=float(os.getenv("BRAIN_CONFIDENCE_THRESHOLD", "0.7")),
            fallback_to_os=os.getenv("BRAIN_FALLBACK_TO_OS", "true").lower() in ("1", "true", "yes"),
            bus_socket_path=os.getenv("BRAIN_BUS_SOCKET_PATH", "/tmp/clevrr_bus.sock"),
            default_user_id=os.getenv("BRAIN_DEFAULT_USER_ID", "default_user"),
            enabled=os.getenv("BRAIN_ENABLED", "true").lower() in ("1", "true", "yes"),
        )
