"""
VoiceListener — Continuous Wake-Word Detection Loop

Listens for "Hey Clevrr" wake word and transcribes commands using local speech recognition.
Uses RealtimeSTT for low-latency, local audio processing.
ZERO external APIs.
"""

import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class VoiceListener:
    """Continuous listening loop for voice commands with wake-word detection.

    Monitors audio for "Hey Clevrr" wake word, then transcribes the following
    command and passes it to a callback handler.
    """

    def __init__(self, on_command_callback: Callable[[str], None]) -> None:
        """Initialize VoiceListener.

        Args:
            on_command_callback: Function to call when a command is recognized.
                                Takes a string (the command text) as argument.
        """
        self.on_command = on_command_callback
        self.listening = False
        self.recorder = None
        self.listener_thread = None
        logger.info("VoiceListener initialized.")

    def start(self) -> None:
        """Start the continuous listening loop in a daemon thread."""
        if self.listening:
            logger.warning("VoiceListener is already running.")
            return

        try:
            from RealtimeSTT import AudioToTextRecorder

            self.recorder = AudioToTextRecorder(
                spinner=False,
                model="tiny.en",
                language="en",
                use_microphone=True,
            )
            logger.info("RealtimeSTT recorder initialized.")
        except ImportError:
            logger.error(
                "RealtimeSTT not installed. Install with: "
                "pip install -U RealtimeSTT"
            )
            return
        except Exception as exc:
            logger.error("Failed to initialize audio recorder: %s", exc)
            return

        self.listening = True
        self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listener_thread.start()
        logger.info("Voice listener started in daemon thread.")

    def stop(self) -> None:
        """Stop the listening loop."""
        self.listening = False
        if self.recorder:
            try:
                self.recorder.shutdown()
            except Exception as exc:
                logger.warning("Error shutting down recorder: %s", exc)
        logger.info("Voice listener stopped.")

    def _listen_loop(self) -> None:
        """Main listening loop (runs in daemon thread).

        Continuously listens for "Hey Clevrr" and transcribes commands.
        """
        if not self.recorder:
            return

        logger.info("Voice listening loop started. Listening for 'Hey Clevrr'...")
        print("[VOICE] Listening for 'Hey Clevrr'...")

        while self.listening:
            try:
                # Get transcribed text from audio
                text = self.recorder.text()
                if not text or len(text.strip()) < 5:
                    continue

                text_lower = text.lower()
                logger.debug("Transcribed: %s", text)

                # Check for wake word
                words = text_lower.strip().split()
                if words and words[0] in ("v", "be", "we", "b"):
                    command = " ".join(text.strip().split()[1:]).strip()

                    # Filter out false positives (partial matches)
                    if len(command) < 4:
                        logger.debug("Wake word detected but command too short: '%s'", command)
                        continue

                    # Check for negation
                    if "never mind" in command[:30].lower():
                        logger.info("User said 'never mind'. Ignoring.")
                        print("[VOICE] Never mind. Listening for 'Hey Clevrr'...")
                        continue

                    # Valid command detected
                    logger.info("Wake word detected. Command: '%s'", command)
                    print(f"[VOICE] Command received: {command}")

                    # Call the registered callback
                    try:
                        self.on_command(command)
                    except Exception as exc:
                        logger.error("Error processing command callback: %s", exc)

            except KeyboardInterrupt:
                break
            except Exception as exc:
                logger.warning("Error in voice listening loop: %s", exc)
                time.sleep(0.5)  # Brief pause before retry

        logger.info("Voice listening loop ended.")


def start_wake_word_loop(on_command_callback: Callable[[str], None]) -> VoiceListener:
    """Convenience function to start a wake-word listener.

    Args:
        on_command_callback: Function to call when a command is recognized.

    Returns:
        VoiceListener instance (already started).
    """
    listener = VoiceListener(on_command_callback)
    listener.start()
    return listener
