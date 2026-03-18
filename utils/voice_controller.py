"""
VoiceController — ultra-fast local voice pipeline.

- tiny Whisper for speed
- direct command routing for simple operations
- optional background wake-word listening
"""

import os
import tempfile
import threading
import time


class VoiceController:

    OPEN_COMMANDS = [
        "open",
        "launch",
        "start",
        "run",
        "load",
        "boot up",
        "fire up",
    ]

    CLOSE_COMMANDS = [
        "close",
        "quit",
        "exit",
        "shut",
        "kill",
        "stop",
        "end",
    ]

    SYSTEM_COMMANDS = {
        "take screenshot": "screenshot",
        "show desktop": "show_desktop",
        "lock computer": "lock",
        "sleep": "sleep",
        "organize downloads": "organize_downloads",
        "system health": "system_health",
        "what is open": "list_windows",
        "side by side": "arrange_side_by_side",
        "maximize": "maximize_window",
        "minimize": "minimize_window",
    }

    def __init__(self, config, app_launcher=None):
        voice_cfg = config.get("voice", {})
        model_size = voice_cfg.get("whisper_model", "tiny")

        print(f"[Voice] Loading Whisper {model_size}...")
        import whisper

        self.model = whisper.load_model(model_size)
        print("[Voice] Whisper ready")

        self.app_launcher = app_launcher
        self.wake_word = voice_cfg.get("wake_word", "hey clevrr")
        self.running = False
        self.callback = None

        import pyttsx3

        self.tts = pyttsx3.init()
        self.tts.setProperty("rate", voice_cfg.get("tts_rate", 200))
        self.tts.setProperty("volume", voice_cfg.get("tts_volume", 0.9))

    def process_command(self, text: str) -> dict:
        text_lower = text.lower().strip()

        for cmd in self.OPEN_COMMANDS:
            if text_lower.startswith(cmd):
                app_name = text_lower.replace(cmd, "", 1).strip()
                if self.app_launcher:
                    result = self.app_launcher.launch_app(app_name)
                else:
                    result = {
                        "success": False,
                        "message": "App launcher unavailable",
                    }
                return {
                    "type": "app_launch",
                    "result": result,
                    "spoke": True,
                }

        for cmd in self.CLOSE_COMMANDS:
            if text_lower.startswith(cmd):
                app_name = text_lower.replace(cmd, "", 1).strip()
                return {
                    "type": "app_close",
                    "target": app_name,
                    "spoke": True,
                }

        for phrase, action in self.SYSTEM_COMMANDS.items():
            if phrase in text_lower:
                return {
                    "type": "system",
                    "action": action,
                    "spoke": True,
                }

        return {
            "type": "ai_task",
            "text": text,
            "spoke": False,
        }

    def listen_once(self) -> str:
        import sounddevice as sd
        import soundfile as sf

        sample_rate = 16000
        duration = 5

        audio = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
        )
        sd.wait()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as file:
            sf.write(file.name, audio, sample_rate)
            temp_path = file.name

        result = self.model.transcribe(
            temp_path,
            language="en",
            fp16=False,
            temperature=0,
        )

        os.unlink(temp_path)
        return result["text"].strip()

    def speak(self, text: str):
        print(f"[AI] {text}")
        try:
            self.tts.say(text)
            self.tts.runAndWait()
        except Exception:
            pass

    def start_listening(self, callback):
        self.callback = callback
        self.running = True
        threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="VoiceListener",
        ).start()

    def _listen_loop(self):
        import numpy as np
        import sounddevice as sd
        import soundfile as sf

        print("[Voice] Listening for wake word...")

        while self.running:
            try:
                audio = sd.rec(
                    int(2 * 16000),
                    samplerate=16000,
                    channels=1,
                    dtype="float32",
                )
                sd.wait()

                if np.abs(audio).mean() < 0.01:
                    continue

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as file:
                    sf.write(file.name, audio, 16000)
                    temp = file.name

                text = self.model.transcribe(
                    temp,
                    language="en",
                    fp16=False,
                    temperature=0,
                )["text"].lower().strip()

                os.unlink(temp)

                if self.wake_word.lower() in text:
                    self.speak("Yes?")
                    command = self.listen_once()
                    if command and self.callback:
                        self.callback(command)

            except Exception:
                time.sleep(1)

    def stop(self):
        self.running = False

    def start_background_listening(self, callback):
        self.start_listening(callback)
