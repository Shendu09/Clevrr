"""Screen Router
===============

Routes tasks to appropriate screen handlers based on detected screen state.
Handles state transitions and recovery logic.
"""

import logging
from typing import Optional, Dict, Any

from .screen_types import ScreenType
from .screen_detector import ScreenDetector, ScreenDetectionResult
from .screen_handler import ScreenHandler, ScreenHandlerRegistry

logger = logging.getLogger(__name__)


class ScreenRouter:
    """Routes tasks to appropriate handlers based on screen state."""
    
    def __init__(self, detector: ScreenDetector, handler_registry: ScreenHandlerRegistry):
        """Initialize screen router.
        
        Args:
            detector: ScreenDetector instance
            handler_registry: ScreenHandlerRegistry instance
        """
        self.detector = detector
        self.registry = handler_registry
        self.last_screen_type: Optional[ScreenType] = None
        self.stuck_count = 0  # Counter for stuck state detection
        logger.info("ScreenRouter initialized")
    
    @property
    def handlers(self) -> ScreenHandlerRegistry:
        """Get handlers registry (for backward compatibility)."""
        return self.registry
    
    def route_task(self, task: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Route task to appropriate handler.
        
        Args:
            task: Task description
            screenshot: Current screenshot
            
        Returns:
            Result from handler
        """
        # Detect current screen
        detection = self.detector.detect(screenshot)
        screen_type = detection.screen_type
        
        logger.info(
            f"Screen detected: {screen_type} (confidence: {detection.confidence})",
            extra={"screen_type": str(screen_type)}
        )
        
        # Check if stuck on same screen
        if screen_type == self.last_screen_type:
            self.stuck_count += 1
        else:
            self.stuck_count = 0
        
        self.last_screen_type = screen_type
        
        # Get handler for this screen
        handler = self.registry.get_handler(screen_type)
        
        if not handler:
            logger.warning(f"No handler for screen type: {screen_type}")
            return {
                "success": False,
                "error": f"No handler for {screen_type}",
                "screen_type": str(screen_type),
                "attempt": 1,
            }
        
        # Execute task on this screen
        result = handler.handle(task, screenshot)
        result["screen_type"] = str(screen_type)
        result["detection_confidence"] = detection.confidence
        
        return result
    
    def is_stuck(self, threshold: int = 3) -> bool:
        """Check if stuck on same screen.
        
        Args:
            threshold: How many times on same screen to consider stuck
            
        Returns:
            True if stuck
        """
        return self.stuck_count >= threshold
    
    def get_stuck_recovery_action(self) -> Optional[str]:
        """Get recovery action for stuck state.
        
        Returns:
            Recovery action to try
        """
        if not self.last_screen_type:
            return None
        
        handler = self.registry.get_handler(self.last_screen_type)
        if not handler:
            return None
        
        return handler.get_recovery_action()
    
    def get_screen_summary(self) -> Dict[str, Any]:
        """Get summary of current screen state.
        
        Returns:
            Summary dict
        """
        return {
            "current_screen": str(self.last_screen_type) if self.last_screen_type else "unknown",
            "stuck_count": self.stuck_count,
            "is_stuck": self.is_stuck(),
            "handlers_available": list(self.registry.get_all_handlers().keys()),
        }


class ScreenRouterWithRetry(ScreenRouter):
    """Extended screen router with retry logic."""
    
    def __init__(self, detector: ScreenDetector, handler_registry: ScreenHandlerRegistry, max_retries: int = 3):
        """Initialize router with retry support.
        
        Args:
            detector: ScreenDetector instance
            handler_registry: ScreenHandlerRegistry instance
            max_retries: Maximum retries before giving up
        """
        super().__init__(detector, handler_registry)
        self.max_retries = max_retries
        self.attempt_count = 0
        self.last_error: Optional[str] = None
        logger.info(f"ScreenRouterWithRetry initialized (max_retries={max_retries})")
    
    def route_task_with_retry(self, task: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Route task with retry logic.
        
        Args:
            task: Task description
            screenshot: Current screenshot
            
        Returns:
            Result from handler (or failure after max retries)
        """
        self.attempt_count = 0
        
        while self.attempt_count < self.max_retries:
            self.attempt_count += 1
            
            logger.info(f"Attempt {self.attempt_count}/{self.max_retries} for task: {task}")
            
            result = self.route_task(task, screenshot)
            result["attempt"] = self.attempt_count
            
            if result.get("success"):
                logger.info(f"Task succeeded on attempt {self.attempt_count}")
                return result
            
            self.last_error = result.get("error", "Unknown error")
            
            # Check if handler wants to retry
            handler = self.registry.get_handler(self.last_screen_type)
            if handler and not handler.should_retry(self.attempt_count, self.last_error):
                logger.info("Handler indicates no retry should be attempted")
                return result
            
            # Try recovery action if stuck
            if self.is_stuck():
                recovery = self.get_stuck_recovery_action()
                if recovery:
                    logger.info(f"Attempting recovery: {recovery}")
                    # Recovery action would be executed here
        
        logger.error(f"Task failed after {self.max_retries} attempts")
        return {
            "success": False,
            "error": f"Failed after {self.max_retries} attempts. Last error: {self.last_error}",
            "attempts": self.attempt_count,
        }
    
    def reset_attempt_counter(self) -> None:
        """Reset retry counter for new task."""
        self.attempt_count = 0
        self.last_error = None
