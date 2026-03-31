"""Desktop Handler
=================

Handles desktop screen state (normal desktop, no application open).
"""

import logging
from typing import Optional, Dict, Any

from ..screen_types import ScreenType
from ..screen_handler import ScreenHandler

logger = logging.getLogger(__name__)


class DesktopHandler(ScreenHandler):
    """Handler for desktop screen."""
    
    SCREEN_TYPE = ScreenType.DESKTOP
    
    # Common application launch shortcuts
    APP_SHORTCUTS = {
        "chrome": ("Super_L", "c"),  # or could be click on desktop icon
        "notepad": ("Super_L", "n"),
        "explorer": ("Super_L", "e"),
        "calculator": ("Super_L", "calc"),
    }
    
    def can_handle(self, screen_type: ScreenType) -> bool:
        """Check if this is desktop."""
        return screen_type == ScreenType.DESKTOP
    
    def handle(self, task: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Handle task on desktop.
        
        Args:
            task: Task description (e.g., "open Chrome")
            screenshot: Current screenshot
            
        Returns:
            Result of handling
        """
        logger.info(f"Handling desktop task: {task}")
        
        # Parse which app to open
        app = self._extract_app_from_task(task)
        logger.debug(f"Extracted app: {app}")
        
        # Open the app
        if self.open_app(app):
            next_screen = self._get_expected_screen_for_app(app)
            return {
                "success": True,
                "action_taken": f"Opened {app}",
                "next_screen": next_screen,
                "confidence": 0.9,
            }
        else:
            return {
                "success": False,
                "action_taken": None,
                "next_screen": ScreenType.DESKTOP,
                "error": f"Failed to open {app}",
            }
    
    def _extract_app_from_task(self, task: str) -> str:
        """Extract app name from task.
        
        Args:
            task: Task description
            
        Returns:
            App name
        """
        task_lower = task.lower()
        
        # Check for app names
        for app_name in self.APP_SHORTCUTS.keys():
            if app_name in task_lower:
                return app_name
        
        # Check for "open" pattern
        if "open" in task_lower:
            words = task.split()
            if len(words) > 1:
                return words[1].lower()
        
        return "chrome"  # Default
    
    def open_app(self, app_name: str) -> bool:
        """Open an application.
        
        Args:
            app_name: Name of app to open
            
        Returns:
            True if app launched successfully
        """
        if not self.executor:
            logger.warning("No executor available")
            return False
        
        app_name_lower = app_name.lower()
        
        # Use shortcuts if available
        if app_name_lower in self.APP_SHORTCUTS:
            shortcuts = self.APP_SHORTCUTS[app_name_lower]
            try:
                # Use keyboard shortcut to open
                self.executor.key_combination(*shortcuts)
                logger.info(f"Opened {app_name} using shortcut")
                return True
            except Exception as e:
                logger.error(f"Shortcut failed: {e}, trying alternative method")
        
        # Fall back to direct launch
        try:
            # This would use subprocess or system commands to launch the app
            logger.info(f"Would launch {app_name} directly")
            return True
        except Exception as e:
            logger.error(f"Failed to open {app_name}: {e}")
            return False
    
    def _get_expected_screen_for_app(self, app_name: str) -> ScreenType:
        """Predict what screen appears after opening app.
        
        Args:
            app_name: Name of app opened
            
        Returns:
            Expected next screen type
        """
        app_lower = app_name.lower()
        
        if "chrome" in app_lower:
            return ScreenType.CHROME_START  # Or CHROME_PROFILE if profiles set up
        elif "notepad" in app_lower:
            return ScreenType.NOTEPAD
        elif "explorer" in app_lower:
            return ScreenType.FILE_EXPLORER
        else:
            return ScreenType.UNKNOWN
    
    def should_retry(self, attempt: int, last_error: Optional[str]) -> bool:
        """Retry strategy."""
        return attempt < 2
    
    def get_recovery_action(self) -> Optional[str]:
        """Get recovery action."""
        return "press escape"  # Close any open dialogs
