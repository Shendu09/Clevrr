"""
Settings Manager — Configure AI system behavior, TTS, image comparison, etc.

Manages configuration for:
- TTS backend selection (ElevenLabs, Coqui, pyttsx3)
- Image comparison thresholds
- Screen watching sensitivity
- Action retry settings
- Chat history retention
- Overlay UI preferences
- Logging levels

Settings stored in YAML with schema validation.
Real-time reload support.
"""

import yaml
import logging
from pathlib import Path
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, asdict
import json

logger = logging.getLogger(__name__)


@dataclass
class TTSSettings:
    """Text-to-Speech configuration."""
    enabled: bool = True
    backend: str = "auto"  # auto, elevenlabs, coqui, pyttsx3
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel
    coqui_model: str = "tts_models/en/ljspeech/glow-tts"
    pyttsx3_rate: float = 150
    pyttsx3_volume: float = 0.9
    async_mode: bool = True  # Speak in background


@dataclass
class ImageComparisonSettings:
    """Image comparison configuration."""
    enabled: bool = True
    similarity_threshold: float = 0.85
    pixel_threshold: float = 0.05
    min_region_size: int = 100


@dataclass
class ScreenWatcherSettings:
    """Continuous screen watching configuration."""
    enabled: bool = False  # Off by default (expensive)
    check_interval: float = 1.0
    similarity_threshold: float = 0.85
    auto_error_close: bool = False
    auto_retry: bool = True
    max_retries: int = 3


@dataclass
class ActionExecutorSettings:
    """Action execution and retry configuration."""
    enabled: bool = True
    max_retries: int = 3
    retry_delay: float = 0.5
    max_retry_delay: float = 5.0
    verify_screen_change: bool = True
    continue_on_failure: bool = False


@dataclass
class ChatHistorySettings:
    """Chat history and conversation memory."""
    enabled: bool = True
    max_context_messages: int = 20
    retention_days: int = 30
    auto_cleanup: bool = True


@dataclass
class OverlayUISettings:
    """Overlay UI preferences."""
    enabled: bool = True
    hotkey: str = "CommandOrControl+Shift+Space"
    show_help_text: bool = True
    show_status_indicator: bool = True
    input_bar_position: str = "bottom"  # bottom, center, top
    animation_speed: float = 0.3  # seconds
    glow_intensity: float = 10.0
    blur_amount: float = 20  # px


@dataclass
class LoggingSettings:
    """Logging configuration."""
    level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    file_path: str = "data/logs/clevrr.log"
    max_file_size: int = 10_485_760  # 10MB
    backup_count: int = 5
    log_tts: bool = True
    log_vision: bool = True
    log_overlay: bool = True


