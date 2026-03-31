"""Keyboard Shortcuts System
============================

Standardized keyboard shortcuts for common actions.
"""

import logging
from typing import Dict, List, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class ModifierKey(Enum):
    """Keyboard modifier keys."""
    NONE = "none"
    CTRL = "ctrl"
    ALT = "alt"
    SHIFT = "shift"
    WIN = "win"


class CommonKey(Enum):
    """Common keyboard keys."""
    ENTER = "enter"
    ESCAPE = "escape"
    TAB = "tab"
    SPACE = "space"
    BACKSPACE = "backspace"
    DELETE = "delete"
    HOME = "home"
    END = "end"
    PAGE_UP = "pageup"
    PAGE_DOWN = "pagedown"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    F1 = "f1"
    F2 = "f2"
    F5 = "f5"
    F11 = "f11"
    F12 = "f12"


class KeyboardShortcut:
    """Represents a keyboard shortcut."""
    
    def __init__(
        self,
        key: str,
        modifier: ModifierKey = ModifierKey.NONE,
        description: str = ""
    ):
        """Initialize shortcut.
        
        Args:
            key: Key to press (letter, number, or CommonKey value)
            modifier: Modifier key (ctrl, alt, shift, win)
            description: Human-readable description
        """
        self.key = key
        self.modifier = modifier
        self.description = description
    
    def __str__(self) -> str:
        """String representation."""
        if self.modifier == ModifierKey.NONE:
            return self.key
        return f"{self.modifier.value.upper()}+{self.key}"
    
    def to_tuple(self) -> tuple:
        """Convert to tuple format for executor."""
        return (self.modifier.value, self.key)


class KeyboardShortcuts:
    """Predefined keyboard shortcuts for common actions."""
    
    # Browser navigation
    BACK = KeyboardShortcut("escape", description="Go back in browser")
    FORWARD = KeyboardShortcut("alt", "right", description="Go forward")
    RELOAD = KeyboardShortcut("f5", description="Reload page")
    STOP = KeyboardShortcut("escape", description="Stop loading")
    
    # Text editing
    SELECT_ALL = KeyboardShortcut("a", ModifierKey.CTRL, "Select all")
    COPY = KeyboardShortcut("c", ModifierKey.CTRL, "Copy")
    PASTE = KeyboardShortcut("v", ModifierKey.CTRL, "Paste")
    CUT = KeyboardShortcut("x", ModifierKey.CTRL, "Cut")
    UNDO = KeyboardShortcut("z", ModifierKey.CTRL, "Undo")
    REDO = KeyboardShortcut("y", ModifierKey.CTRL, "Redo")
    
    # Navigation
    TAB = KeyboardShortcut("tab", description="Next field")
    SHIFT_TAB = KeyboardShortcut("tab", ModifierKey.SHIFT, "Previous field")
    ENTER = KeyboardShortcut("enter", description="Submit/Confirm")
    ESCAPE = KeyboardShortcut("escape", description="Cancel/Close")
    HOME = KeyboardShortcut("home", description="Go to top")
    END = KeyboardShortcut("end", description="Go to bottom")
    
    # Page navigation
    SCROLL_UP = KeyboardShortcut("pageup", description="Scroll up")
    SCROLL_DOWN = KeyboardShortcut("pagedown", description="Scroll down")
    
    # Window/App
    ALT_TAB = KeyboardShortcut("tab", ModifierKey.ALT, "Switch app")
    WINKEY = KeyboardShortcut("win", description="Open Start Menu")
    
    # Media
    PLAY_PAUSE = KeyboardShortcut("space", description="Play/Pause video")
    MUTE = KeyboardShortcut("m", description="Mute/Unmute")
    FULLSCREEN = KeyboardShortcut("f", description="Fullscreen video")
    
    # Browser specific
    NEW_TAB = KeyboardShortcut("t", ModifierKey.CTRL, "New tab")
    CLOSE_TAB = KeyboardShortcut("w", ModifierKey.CTRL, "Close tab")
    FIND = KeyboardShortcut("f", ModifierKey.CTRL, "Find on page")
    DEV_TOOLS = KeyboardShortcut("f12", description="Developer tools")
    VIEW_SOURCE = KeyboardShortcut("u", ModifierKey.CTRL, "View source")
    
    # System
    SHUTDOWN = KeyboardShortcut("s", ModifierKey.ALT, "Shutdown")
    
    # Maps for easy lookup
    _BY_NAME: Dict[str, KeyboardShortcut] = {}


