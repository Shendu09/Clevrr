"""
VoiceController — 100% Local Voice Input & Output

Speech-to-text: OpenAI Whisper running locally (no API).
Text-to-speech: pyttsx3 running locally (no API).
Audio capture: sounddevice (local microphone).

ZERO external API calls. Everything runs on the user's machine.
"""

import logging
import os
import tempfile
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class VoiceController:
    """Handles voice input and output using only local tools.

    - **Whisper**: Runs the speech recognition model locally.
      Downloads once on first use, then works fully offline.
    - **pyttsx3**: Uses the OS text-to-speech engine. Fully offline.
    - **sounddevice**: Records from the local microphone.
    """

    def __init__(self, config: dict) -> None:
        """Initialize VoiceController with configuration.

        Args:
            config: Dictionary containing voice settings from settings.yaml.
        """
        voice_config = config.get("voice", {})
        self.enabled: bool = voice_config.get("enabled", False)
        self.wake_word: str = voice_config.get("wake_word", "hey computer")
        self.whisper_model_name: str = voice_config.get("whisper_model", "base")
        self.whisper_language: str = voice_config.get("whisper_language", "en")
        self.tts_rate: int = voice_config.get("tts_rate", 175)
        self.tts_volume: float = voice_config.get("tts_volume", 1.0)

        self.running: bool = False
        self.callback: Optional[Callable[[str], None]] = None
        self._listen_thread: Optional[threading.Thread] = None

        # Load Whisper model locally
        self._whisper_model = None
        if self.enabled:
            self._load_whisper()

        # Initialize pyttsx3
        self._tts_engine = None
        if self.enabled:
            self._load_tts()

    # ------------------------------------------------------------------
    # Model Loading
    # ------------------------------------------------------------------

    def _load_whisper(self) -> None:
        """Load the Whisper speech recognition model locally."""
        try:
            import whisper

            print(
                f"🎤 Loading Whisper model '{self.whisper_model_name}' "
                f"(local, offline after first download)..."
            )
            self._whisper_model = whisper.load_model(self.whisper_model_name)
            logger.info("Whisper model '%s' loaded.", self.whisper_model_name)
        except ImportError:
            logger.warning(
                "openai-whisper not installed. Voice input disabled. "
                "Install with: pip install openai-whisper"
            )
        except Exception as exc:
            logger.error("Failed to load Whisper model: %s", exc)

    def _load_tts(self) -> None:
        """Initialize the pyttsx3 text-to-speech engine."""
        try:
            import pyttsx3

            self._tts_engine = pyttsx3.init()
            self._tts_engine.setProperty("rate", self.tts_rate)
            self._tts_engine.setProperty("volume", self.tts_volume)
            logger.info("pyttsx3 TTS engine initialized.")
        except ImportError:
            logger.warning(
                "pyttsx3 not installed. Voice output disabled. "
                "Install with: pip install pyttsx3"
            )
        except Exception as exc:
            logger.error("Failed to initialize TTS engine: %s", exc)

    # ------------------------------------------------------------------
    # Audio Recording
    # ------------------------------------------------------------------

    def record_audio(self, duration: int = 5, sample_rate: int = 16000) -> str:
        """Record audio from the microphone.

        Args:
            duration: Recording duration in seconds.
            sample_rate: Audio sample rate (Whisper expects 16kHz).

        Returns:
            Path to the saved WAV file.
        """
        try:
            import numpy as np
            import sounddevice as sd
            import soundfile as sf

            print(f"🎙️  Recording for {duration} seconds...")
            audio_data = sd.rec(
                int(duration * sample_rate),
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
            )
            sd.wait()  # Block until recording is complete

            # Save to a temporary WAV file
            tmp_path = os.path.join(
                tempfile.gettempdir(), f"clevrr_audio_{int(time.time())}.wav"
            )
            sf.write(tmp_path, audio_data, sample_rate)

            logger.info("Audio recorded → %s", tmp_path)
            return tmp_path

        except ImportError as exc:
            logger.error(
                "Audio libraries not installed: %s. "
                "Install with: pip install sounddevice soundfile",
                exc,
            )
            return ""
        except Exception as exc:
            logger.error("Failed to record audio: %s", exc)
            return ""

    # ------------------------------------------------------------------
    # Speech-to-Text (Local Whisper)
    # ------------------------------------------------------------------

    def transcribe_audio(self, audio_path: str) -> str:
        """Transcribe an audio file using the local Whisper model.

        Args:
            audio_path: Path to the audio file.

        Returns:
            Transcribed text string.
        """
        if self._whisper_model is None:
            logger.error("Whisper model not loaded. Cannot transcribe.")
            return ""

        if not audio_path or not os.path.exists(audio_path):
            logger.error("Audio file not found: %s", audio_path)
            return ""

        try:
            result = self._whisper_model.transcribe(
                audio_path,
                language=self.whisper_language,
                fp16=False,  # CPU-safe
            )
            text = result.get("text", "").strip()
            logger.info("Transcribed: '%s'", text[:100])
            return text

        except Exception as exc:
            logger.error("Transcription failed: %s", exc)
            return ""

    def listen_for_command(self) -> str:
        """Record audio and transcribe to get a voice command.

        Returns:
            The transcribed command text.
        """
        audio_path = self.record_audio(duration=5)
        if not audio_path:
            return ""
        text = self.transcribe_audio(audio_path)

        # Clean up temp file
        try:
            os.unlink(audio_path)
        except OSError:
            pass

        return text

    # ------------------------------------------------------------------
    # Wake Word Detection
    # ------------------------------------------------------------------

    def detect_wake_word(self, text: str) -> bool:
        """Check if the wake word is present in the text.

        Args:
            text: Transcribed text to check.

        Returns:
            True if the wake word is detected.
        """
        return self.wake_word.lower() in text.lower()

    # ------------------------------------------------------------------
    # Text-to-Speech (Local pyttsx3)
    # ------------------------------------------------------------------

    def speak(self, text: str) -> None:
        """Speak text aloud using the local TTS engine.

        Also prints the spoken text to the console.

        Args:
            text: The text to speak.
        """
        print(f"[AGENT]: {text}")

        if self._tts_engine is None:
            logger.warning("TTS engine not available. Text printed only.")
            return

        try:
            self._tts_engine.say(text)
            self._tts_engine.runAndWait()
        except Exception as exc:
            logger.warning(
                "TTS playback failed: %s. "
                "Audio device may not be available.",
                exc,
            )

    # ------------------------------------------------------------------
    # Background Listening
    # ------------------------------------------------------------------

    def start_background_listening(
        self, callback: Callable[[str], None]
    ) -> None:
        """Start a background thread that listens for the wake word.

        When the wake word is detected, records a command and calls
        the callback with the transcribed text.

        Args:
            callback: Function to call with the recognized command.
        """
        if self._whisper_model is None:
            logger.error(
                "Cannot start background listening: Whisper model not loaded."
            )
            return

        self.callback = callback
        self.running = True

        def _listen_loop() -> None:
            logger.info("Background voice listening started.")
            print("👂 Listening for wake word: '%s'...", self.wake_word)

            while self.running:
                try:
                    # Short recording to check for wake word
                    audio_path = self.record_audio(duration=3)
                    if not audio_path:
                        time.sleep(1)
                        continue

                    text = self.transcribe_audio(audio_path)

                    # Clean up
                    try:
                        os.unlink(audio_path)
                    except OSError:
                        pass

                    if text and self.detect_wake_word(text):
                        self.speak("I'm listening...")

                        # Record the actual command
                        command = self.listen_for_command()
                        if command and self.callback:
                            logger.info("Voice command: '%s'", command)
                            self.callback(command)

                except Exception as exc:
                    logger.error("Background listening error: %s", exc)
                    time.sleep(2)

            logger.info("Background voice listening stopped.")

        self._listen_thread = threading.Thread(
            target=_listen_loop, daemon=True
        )
        self._listen_thread.start()

    def stop(self) -> None:
        """Stop background listening and clean up resources."""
        self.running = False
        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=5)
        logger.info("VoiceController stopped.")