class SettingsManager:
    """Manage all system settings."""
    
    def __init__(self, config_path: str = "config/settings.yaml"):
        """
        Initialize settings manager.
        
        Args:
            config_path: Path to settings YAML file
        """
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize with defaults
        self.tts = TTSSettings()
        self.image_comparison = ImageComparisonSettings()
        self.screen_watcher = ScreenWatcherSettings()
        self.action_executor = ActionExecutorSettings()
        self.chat_history = ChatHistorySettings()
        self.overlay_ui = OverlayUISettings()
        self.logging = LoggingSettings()
        
        # Load from file if exists
        self.load()
    
    def load(self):
        """Load settings from YAML file."""
        if not self.config_path.exists():
            logger.debug(f"[Settings] File not found: {self.config_path}, using defaults")
            return
        
        try:
            with open(self.config_path, 'r') as f:
                data = yaml.safe_load(f) or {}
            
            # Parse settings sections
            if 'tts' in data:
                self.tts = TTSSettings(**data['tts'])
            
            if 'image_comparison' in data:
                self.image_comparison = ImageComparisonSettings(**data['image_comparison'])
            
            if 'screen_watcher' in data:
                self.screen_watcher = ScreenWatcherSettings(**data['screen_watcher'])
            
            if 'action_executor' in data:
                self.action_executor = ActionExecutorSettings(**data['action_executor'])
            
            if 'chat_history' in data:
                self.chat_history = ChatHistorySettings(**data['chat_history'])
            
            if 'overlay_ui' in data:
                self.overlay_ui = OverlayUISettings(**data['overlay_ui'])
            
            if 'logging' in data:
                self.logging = LoggingSettings(**data['logging'])
            
            logger.info(f"[Settings] Loaded from {self.config_path}")
        
        except Exception as e:
            logger.error(f"[Settings] Failed to load: {e}")
            logger.info("[Settings] Using defaults")
    
    def save(self):
        """Save settings to YAML file."""
        try:
            data = {
                'tts': asdict(self.tts),
                'image_comparison': asdict(self.image_comparison),
                'screen_watcher': asdict(self.screen_watcher),
                'action_executor': asdict(self.action_executor),
                'chat_history': asdict(self.chat_history),
                'overlay_ui': asdict(self.overlay_ui),
                'logging': asdict(self.logging),
            }
            
            with open(self.config_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"[Settings] Saved to {self.config_path}")
        
        except Exception as e:
            logger.error(f"[Settings] Failed to save: {e}")
    
    def get(self, key: str) -> Any:
        """
        Get setting by dot-notation key.
        
        Args:
            key: e.g. "tts.enabled" or "overlay_ui.hotkey"
        
        Returns:
            Setting value or None
        """
        parts = key.split('.')
        if len(parts) < 2:
            return None
        
        section = parts[0]
        setting = '.'.join(parts[1:])
        
        if section == 'tts':
            obj = self.tts
        elif section == 'image_comparison':
            obj = self.image_comparison
        elif section == 'screen_watcher':
            obj = self.screen_watcher
        elif section == 'action_executor':
            obj = self.action_executor
        elif section == 'chat_history':
            obj = self.chat_history
        elif section == 'overlay_ui':
            obj = self.overlay_ui
        elif section == 'logging':
            obj = self.logging
        else:
            return None
        
        # Handle nested keys
        for part in setting.split('.'):
            obj = getattr(obj, part, None)
            if obj is None:
                return None
        
        return obj
    
    def set(self, key: str, value: Any) -> bool:
        """
        Set setting by dot-notation key.
        
        Args:
            key: e.g. "tts.enabled"
            value: New value
        
        Returns:
            True if successful
        """
        parts = key.split('.')
        if len(parts) < 2:
            return False
        
        section = parts[0]
        setting = parts[1]
        
        if section == 'tts':
            setattr(self.tts, setting, value)
        elif section == 'image_comparison':
            setattr(self.image_comparison, setting, value)
        elif section == 'screen_watcher':
            setattr(self.screen_watcher, setting, value)
        elif section == 'action_executor':
            setattr(self.action_executor, setting, value)
        elif section == 'chat_history':
            setattr(self.chat_history, setting, value)
        elif section == 'overlay_ui':
            setattr(self.overlay_ui, setting, value)
        elif section == 'logging':
            setattr(self.logging, setting, value)
        else:
            return False
        
        self.save()
        logger.debug(f"[Settings] Updated {key} = {value}")
        return True
    
    def get_all(self) -> Dict[str, Any]:
        """Get all settings as dict."""
        return {
            'tts': asdict(self.tts),
            'image_comparison': asdict(self.image_comparison),
            'screen_watcher': asdict(self.screen_watcher),
            'action_executor': asdict(self.action_executor),
            'chat_history': asdict(self.chat_history),
            'overlay_ui': asdict(self.overlay_ui),
            'logging': asdict(self.logging),
        }
    
    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        self.tts = TTSSettings()
        self.image_comparison = ImageComparisonSettings()
        self.screen_watcher = ScreenWatcherSettings()
        self.action_executor = ActionExecutorSettings()
        self.chat_history = ChatHistorySettings()
        self.overlay_ui = OverlayUISettings()
        self.logging = LoggingSettings()
        
        self.save()
        logger.info("[Settings] Reset to defaults")
    
    def validate(self) -> List[str]:
        """
        Validate settings.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate TTS
        if self.tts.enabled and self.tts.backend == "elevenlabs":
            if not self.tts.elevenlabs_api_key:
                errors.append("TTS: ElevenLabs API key required when backend=elevenlabs")
        
        # Validate thresholds
        if not (0.0 <= self.image_comparison.similarity_threshold <= 1.0):
            errors.append("Image comparison: similarity_threshold must be 0.0-1.0")
        
        if not (0.0 <= self.image_comparison.pixel_threshold <= 1.0):
            errors.append("Image comparison: pixel_threshold must be 0.0-1.0")
        
        if self.action_executor.max_retries < 0:
            errors.append("Action executor: max_retries must be >= 0")
        
        if self.chat_history.retention_days < 1:
            errors.append("Chat history: retention_days must be >= 1")
        
        return errors


# Global settings instance
_settings: Optional[SettingsManager] = None


def initialize_settings(config_path: str = "config/settings.yaml") -> SettingsManager:
    """Initialize global settings manager."""
    global _settings
    _settings = SettingsManager(config_path)
    return _settings


def get_settings() -> SettingsManager:
    """Get global settings manager."""
    global _settings
    if _settings is None:
        _settings = SettingsManager()
    return _settings


def get_setting(key: str) -> Any:
    """Get individual setting."""
    return get_settings().get(key)


def set_setting(key: str, value: Any) -> bool:
    """Set individual setting."""
    return get_settings().set(key, value)


def get_all_settings() -> Dict[str, Any]:
    """Get all settings."""
    return get_settings().get_all()


def validate_settings() -> List[str]:
    """Validate all settings."""
    return get_settings().validate()
