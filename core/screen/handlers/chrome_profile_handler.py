"""Chrome Profile Selection Handler
===================================

Handles the Chrome "Who's using Chrome?" profile selection screen.
"""

import logging
from typing import Optional, Dict, Any

from ..screen_types import ScreenType
from ..screen_handler import ScreenHandler

logger = logging.getLogger(__name__)


class ChromeProfileHandler(ScreenHandler):
    """Handler for Chrome profile selection screen."""
    
    SCREEN_TYPE = ScreenType.CHROME_PROFILE
    
    # Approximate coordinates for common profiles (adjust for your screen)
    # These would be calibrated during setup
    PROFILE_COORDINATES = {
        "bushra": (450, 540),
        "v": (960, 540),
        "default": (960, 540),
        "add": (1450, 540),
    }
    
    def can_handle(self, screen_type: ScreenType) -> bool:
        """Check if this is a Chrome profile screen."""
        return screen_type == ScreenType.CHROME_PROFILE
    
    def handle(self, task: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Handle task on Chrome profile selection screen.
        
        Args:
            task: Task description
            screenshot: Current screenshot
            
        Returns:
            Result of handling
        """
        logger.info(f"Handling Chrome profile selection for: {task}")
        
        # Parse which profile to select
        profile = self._extract_profile_from_task(task)
        logger.debug(f"Extracted profile: {profile}")
        
        # Click the profile
        if self.click_profile(profile):
            return {
                "success": True,
                "action_taken": f"Selected Chrome profile: {profile}",
                "next_screen": ScreenType.CHROME_BROWSER,
                "confidence": 0.95,
            }
        else:
            return {
                "success": False,
                "action_taken": None,
                "next_screen": ScreenType.CHROME_PROFILE,
                "confidence": 0.8,
                "error": f"Failed to click profile: {profile}",
            }
    
    def _extract_profile_from_task(self, task: str) -> str:
        """Extract profile name from task.
        
        Args:
            task: Task description
            
        Returns:
            Profile name to select
        """
        task_lower = task.lower()
        
        # Check for explicit profile names
        for profile_name in self.PROFILE_COORDINATES.keys():
            if profile_name in task_lower:
                return profile_name
        
        # Default to profile 'V' or 'default'
        return "v"
    
    def click_profile(self, profile_name: str) -> bool:
        """Click a profile.
        
        Args:
            profile_name: Name of profile to click
            
        Returns:
            True if click succeeded
        """
        if not self.executor:
            logger.warning("No executor available")
            return False
        
        # Get coordinates
        coords = self.PROFILE_COORDINATES.get(profile_name.lower())
        if not coords:
            logger.warning(f"Unknown profile: {profile_name}")
            return False
        
        x, y = coords
        logger.info(f"Clicking profile '{profile_name}' at ({x}, {y})")
        
        try:
            self.executor.click(x, y)
            return True
        except Exception as e:
            logger.error(f"Failed to click profile: {e}")
            return False
    
    def should_retry(self, attempt: int, last_error: Optional[str]) -> bool:
        """Retry strategy for profile selection."""
        # Retry up to 2 times
        return attempt < 2
    
    def get_recovery_action(self) -> Optional[str]:
        """Get recovery action if stuck."""
        # If stuck on profile selection, press Escape to go back
        return "press escape"
    
    def wait_for_element(self, element_name: str, timeout_sec: int = 5) -> bool:
        """Wait for profile element to appear."""
        # This would use image detection to wait for profile button
        # For now, return immediate true
        return True
