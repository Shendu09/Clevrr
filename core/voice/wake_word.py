from __future__ import annotations

import logging
import time
from typing import Callable, Optional

import numpy as np

from .config import VoiceConfig

try:
    from openwakeword.model import Model as OpenWakeWordModel

    _HAS_OPENWAKEWORD = True
except ImportError:
    _HAS_OPENWAKEWORD = False


class WakeWordDetector:
    def __init__(
        self,
        config: VoiceConfig,
        on_wake_word: Optional[Callable[[str, float], None]] = None,
        threshold: float = 0.5,
        cooldown_seconds: float = 1.2,
    ) -> None:
        self._config = config
        self._on_wake_word = on_wake_word
        self._threshold = threshold
        self._cooldown_seconds = cooldown_seconds
        self._last_trigger_ts = 0.0
        self._wake_words = [word.strip().lower() for word in config.wake_words if word.strip()]
        self._model = None
        self.logger = logging.getLogger("clevrr.voice.wakeword")

        if _HAS_OPENWAKEWORD:
            try:
                self._model = OpenWakeWordModel()
                self.logger.info("Wake-word backend: openwakeword")
            except Exception as exc:
                self._model = None
                self.logger.warning(f"Failed to initialize openwakeword model: {exc}")
        else:
            self.logger.warning("openwakeword not installed; using transcript fallback detection")

    @property
    def has_audio_backend(self) -> bool:
        return self._model is not None

    def detect_audio(self, audio_bytes: bytes) -> bool:
        if self._model is None or not audio_bytes:
            return False

        if self._in_cooldown():
            return False

        try:
            samples = np.frombuffer(audio_bytes, dtype=np.int16)
            if samples.size == 0:
                return False

            predictions = self._model.predict(samples)
            matched_word, score = self._best_match(predictions)
            if matched_word and score >= self._threshold:
                self._trigger(matched_word, score)
                return True
        except Exception as exc:
            self.logger.debug(f"Wake-word audio detection failed: {exc}")

        return False

    def detect_transcript(self, transcript: str) -> bool:
        text = transcript.strip().lower()
        if not text or self._in_cooldown():
            return False

        for wake_word in self._wake_words:
            if wake_word in text:
                self._trigger(wake_word, 1.0)
                return True
        return False

    def _best_match(self, predictions: object) -> tuple[Optional[str], float]:
        if not isinstance(predictions, dict):
            return None, 0.0

        best_label: Optional[str] = None
        best_score = 0.0

        for label, score in predictions.items():
            if not isinstance(score, (int, float)):
                continue
            normalized_label = str(label).replace("_", " ").strip().lower()
            if self._wake_words and not any(w in normalized_label for w in self._wake_words):
                continue
            score_value = float(score)
            if score_value > best_score:
                best_score = score_value
                best_label = normalized_label

        return best_label, best_score

    def _trigger(self, wake_word: str, score: float) -> None:
        self._last_trigger_ts = time.time()
        self.logger.info(f"Wake word detected: {wake_word} (score={score:.3f})")
        if self._on_wake_word:
            self._on_wake_word(wake_word, score)

    def _in_cooldown(self) -> bool:
        return (time.time() - self._last_trigger_ts) < self._cooldown_seconds
