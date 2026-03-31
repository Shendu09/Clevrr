"""Google Search Results Handler
===============================

Handles Google search results page.
"""

import logging
from typing import Optional, Dict, Any

from ..screen_types import ScreenType
from ..screen_handler import ScreenHandler

logger = logging.getLogger(__name__)


class GoogleSearchResultsHandler(ScreenHandler):
    """Handler for Google search results page."""
    
    SCREEN_TYPE = ScreenType.GOOGLE_SEARCH_RESULTS
    
    def can_handle(self, screen_type: ScreenType) -> bool:
        """Check if this is search results page."""
        return screen_type == ScreenType.GOOGLE_SEARCH_RESULTS
    
    def handle(self, task: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Handle task on search results.
        
        Args:
            task: Task description (e.g., "click first result", "click V")
            screenshot: Current screenshot
            
        Returns:
            Result of handling
        """
        logger.info(f"Handling search results task: {task}")
        
        # Parse what link to click
        intent = self._parse_click_intent(task)
        logger.debug(f"Click intent: {intent}")
        
        if intent["action"] == "click_first":
            return self._click_first_result()
        elif intent["action"] == "click_by_text":
            return self._click_by_text(intent["text"], screenshot)
        elif intent["action"] == "new_search":
            return self._new_search(intent["query"])
        else:
            return {
                "success": False,
                "error": f"Unknown action for search results: {intent['action']}",
            }
    
    def _parse_click_intent(self, task: str) -> Dict[str, Any]:
        """Parse what to click on search results.
        
        Args:
            task: Task description
            
        Returns:
            Dict with action and parameters
        """
        task_lower = task.lower()
        
        # Click first result
        if any(x in task_lower for x in ["first result", "first link", "first"]):
            return {"action": "click_first"}
        
        # Click by text (e.g., "click BTS", "click V")
        if "click" in task_lower:
            text = task.replace("click", "").strip()
            return {"action": "click_by_text", "text": text}
        
        # New search
        if any(x in task_lower for x in ["search again", "new search", "search for"]):
            query = task.replace("search for", "").replace("search", "").strip()
            return {"action": "new_search", "query": query}
        
        return {"action": "unknown"}
    
    def _click_first_result(self) -> Dict[str, Any]:
        """Click first search result.
        
        Returns:
            Result of action
        """
        if not self.executor:
            return {"success": False, "error": "No executor"}
        
        try:
            # First result is usually at these coordinates (rough estimate)
            self.executor.click(500, 200)  # Approximate first result coords
            
            logger.info("Clicked first search result")
            return {
                "success": True,
                "action_taken": "Clicked first search result",
                "next_screen": ScreenType.CHROME_BROWSER,  # Will navigate to result
                "confidence": 0.85,
            }
        except Exception as e:
            logger.error(f"Failed to click first result: {e}")
            return {
                "success": False,
                "error": f"Failed to click: {e}",
            }
    
    def _click_by_text(self, text: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Click result by matching text.
        
        Args:
            text: Text to search for
            screenshot: Current screenshot
            
        Returns:
            Result of action
        """
        logger.info(f"Looking for and clicking: {text}")
        
        # This would use OCR or image recognition to find the text
        # For now, return that it needs detection
        return {
            "success": False,
            "error": "Text matching not yet implemented (requires OCR)",
            "next_action": "Need to implement OCR for finding text in results",
        }
    
    def _new_search(self, query: str) -> Dict[str, Any]:
        """Perform new search.
        
        Args:
            query: New search query
            
        Returns:
            Result of action
        """
        if not self.executor:
            return {"success": False, "error": "No executor"}
        
        try:
            # Click search box at top of results page
            self.executor.click(960, 80)
            
            # Clear and type new query
            self.executor.key_combination("ctrl", "a")
            self.executor.type_keys(query)
            self.executor.press_key("return")
            
            logger.info(f"Performed new search: {query}")
            return {
                "success": True,
                "action_taken": f"Searched for: {query}",
                "next_screen": ScreenType.GOOGLE_SEARCH_RESULTS,
                "confidence": 0.9,
            }
        except Exception as e:
            logger.error(f"New search failed: {e}")
            return {
                "success": False,
                "error": f"Failed to search: {e}",
            }
    
    def should_retry(self, attempt: int, last_error: Optional[str]) -> bool:
        """Retry strategy."""
        return attempt < 3
    
    def get_recovery_action(self) -> Optional[str]:
        """Get recovery action."""
        return "go back"