# Build lookup map
def _build_shortcut_map():
    """Build shortcut lookup map."""
    for name, attr in vars(KeyboardShortcuts).items():
        if isinstance(attr, KeyboardShortcut):
            KeyboardShortcuts._BY_NAME[name.lower()] = attr
    logger.debug(f"Loaded {len(KeyboardShortcuts._BY_NAME)} shortcuts")


_build_shortcut_map()


class KeyboardShortcutsManager:
    """Manages keyboard shortcuts."""
    
    def __init__(self, executor=None):
        """Initialize manager.
        
        Args:
            executor: Executor for pressing keys
        """
        self.executor = executor
        self.custom_shortcuts: Dict[str, KeyboardShortcut] = {}
        logger.info("KeyboardShortcutsManager initialized")
    
    def register_shortcut(
        self,
        name: str,
        key: str,
        modifier: ModifierKey = ModifierKey.NONE,
        description: str = ""
    ):
        """Register a custom shortcut.
        
        Args:
            name: Name for the shortcut
            key: Key to press
            modifier: Modifier key
            description: Description
        """
        self.custom_shortcuts[name.lower()] = KeyboardShortcut(
            key, modifier, description
        )
        logger.info(f"Registered shortcut: {name}")
    
    def get_shortcut(self, name: str) -> Optional[KeyboardShortcut]:
        """Get a shortcut by name.
        
        Args:
            name: Name of shortcut
            
        Returns:
            KeyboardShortcut or None
        """
        name_lower = name.lower()
        return (
            self.custom_shortcuts.get(name_lower) or
            KeyboardShortcuts._BY_NAME.get(name_lower)
        )
    
    async def press_shortcut(self, name: str) -> bool:
        """Press a shortcut.
        
        Args:
            name: Name of shortcut
            
        Returns:
            True if successful
        """
        shortcut = self.get_shortcut(name)
        if not shortcut:
            logger.warning(f"Unknown shortcut: {name}")
            return False
        
        if not self.executor:
            logger.warning("No executor available")
            return False
        
        try:
            await self.executor.press_key(
                shortcut.key,
                shortcut.modifier.value
            )
            logger.debug(f"Pressed shortcut: {name} ({shortcut})")
            return True
        except Exception as e:
            logger.error(f"Failed to press shortcut {name}: {e}")
            return False
    
    def get_shortcut_info(self, name: str) -> Optional[Dict]:
        """Get information about a shortcut.
        
        Args:
            name: Name of shortcut
            
        Returns:
            Dictionary with shortcut info or None
        """
        shortcut = self.get_shortcut(name)
        if not shortcut:
            return None
        
        return {
            "name": name,
            "key": shortcut.key,
            "modifier": shortcut.modifier.value,
            "display": str(shortcut),
            "description": shortcut.description,
        }
    
    def list_shortcuts(self) -> List[Dict]:
        """List all available shortcuts.
        
        Returns:
            List of shortcut information
        """
        shortcuts = []
        
        # Built-in shortcuts
        for name, shortcut in KeyboardShortcuts._BY_NAME.items():
            shortcuts.append({
                "name": name,
                "key": shortcut.key,
                "modifier": shortcut.modifier.value,
                "display": str(shortcut),
                "description": shortcut.description,
            })
        
        # Custom shortcuts
        for name, shortcut in self.custom_shortcuts.items():
            shortcuts.append({
                "name": name,
                "key": shortcut.key,
                "modifier": shortcut.modifier.value,
                "display": str(shortcut),
                "description": shortcut.description,
            })
        
        return sorted(shortcuts, key=lambda s: s["name"])
