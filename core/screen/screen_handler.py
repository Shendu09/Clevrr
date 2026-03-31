"""Screen Handler Base Class
============================

Base class for screen-specific handlers.
Each screen type gets its own handler implementing this interface.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from .screen_types import ScreenType

logger = logging.getLogger(__name__)


class ScreenHandler(ABC):
    """Base class for screen-specific handlers."""
    
    # Must be set by subclasses
    SCREEN_TYPE: ScreenType = ScreenType.UNKNOWN
    
    def __init__(self, executor=None, vision_agent=None):
        """Initialize handler.
        
        Args:
            executor: Executor agent for actions
            vision_agent: Vision agent for analysis
        """
        self.executor = executor
        self.vision_agent = vision_agent
        logger.debug(f"Initialized handler for {self.SCREEN_TYPE}")
    
    @abstractmethod
    def can_handle(self, screen_type: ScreenType) -> bool:
        """Check if this handler can handle the screen type.
        
        Args:
            screen_type: Detected screen type
            
        Returns:
            True if this handler can handle it
        """
        pass
    
    @abstractmethod
    def handle(self, task: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Handle task on this screen.
        
        Args:
            task: Task description (e.g., "search for cat videos")
            screenshot: Current screenshot
            
        Returns:
            Result dict with keys:
                - success: bool
                - action_taken: str (description of what was done)
                - next_screen: ScreenType (predicted next state)
                - confidence: float
                - error: Optional error message
        """
        pass
    
    def extract_task_intent(self, task: str) -> Dict[str, Any]:
        """Parse task to extract intent.
        
        Args:
            task: Task description
            
        Returns:
            Dict with parsed intent structure
        """
        return {
            "original": task,
            "action": task.lower(),
            "target": None,
        }
    
    def should_retry(self, attempt: int, last_error: Optional[str]) -> bool:
        """Check if we should retry after failure.
        
        Args:
            attempt: Which attempt (1, 2, 3...)
            last_error: Error from last attempt
            
        Returns:
            True if should retry
        """
        # By default, retry up to 3 times
        return attempt < 3
    
    def get_recovery_action(self) -> Optional[str]:
        """Get recovery action if stuck on this screen.
        
        Returns:
            Recovery action (e.g., "press escape", "click back button")
        """
        return None  # Subclasses override
    
    def wait_for_element(self, element_name: str, timeout_sec: int = 5) -> bool:
        """Wait for an element to appear on screen.
        
        Args:
            element_name: Name/description of element
            timeout_sec: Timeout in seconds
            
        Returns:
            True if element appeared
        """
        # Subclasses override with specific detection logic
        return False
    
    def click_element(self, element_name: str) -> bool:
        """Click an element on this screen.
        
        Args:
            element_name: Name/description of element (e.g., "profile V")
            
        Returns:
            True if click succeeded
        """
        if not self.executor:
            logger.warning("No executor available for click")
            return False
        
        # Subclasses override with specific coordinates
        return False
    
    def type_text(self, text: str) -> bool:
        """Type text on this screen.
        
        Args:
            text: Text to type
            
        Returns:
            True if typing succeeded
        """
        if not self.executor:
            logger.warning("No executor available for typing")
            return False
        
        try:
            self.executor.type_keys(text)
            return True
        except Exception as e:
            logger.error(f"Failed to type: {e}")
            return False
    
    def press_key(self, key: str) -> bool:
        """Press a keyboard key.
        
        Args:
            key: Key name (e.g., "escape", "enter", "backspace")
            
        Returns:
            True if key press succeeded
        """
        if not self.executor:
            logger.warning("No executor available for key press")
            return False
        
        try:
            self.executor.press_key(key)
            return True
        except Exception as e:
            logger.error(f"Failed to press key: {e}")
            return False
    
    def get_log_context(self) -> Dict[str, Any]:
        """Get context for logging."""
        return {
            "handler": self.__class__.__name__,
            "screen_type": str(self.SCREEN_TYPE),
        }


class ScreenHandlerRegistry:
    """Registry of all available screen handlers."""
    
    def __init__(self):
        """Initialize handler registry."""
        self.handlers: Dict[ScreenType, ScreenHandler] = {}
        logger.info("ScreenHandlerRegistry initialized")
    
    def register(self, handler: ScreenHandler) -> None:
        """Register a handler.
        
        Args:
            handler: Handler instance
        """
        screen_type = handler.SCREEN_TYPE
        self.handlers[screen_type] = handler
        logger.info(f"Registered handler for {screen_type}")
    
    def get_handler(self, screen_type: ScreenType) -> Optional[ScreenHandler]:
        """Get handler for screen type.
        
        Args:
            screen_type: Type of screen
            
        Returns:
            Handler or None if not registered
        """
        return self.handlers.get(screen_type)
    
    def has_handler(self, screen_type: ScreenType) -> bool:
        """Check if handler exists for screen type.
        
        Args:
            screen_type: Type of screen
            
        Returns:
            True if handler registered
        """
        return screen_type in self.handlers
    
    def get_all_handlers(self) -> Dict[ScreenType, ScreenHandler]:
        """Get all registered handlers.
        
        Returns:
            Dict of screen_type -> handler
        """
        return self.handlers.copy()
