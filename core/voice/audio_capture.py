from __future__ import annotations

import collections
import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from .config import VoiceConfig

try:
    import sounddevice as sd

    _HAS_SOUNDDEVICE = True
except ImportError:
    _HAS_SOUNDDEVICE = False

try:
    import webrtcvad

    _HAS_VAD = True
except ImportError:
    _HAS_VAD = False


@dataclass(slots=True)
class AudioChunk:
    data: bytes
    timestamp: float
    is_speech: bool


class AudioCapture:
    def __init__(
        self,
        config: VoiceConfig,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_end: Optional[Callable[[bytes], None]] = None,
    ) -> None:
        self._config = config
        self._on_speech_start = on_speech_start
        self._on_speech_end = on_speech_end
        self._vad = webrtcvad.Vad(config.vad_aggressiveness) if _HAS_VAD else None
        self._audio_queue: queue.Queue[bytes] = queue.Queue()
        self._stop_event = threading.Event()
        self._recording = False
        self._frames: list[bytes] = []
        self._silence_counter = 0
        self._recent_chunks = collections.deque(maxlen=16)
        self.logger = logging.getLogger("clevrr.voice.capture")

    def start(self) -> None:
        if not _HAS_SOUNDDEVICE:
            raise RuntimeError(
                "sounddevice not installed. "
                "Run: pip install sounddevice"
            )

        self._stop_event.clear()
        threading.Thread(
            target=self._capture_loop,
            name="clevrr-audio-capture",
            daemon=True,
        ).start()
        self.logger.info(
            f"Audio capture started ({self._config.sample_rate}Hz mono)"
        )

    def stop(self) -> None:
        self._stop_event.set()
        self.logger.info("Audio capture stopped")

    def _capture_loop(self) -> None:
        chunk_samples = int(
            self._config.sample_rate * self._config.chunk_duration_ms / 1000
        )

        def _callback(indata, frames, time_info, status) -> None:
            _ = frames, time_info
            if status:
                self.logger.warning(f"Audio status: {status}")
            audio_bytes = (indata * 32767).astype(np.int16).tobytes()
            self._audio_queue.put(audio_bytes)

        with sd.InputStream(
            samplerate=self._config.sample_rate,
            channels=self._config.channels,
            dtype="float32",
            blocksize=chunk_samples,
            callback=_callback,
        ):
            while not self._stop_event.is_set():
                try:
                    chunk = self._audio_queue.get(timeout=0.1)
                    self._process_chunk(chunk)
                except queue.Empty:
                    continue

    def _process_chunk(self, chunk: bytes) -> None:
        is_speech = False
        if self._vad:
            try:
                is_speech = self._vad.is_speech(chunk, self._config.sample_rate)
            except Exception:
                is_speech = True

        self._recent_chunks.append(
            AudioChunk(data=chunk, timestamp=time.time(), is_speech=is_speech)
        )

        if is_speech:
            if not self._recording:
                self._recording = True
                self._frames = []
                self._silence_counter = 0
                if self._on_speech_start:
                    self._on_speech_start()
                self.logger.debug("Speech started")

            self._frames.append(chunk)
            self._silence_counter = 0
            return

        if self._recording:
            self._frames.append(chunk)
            self._silence_counter += 1

            silence_chunks = (
                self._config.silence_threshold_ms // self._config.chunk_duration_ms
            )
            if self._silence_counter >= silence_chunks:
                audio_data = b"".join(self._frames)
                self._recording = False
                self._frames = []
                self._silence_counter = 0
                self.logger.debug(f"Speech ended — {len(audio_data)} bytes")
                if self._on_speech_end:
                    self._on_speech_end(audio_data)
