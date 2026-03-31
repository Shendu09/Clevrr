# Advanced Clevrr Computer - Utilities Package
# All utilities run 100% locally with zero external API dependencies.

from .ollama_client import OllamaClient
from .screen_capture import ScreenCapture
from .memory_system import MemorySystem
from .safety_guard import SafetyGuard
from .voice_controller import VoiceController
from .self_healer import SelfHealer
from .element_finder import ElementFinder
from .tts_manager import TTSManager, speak, get_tts_backend
from .image_comparison import ImageComparator, compare_images, are_different

__all__ = [
    "OllamaClient",
    "ScreenCapture",
    "MemorySystem",
    "SafetyGuard",
    "VoiceController",
    "SelfHealer",
    "ElementFinder",
    "TTSManager",
    "speak",
    "get_tts_backend",
    "ImageComparator",
    "compare_images",
    "are_different",
]
