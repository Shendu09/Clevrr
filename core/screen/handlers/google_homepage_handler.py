"""Google Homepage Handler
=========================

Handles Google homepage (search.google.com or google.com).
"""

import logging
from typing import Optional, Dict, Any

from ..screen_types import ScreenType
from ..screen_handler import ScreenHandler

logger = logging.getLogger(__name__)


class GoogleHomepageHandler(ScreenHandler):
    """Handler for Google homepage."""
    
    SCREEN_TYPE = ScreenType.GOOGLE_HOMEPAGE
    
    # Approximate coordinates for Google search box
    SEARCH_BOX_COORDS = (960, 470)
    
    def can_handle(self, screen_type: ScreenType) -> bool:
        """Check if this is Google homepage."""
        return screen_type == ScreenType.GOOGLE_HOMEPAGE
    
    def handle(self, task: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Handle task on Google homepage.
        
        Args:
            task: Task description (e.g., "search for BTS V")
            screenshot: Current screenshot
            
        Returns:
            Result of handling
        """
        logger.info(f"Handling Google homepage task: {task}")
        
        # Extract search query
        query = self._extract_search_query(task)
        logger.debug(f"Search query: {query}")
        
        # Click search box and type
        if self.search(query):
            return {
                "success": True,
                "action_taken": f"Searched for: {query}",
                "next_screen": ScreenType.GOOGLE_SEARCH_RESULTS,
                "confidence": 0.95,
            }
        else:
            return {
                "success": False,
                "action_taken": None,
                "next_screen": ScreenType.GOOGLE_HOMEPAGE,
                "error": f"Failed to search for: {query}",
            }
    
    def _extract_search_query(self, task: str) -> str:
        """Extract search query from task.
        
        Args:
            task: Task description
            
        Returns:
            Search query
        """
        task_lower = task.lower()
        
        # Remove common prefixes
        for prefix in ["search for", "search", "find", "look up"]:
            if task_lower.startswith(prefix):
                return task[len(prefix):].strip()
        
        return task.strip()
    
    def search(self, query: str) -> bool:
        """Perform search on Google.
        
        Args:
            query: Search query
            
        Returns:
            True if search succeeded
        """
        if not self.executor:
            logger.warning("No executor available")
            return False
        
        try:
            # Click search box
            x, y = self.SEARCH_BOX_COORDS
            self.executor.click(x, y)
            
            # Type query
            self.executor.type_keys(query)
            
            # Press Enter
            self.executor.press_key("return")
            
            logger.info(f"Searched for: {query}")
            return True
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return False
    
    def should_retry(self, attempt: int, last_error: Optional[str]) -> bool:
        """Retry strategy."""
        return attempt < 2
    
    def get_recovery_action(self) -> Optional[str]:
        """Get recovery action."""
        return "click search box"
