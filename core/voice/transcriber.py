from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import numpy as np

from .config import VoiceConfig

try:
    from faster_whisper import WhisperModel

    _HAS_FASTER_WHISPER = True
except ImportError:
    _HAS_FASTER_WHISPER = False


@dataclass(slots=True)
class TranscriptionResult:
    text: str
    language: str
    duration_ms: int
    success: bool


class Transcriber:
    def __init__(self, config: VoiceConfig) -> None:
        self._config = config
        self._model = None
        self.logger = logging.getLogger("clevrr.voice.transcriber")

        if _HAS_FASTER_WHISPER:
            try:
                self._model = WhisperModel(
                    model_size_or_path=config.whisper_model,
                    device=config.whisper_device,
                    compute_type=config.whisper_compute_type,
                )
                self.logger.info(
                    "Transcriber backend: faster-whisper "
                    f"({config.whisper_model}, {config.whisper_device}/{config.whisper_compute_type})"
                )
            except Exception as exc:
                self._model = None
                self.logger.warning(f"Failed to initialize faster-whisper: {exc}")
        else:
            self.logger.warning("faster-whisper not installed; transcription disabled")

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    def transcribe(self, audio_bytes: bytes) -> TranscriptionResult:
        start_time = time.time()
        if not audio_bytes:
            return TranscriptionResult(
                text="",
                language=self._config.language,
                duration_ms=0,
                success=False,
            )

        if self._model is None:
            return TranscriptionResult(
                text="",
                language=self._config.language,
                duration_ms=self._elapsed_ms(start_time),
                success=False,
            )

        try:
            audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
            if audio_int16.size == 0:
                return TranscriptionResult(
                    text="",
                    language=self._config.language,
                    duration_ms=self._elapsed_ms(start_time),
                    success=False,
                )

            audio_float = audio_int16.astype(np.float32) / 32768.0
            segments, info = self._model.transcribe(
                audio_float,
                language=self._config.language,
                vad_filter=True,
            )
            text = " ".join(segment.text.strip() for segment in segments if segment.text).strip()
            language = info.language if getattr(info, "language", None) else self._config.language

            return TranscriptionResult(
                text=text,
                language=language,
                duration_ms=self._elapsed_ms(start_time),
                success=bool(text),
            )
        except Exception as exc:
            self.logger.warning(f"Transcription failed: {exc}")
            return TranscriptionResult(
                text="",
                language=self._config.language,
                duration_ms=self._elapsed_ms(start_time),
                success=False,
            )

    @staticmethod
    def _elapsed_ms(start_time: float) -> int:
        return int((time.time() - start_time) * 1000)
