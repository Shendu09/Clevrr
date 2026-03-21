from __future__ import annotations

import time

from core.voice.audio_capture import AudioCapture
from core.voice.config import VoiceConfig
from core.voice.transcriber import Transcriber
from core.voice.transcriber import TranscriptionResult
from core.voice.voice_pipeline import VoicePipeline
from core.voice.wake_word import WakeWordDetector


class _FakeVad:
    def __init__(self, outputs: list[bool]) -> None:
        self._outputs = outputs
        self._index = 0

    def is_speech(self, _chunk: bytes, _sample_rate: int) -> bool:
        if self._index >= len(self._outputs):
            return False
        value = self._outputs[self._index]
        self._index += 1
        return value


class _FakeWakeWord:
    def __init__(self, audio_match: bool = False, transcript_match: bool = False) -> None:
        self.audio_match = audio_match
        self.transcript_match = transcript_match

    def detect_audio(self, _audio_bytes: bytes) -> bool:
        return self.audio_match

    def detect_transcript(self, _text: str) -> bool:
        return self.transcript_match


class _FakeTranscriber:
    def __init__(self, text: str, success: bool = True) -> None:
        self._result = TranscriptionResult(
            text=text,
            language="en",
            duration_ms=1,
            success=success,
        )

    def transcribe(self, _audio_bytes: bytes) -> TranscriptionResult:
        return self._result


class _FakeCapture:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def test_voice_config_defaults() -> None:
    config = VoiceConfig()
    assert config.sample_rate == 16000
    assert config.channels == 1
    assert "clevrr" in config.wake_words


def test_wake_word_detect_transcript_match() -> None:
    detector = WakeWordDetector(VoiceConfig())
    assert detector.detect_transcript("Hey Clevrr open browser")


def test_wake_word_detect_transcript_cooldown() -> None:
    detector = WakeWordDetector(VoiceConfig(), cooldown_seconds=5.0)
    detector._last_trigger_ts = time.time()
    assert not detector.detect_transcript("hey clevrr open browser")


def test_transcriber_empty_audio_returns_failure() -> None:
    transcriber = Transcriber(VoiceConfig())
    result = transcriber.transcribe(b"")
    assert not result.success
    assert result.text == ""


def test_transcriber_without_backend_returns_failure() -> None:
    transcriber = Transcriber(VoiceConfig())
    transcriber._model = None
    result = transcriber.transcribe(b"\x00\x00\x01\x00")
    assert not result.success
    assert result.text == ""


def test_audio_capture_process_chunk_emits_speech_end() -> None:
    ended_audio: list[bytes] = []

    capture = AudioCapture(
        VoiceConfig(),
        on_speech_end=lambda audio: ended_audio.append(audio),
    )
    capture._vad = _FakeVad([True] + [False] * 30)

    chunk = b"\x00\x00" * 480
    capture._process_chunk(chunk)
    for _ in range(30):
        capture._process_chunk(chunk)

    assert len(ended_audio) == 1
    assert len(ended_audio[0]) > 0


def test_voice_pipeline_start_disabled() -> None:
    config = VoiceConfig(enabled=False)
    pipeline = VoicePipeline(config)
    fake_capture = _FakeCapture()
    pipeline._capture = fake_capture

    pipeline.start()

    assert not pipeline.is_running
    assert not fake_capture.started


def test_voice_pipeline_wake_then_next_phrase_dispatches_command() -> None:
    commands: list[str] = []
    pipeline = VoicePipeline(VoiceConfig(), on_command=commands.append)
    pipeline._capture = _FakeCapture()
    pipeline._wake_word = _FakeWakeWord(audio_match=False, transcript_match=False)
    pipeline._transcriber = _FakeTranscriber("open calculator", success=True)
    pipeline._active = True

    pipeline._on_wake_word("clevrr", 1.0)
    pipeline._on_speech_end(b"\x00\x00" * 480)

    assert commands == ["open calculator"]


def test_voice_pipeline_inline_wake_word_dispatches_trimmed_command() -> None:
    commands: list[str] = []
    pipeline = VoicePipeline(VoiceConfig(), on_command=commands.append)
    pipeline._capture = _FakeCapture()
    pipeline._wake_word = _FakeWakeWord(audio_match=False, transcript_match=True)
    pipeline._transcriber = _FakeTranscriber("hey clevrr, open spotify", success=True)
    pipeline._active = True

    pipeline._on_speech_end(b"\x00\x00" * 480)

    assert commands == ["open spotify"]


def test_voice_pipeline_stop_resets_state() -> None:
    pipeline = VoicePipeline(VoiceConfig())
    fake_capture = _FakeCapture()
    pipeline._capture = fake_capture
    pipeline._active = True
    pipeline._awaiting_command = True

    pipeline.stop()

    assert not pipeline.is_running
    assert not pipeline._awaiting_command
    assert fake_capture.stopped
