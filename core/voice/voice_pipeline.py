from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from .audio_capture import AudioCapture
from .config import VoiceConfig
from .transcriber import Transcriber
from .wake_word import WakeWordDetector


class VoicePipeline:
    def __init__(
        self,
        config: VoiceConfig,
        on_command: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._config = config
        self._on_command = on_command
        self._on_status = on_status
        self._active = False
        self._awaiting_command = False
        self._lock = threading.Lock()
        self.logger = logging.getLogger("clevrr.voice.pipeline")

        self._wake_word = WakeWordDetector(config, on_wake_word=self._on_wake_word)
        self._transcriber = Transcriber(config)
        self._capture = AudioCapture(
            config,
            on_speech_start=self._on_speech_start,
            on_speech_end=self._on_speech_end,
        )

    @property
    def is_running(self) -> bool:
        return self._active

    def start(self) -> None:
        if not self._config.enabled:
            self.logger.info("Voice pipeline disabled via config")
            return

        if self._active:
            return

        self._active = True
        self._capture.start()
        self._emit_status("listening")
        self.logger.info("Voice pipeline started")

    def stop(self) -> None:
        if not self._active:
            return

        self._active = False
        self._capture.stop()
        with self._lock:
            self._awaiting_command = False
        self._emit_status("stopped")
        self.logger.info("Voice pipeline stopped")

    def _on_speech_start(self) -> None:
        if self._active:
            self._emit_status("speech")

    def _on_speech_end(self, audio_bytes: bytes) -> None:
        if not self._active:
            return

        if self._wake_word.detect_audio(audio_bytes):
            with self._lock:
                self._awaiting_command = True
            self._emit_status("wake")
            return

        result = self._transcriber.transcribe(audio_bytes)
        if not result.success or not result.text:
            self.logger.debug("Transcription empty or unavailable")
            return

        text = result.text.strip()
        self.logger.debug(f"Transcription: {text}")

        if self._wake_word.detect_transcript(text):
            command_text = self._strip_wake_word_prefix(text)
            if command_text:
                self._dispatch_command(command_text)
                return

            with self._lock:
                self._awaiting_command = True
            self._emit_status("wake")
            return

        with self._lock:
            awaiting = self._awaiting_command
            if awaiting:
                self._awaiting_command = False

        if awaiting:
            self._dispatch_command(text)

    def _on_wake_word(self, wake_word: str, score: float) -> None:
        _ = wake_word, score
        with self._lock:
            self._awaiting_command = True
        self._emit_status("wake")

    def _dispatch_command(self, command_text: str) -> None:
        cleaned = command_text.strip()
        if not cleaned:
            return

        self.logger.info(f"Voice command: {cleaned}")
        self._emit_status("command")
        if self._on_command:
            self._on_command(cleaned)

    def _strip_wake_word_prefix(self, text: str) -> str:
        lowered = text.lower().strip()
        for wake_word in self._config.wake_words:
            normalized = wake_word.lower().strip()
            if not normalized:
                continue
            if lowered.startswith(normalized):
                candidate = lowered[len(normalized):].lstrip(" ,:;.!?-")
                if candidate:
                    return candidate
                return ""
            token = f"{normalized},"
            if lowered.startswith(token):
                candidate = lowered[len(token):].strip()
                return candidate
        return ""

    def _emit_status(self, status: str) -> None:
        if self._on_status:
            self._on_status(status)
