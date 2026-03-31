"""Chrome Browser Handler
========================

Handles the Chrome browser window (normal browsing state).
"""

import logging
from typing import Optional, Dict, Any

from ..screen_types import ScreenType
from ..screen_handler import ScreenHandler

logger = logging.getLogger(__name__)


class ChromeBrowserHandler(ScreenHandler):
    """Handler for Chrome browser window."""
    
    SCREEN_TYPE = ScreenType.CHROME_BROWSER
    
    def can_handle(self, screen_type: ScreenType) -> bool:
        """Check if this is a Chrome browser screen."""
        return screen_type == ScreenType.CHROME_BROWSER
    
    def handle(self, task: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Handle task in Chrome browser.
        
        Args:
            task: Task description (e.g., "go to google.com")
            screenshot: Current screenshot
            
        Returns:
            Result of handling
        """
        logger.info(f"Handling Chrome browser task: {task}")
        
        intent = self._parse_intent(task)
        logger.debug(f"Parsed intent: {intent}")
        
        if intent["action"] == "navigate":
            return self._handle_navigation(intent["url"], screenshot)
        elif intent["action"] == "search":
            return self._handle_search(intent["query"], screenshot)
        elif intent["action"] == "click":
            return self._handle_click(intent["target"], screenshot)
        else:
            return {
                "success": False,
                "action_taken": None,
                "next_screen": ScreenType.CHROME_BROWSER,
                "error": f"Unknown action: {intent['action']}",
            }
    
    def _parse_intent(self, task: str) -> Dict[str, Any]:
        """Parse browser task intent.
        
        Args:
            task: Task description
            
        Returns:
            Dict with action and parameters
        """
        task_lower = task.lower()
        
        # Navigation detection
        if any(x in task_lower for x in ["go to", "navigate", "visit", "open"]):
            # Extract URL
            url = self._extract_url(task)
            return {"action": "navigate", "url": url}
        
        # Search detection
        elif any(x in task_lower for x in ["search", "find", "look up"]):
            query = task.replace("search for", "").replace("search", "").strip()
            return {"action": "search", "query": query}
        
        # Click detection
        elif any(x in task_lower for x in ["click", "press"]):
            target = task.replace("click", "").replace("press", "").strip()
            return {"action": "click", "target": target}
        
        return {"action": "unknown"}
    
    def _extract_url(self, task: str) -> str:
        """Extract URL from task.
        
        Args:
            task: Task description
            
        Returns:
            URL to navigate to
        """
        # Simple extraction - could be more sophisticated
        if "google.com" in task:
            return "https://www.google.com"
        elif "youtube.com" in task:
            return "https://www.youtube.com"
        else:
            # Assume it's in the task
            words = task.split()
            for word in words:
                if "." in word and not word.endswith("."):
                    return f"https://{word}"
        
        return "https://www.google.com"
    
    def _handle_navigation(self, url: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Navigate to URL.
        
        Args:
            url: URL to navigate to
            screenshot: Current screenshot
            
        Returns:
            Result of navigation
        """
        if not self.executor:
            return {"success": False, "error": "No executor"}
        
        try:
            # Click address bar
            self.executor.click(960, 60)  # Address bar coordinates
            
            # Clear and type URL
            self.executor.key_combination("ctrl", "a")  # Select all
            self.executor.type_keys(url)
            self.executor.press_key("return")
            
            logger.info(f"Navigated to {url}")
            return {
                "success": True,
                "action_taken": f"Navigated to {url}",
                "next_screen": ScreenType.GOOGLE_HOMEPAGE if "google" in url else ScreenType.CHROME_BROWSER,
                "confidence": 0.9,
            }
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return {
                "success": False,
                "error": f"Failed to navigate: {e}",
            }
    
    def _handle_search(self, query: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Perform search.
        
        Args:
            query: Search query
            screenshot: Current screenshot
            
        Returns:
            Result of search
        """
        if not self.executor:
            return {"success": False, "error": "No executor"}
        
        try:
            # Navigate to Google if not already there
            self.executor.click(960, 60)
            self.executor.key_combination("ctrl", "a")
            self.executor.type_keys("https://www.google.com")
            self.executor.press_key("return")
            
            # Wait for page load
            import time
            time.sleep(2)
            
            # Type in search box and search
            self.executor.type_keys(query)
            self.executor.press_key("return")
            
            logger.info(f"Searched for: {query}")
            return {
                "success": True,
                "action_taken": f"Searched for: {query}",
                "next_screen": ScreenType.GOOGLE_SEARCH_RESULTS,
                "confidence": 0.9,
            }
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {
                "success": False,
                "error": f"Failed to search: {e}",
            }
    
    def _handle_click(self, target: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Click an element.
        
        Args:
            target: Element to click
            screenshot: Current screenshot
            
        Returns:
            Result of click
        """
        return {
            "success": False,
            "error": "Click handler not yet implemented (requires OCR/detection)",
        }
    
    def should_retry(self, attempt: int, last_error: Optional[str]) -> bool:
        """Retry strategy for browser operations."""
        return attempt < 3
    
    def get_recovery_action(self) -> Optional[str]:
        """Get recovery action if stuck."""
        return "reload page"  # Use Ctrl+R to reload
