"""Error Page Handler
====================

Handles error pages (404, 500, connection errors, etc.).
"""

import logging
from typing import Optional, Dict, Any

from ..screen_types import ScreenType
from ..screen_handler import ScreenHandler

logger = logging.getLogger(__name__)


class ErrorPageHandler(ScreenHandler):
    """Handler for error pages."""
    
    SCREEN_TYPE = ScreenType.ERROR_PAGE
    
    def can_handle(self, screen_type: ScreenType) -> bool:
        """Check if this is an error page."""
        return screen_type == ScreenType.ERROR_PAGE
    
    def handle(self, task: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Handle task when encountering error page.
        
        Args:
            task: Original task description
            screenshot: Current screenshot showing error
            
        Returns:
            Result of error handling
        """
        logger.warning(f"Encountered error page while handling: {task}")
        
        # Extract error type
        error_type = self._detect_error_type(screenshot)
        logger.debug(f"Error type detected: {error_type}")
        
        # Decide recovery action based on error type
        if error_type == "404":
            return self._handle_404()
        elif error_type == "500":
            return self._handle_server_error()
        elif error_type == "connection":
            return self._handle_connection_error()
        else:
            return self._handle_unknown_error()
    
    def _detect_error_type(self, screenshot: Optional[bytes]) -> str:
        """Detect what type of error this is.
        
        Args:
            screenshot: Error page screenshot
            
        Returns:
            Error type: "404", "500", "connection", "unknown"
        """
        # In real implementation, would use OCR or vision to read error message
        # For now, return based on heuristics
        return "unknown"
    
    def _handle_404(self) -> Dict[str, Any]:
        """Handle 404 Not Found error."""
        logger.info("Handling 404 error")
        
        if not self.executor:
            return {
                "success": False,
                "error": "404 Not Found - resource doesn't exist",
            }
        
        try:
            # Go back
            self.executor.press_key("backspace")  # Or Alt+Left
            
            return {
                "success": True,
                "action_taken": "Went back from 404 error",
                "next_screen": ScreenType.CHROME_BROWSER,
                "confidence": 0.85,
            }
        except Exception as e:
            logger.error(f"Failed to recover from 404: {e}")
            return {
                "success": False,
                "error": f"Failed to recover: {e}",
            }
    
    def _handle_server_error(self) -> Dict[str, Any]:
        """Handle 5xx Server error."""
        logger.info("Handling server error")
        
        if not self.executor:
            return {
                "success": False,
                "error": "Server error - please retry later",
            }
        
        try:
            # Refresh the page
            self.executor.key_combination("ctrl", "r")
            
            return {
                "success": True,
                "action_taken": "Refreshed page to recover from server error",
                "next_screen": ScreenType.CHROME_BROWSER,
                "confidence": 0.8,
            }
        except Exception as e:
            logger.error(f"Failed to recover from server error: {e}")
            return {
                "success": False,
                "error": f"Server error and refresh failed: {e}",
            }
    
    def _handle_connection_error(self) -> Dict[str, Any]:
        """Handle connection/network error."""
        logger.info("Handling connection error")
        
        if not self.executor:
            return {
                "success": False,
                "error": "Connection error - check network",
            }
        
        try:
            # Try to go back
            self.executor.key_combination("alt", "left")
            
            return {
                "success": True,
                "action_taken": "Went back from connection error",
                "next_screen": ScreenType.CHROME_BROWSER,
                "confidence": 0.8,
            }
        except Exception as e:
            logger.error(f"Failed to recover from connection error: {e}")
            return {
                "success": False,
                "error": f"Connection error and recovery failed: {e}",
            }
    
    def _handle_unknown_error(self) -> Dict[str, Any]:
        """Handle unknown error type."""
        logger.warning("Encountered unknown error page")
        
        return {
            "success": False,
            "error": "Unknown error encountered",
            "suggestion": "Try going back or closing and restarting",
        }
    
    def should_retry(self, attempt: int, last_error: Optional[str]) -> bool:
        """Retry strategy for error pages."""
        # Don't retry immediately after error
        return False
    
    def get_recovery_action(self) -> Optional[str]:
        """Get recovery action."""
        return "go back"
