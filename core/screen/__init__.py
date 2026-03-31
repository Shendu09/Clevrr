"""Screen State Classification System
===================================

Detects and manages screen states for intelligent automation.

Provides:
- Screen type detection (desktop, browser, profile selection, etc.)
- Screen-specific handlers for each state
- State-aware action routing
- Recovery logic for stuck states
"""

from .screen_types import ScreenType
from .screen_detector import ScreenDetector
from .screen_handler import ScreenHandler
from .screen_router import ScreenRouter

__all__ = [
    "ScreenType",
    "ScreenDetector", 
    "ScreenHandler",
    "ScreenRouter",
]
