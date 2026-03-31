"""
TTS Manager — Multi-backend Text-to-Speech system.

Supports:
- pyttsx3 (offline, always available)
- ElevenLabs (cloud, best voice quality)
- Coqui TTS (offline, better quality than pyttsx3)

Priority fallback chain:
1. ElevenLabs (if API key available)
2. Coqui TTS (if available)
3. pyttsx3 (always available)
"""

import os
import threading
import logging
from typing import Optional, Literal
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class TTSBackend(ABC):
    """Abstract base class for TTS backends."""
    
    @abstractmethod
    def speak(self, text: str) -> bool:
        """Speak the text. Returns True if successful."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available."""
        pass


class PyTTSX3Backend(TTSBackend):
    """Local TTS using pyttsx3."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.engine = None
        self._initialize()
    
    def _initialize(self):
        """Initialize pyttsx3 engine."""
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', self.config.get('tts_rate', 150))
            self.engine.setProperty('volume', self.config.get('tts_volume', 0.9))
            logger.info("[TTS] PyTTSX3 initialized")
        except Exception as e:
            logger.error(f"[TTS] PyTTSX3 initialization failed: {e}")
            self.engine = None
    
    def speak(self, text: str) -> bool:
        """Speak using pyttsx3."""
        if not self.is_available():
            return False
        
        try:
            self.engine.say(text)
            self.engine.runAndWait()
            return True
        except Exception as e:
            logger.error(f"[TTS] PyTTSX3 speak failed: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if engine is available."""
        return self.engine is not None


