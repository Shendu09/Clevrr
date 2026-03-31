"""Login Page Handler
====================

Handles login/authentication pages.
"""

import logging
from typing import Optional, Dict, Any

from ..screen_types import ScreenType
from ..screen_handler import ScreenHandler

logger = logging.getLogger(__name__)


class LoginPageHandler(ScreenHandler):
    """Handler for login pages."""
    
    SCREEN_TYPE = ScreenType.LOGIN_PAGE
    
    # Common login form coordinates (approximate)
    USERNAME_FIELD_COORDS = (960, 250)
    PASSWORD_FIELD_COORDS = (960, 350)
    LOGIN_BUTTON_COORDS = (960, 450)
    
    def can_handle(self, screen_type: ScreenType) -> bool:
        """Check if this is a login page."""
        return screen_type == ScreenType.LOGIN_PAGE
    
    def handle(self, task: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Handle login task.
        
        Args:
            task: Task description (e.g., "login with username", "enter password")
            screenshot: Current screenshot
            
        Returns:
            Result of handling
        """
        logger.info(f"Handling login task: {task}")
        
        # Parse login intent
        intent = self._parse_login_intent(task)
        logger.debug(f"Login intent: {intent}")
        
        if intent["action"] == "login":
            return self._login(intent.get("username"), intent.get("password"))
        elif intent["action"] == "enter_username":
            return self._enter_field("username", intent.get("value"))
        elif intent["action"] == "enter_password":
            return self._enter_field("password", intent.get("value"))
        else:
            return {
                "success": False,
                "error": f"Unknown login action: {intent['action']}",
            }
    
    def _parse_login_intent(self, task: str) -> Dict[str, Any]:
        """Parse login task intent.
        
        Args:
            task: Task description
            
        Returns:
            Dict with action and parameters
        """
        task_lower = task.lower()
        
        if "login" in task_lower:
            return {
                "action": "login",
                # In a real system, credentials would come from secure storage
                "username": "example_user",
                "password": "example_pass",
            }
        elif "username" in task_lower or "email" in task_lower:
            value = task.split(":")[-1].strip() if ":" in task else ""
            return {
                "action": "enter_username",
                "value": value,
            }
        elif "password" in task_lower:
            value = task.split(":")[-1].strip() if ":" in task else ""
            return {
                "action": "enter_password",
                "value": value,
            }
        
        return {"action": "unknown"}
    
    def _login(self, username: Optional[str], password: Optional[str]) -> Dict[str, Any]:
        """Perform login.
        
        Args:
            username: Username
            password: Password
            
        Returns:
            Result of login
        """
        if not self.executor:
            return {"success": False, "error": "No executor"}
        
        if not username or not password:
            return {
                "success": False,
                "error": "Username and password required",
            }
        
        try:
            # Click username field
            self.executor.click(*self.USERNAME_FIELD_COORDS)
            self.executor.type_keys(username)
            
            # Click password field
            self.executor.click(*self.PASSWORD_FIELD_COORDS)
            self.executor.type_keys(password)
            
            # Click login button
            self.executor.click(*self.LOGIN_BUTTON_COORDS)
            
            logger.info(f"Logged in as: {username}")
            return {
                "success": True,
                "action_taken": f"Logged in",
                "next_screen": ScreenType.CHROME_BROWSER,  # After login
                "confidence": 0.9,
            }
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return {
                "success": False,
                "error": f"Login failed: {e}",
            }
    
    def _enter_field(self, field_type: str, value: str) -> Dict[str, Any]:
        """Enter a login form field.
        
        Args:
            field_type: "username" or "password"
            value: Value to enter
            
        Returns:
            Result of entering field
        """
        if not self.executor:
            return {"success": False, "error": "No executor"}
        
        try:
            if field_type == "username":
                self.executor.click(*self.USERNAME_FIELD_COORDS)
            elif field_type == "password":
                self.executor.click(*self.PASSWORD_FIELD_COORDS)
            else:
                return {"success": False, "error": f"Unknown field: {field_type}"}
            
            if value:
                self.executor.type_keys(value)
            
            logger.info(f"Entered {field_type}")
            return {
                "success": True,
                "action_taken": f"Entered {field_type}",
                "next_screen": ScreenType.LOGIN_PAGE,
                "confidence": 0.9,
            }
        except Exception as e:
            logger.error(f"Failed to enter {field_type}: {e}")
            return {
                "success": False,
                "error": f"Failed to enter {field_type}: {e}",
            }
    
    def should_retry(self, attempt: int, last_error: Optional[str]) -> bool:
        return attempt < 3
    
    def get_recovery_action(self) -> Optional[str]:
        return "clear fields"  # Clear and retry
