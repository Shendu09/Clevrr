from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class VoiceConfig:
    wake_words: list[str] = field(default_factory=lambda: ["hey clevrr", "clevrr"])
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration_ms: int = 30
    silence_threshold_ms: int = 800
    max_recording_ms: int = 10000
    whisper_model: str = "base"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"
    vad_aggressiveness: int = 2
    language: str = "en"
    bus_socket_path: str = "/tmp/clevrr_bus.sock"
    enabled: bool = True