class ElevenLabsBackend(TTSBackend):
    """Cloud TTS using ElevenLabs API."""
    
    def __init__(self, api_key: Optional[str] = None, config: dict = None):
        self.config = config or {}
        self.api_key = api_key or os.getenv('ELEVENLABS_API_KEY')
        self.voice_id = self.config.get('elevenlabs_voice_id', '21m00Tcm4TlvDq8ikWAM')  # Rachel
        self.model_id = self.config.get('elevenlabs_model_id', 'eleven_monolingual_v1')
        self.available = bool(self.api_key)
        
        if self.available:
            logger.info(f"[TTS] ElevenLabs initialized (voice: {self.voice_id})")
        else:
            logger.debug("[TTS] ElevenLabs API key not found")
    
    def speak(self, text: str) -> bool:
        """Speak using ElevenLabs API."""
        if not self.is_available():
            return False
        
        try:
            import requests
            
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }
            data = {
                "text": text,
                "model_id": self.model_id,
                "voice_settings": {
                    "stability": self.config.get('stability', 0.5),
                    "similarity_boost": self.config.get('similarity_boost', 0.75)
                }
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # Save and play audio
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    f.write(response.content)
                    audio_path = f.name
                
                # Play audio in background
                self._play_audio(audio_path)
                return True
            else:
                logger.error(f"[TTS] ElevenLabs error: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"[TTS] ElevenLabs speak failed: {e}")
            return False
    
    def _play_audio(self, audio_path: str):
        """Play audio file."""
        try:
            # Try VLC first
            try:
                import vlc
                media = vlc.Media(audio_path)
                player = vlc.MediaListPlayer()
                player.get_media_list().add_media(media)
                player.play()
                return
            except:
                pass
            
            # Fallback to pygame
            try:
                import pygame
                pygame.mixer.init()
                pygame.mixer.music.load(audio_path)
                pygame.mixer.music.play()
                return
            except:
                pass
            
            # Fallback to playsound
            try:
                from playsound import playsound
                playsound(audio_path)
                return
            except:
                pass
            
            logger.warning("[TTS] No audio player found")
        
        except Exception as e:
            logger.error(f"[TTS] Audio playback failed: {e}")
    
    def is_available(self) -> bool:
        """Check if API key is available."""
        return self.available


class CoquiTTSBackend(TTSBackend):
    """Offline TTS using Coqui TTS."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.model = None
        self._device = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Coqui TTS."""
        try:
            from TTS.api import TTS
            import torch
            
            # Use GPU if available
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            
            # Load model (first time will download ~1GB)
            model_name = self.config.get('coqui_model', 'tts_models/en/ljspeech/glow-tts')
            self.model = TTS(model_name, gpu=(self._device == "cuda"))
            
            logger.info(f"[TTS] Coqui initialized on {self._device}")
        
        except Exception as e:
            logger.debug(f"[TTS] Coqui initialization failed: {e}")
            self.model = None
    
    def speak(self, text: str) -> bool:
        """Speak using Coqui TTS."""
        if not self.is_available():
            return False
        
        try:
            import tempfile
            import winsound
            
            # Generate speech
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                output_path = f.name
            
            self.model.tts_to_file(text=text, file_path=output_path)
            
            # Play on Windows
            if os.name == 'nt':
                winsound.PlaySound(output_path, winsound.SND_FILENAME)
            else:
                # On Linux/Mac, try os.system
                os.system(f"play {output_path}")
            
            return True
        
        except Exception as e:
            logger.error(f"[TTS] Coqui speak failed: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if model is available."""
        return self.model is not None


class TTSManager:
    """Manages multiple TTS backends with automatic fallback."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.executor = ThreadPoolExecutor(max_workers=1)
        
        # Initialize backends in priority order
        self.backends = []
        
        # 1. ElevenLabs (cloud, best quality)
        elevenlabs = ElevenLabsBackend(config=self.config)
        if elevenlabs.is_available():
            self.backends.append(("ElevenLabs", elevenlabs))
        
        # 2. Coqui TTS (offline, good quality)
        try:
            coqui = CoquiTTSBackend(config=self.config)
            if coqui.is_available():
                self.backends.append(("Coqui", coqui))
        except:
            pass
        
        # 3. PyTTSX3 (always available fallback)
        pyttsx3 = PyTTSX3Backend(config=self.config)
        self.backends.append(("PyTTSX3", pyttsx3))
        
        logger.info(f"[TTS] Initialized with backends: {[name for name, _ in self.backends]}")
    
    def speak(self, text: str, async_mode: bool = True) -> bool:
        """
        Speak text using available backend.
        
        Args:
            text: Text to speak
            async_mode: If True, speak in background thread
        
        Returns:
            True if speech started successfully
        """
        if not text or not text.strip():
            return False
        
        def _do_speak():
            for backend_name, backend in self.backends:
                try:
                    if backend.speak(text):
                        logger.debug(f"[TTS] Spoke with {backend_name}")
                        return True
                except Exception as e:
                    logger.warning(f"[TTS] {backend_name} failed: {e}")
                    continue
            
            logger.warning("[TTS] All backends failed")
            return False
        
        if async_mode:
            self.executor.submit(_do_speak)
            return True
        else:
            return _do_speak()
    
    def get_backend_name(self) -> str:
        """Get name of primary active backend."""
        if self.backends:
            return self.backends[0][0]
        return "None"
    
    def shutdown(self):
        """Shutdown TTS manager."""
        self.executor.shutdown(wait=False)


# Global TTS manager singleton
_tts_manager: Optional[TTSManager] = None


def initialize_tts(config: dict = None) -> TTSManager:
    """Initialize global TTS manager."""
    global _tts_manager
    _tts_manager = TTSManager(config)
    return _tts_manager


def speak(text: str, async_mode: bool = True) -> bool:
    """Speak text using global TTS manager."""
    global _tts_manager
    if _tts_manager is None:
        _tts_manager = TTSManager()
    return _tts_manager.speak(text, async_mode=async_mode)


def get_tts_backend() -> str:
    """Get current TTS backend name."""
    global _tts_manager
    if _tts_manager is None:
        _tts_manager = TTSManager()
    return _tts_manager.get_backend_name()


def shutdown_tts():
    """Shutdown TTS manager."""
    global _tts_manager
    if _tts_manager:
        _tts_manager.shutdown()
