"""YouTube Handler
=================

Handles YouTube homepage and video watching.
"""

import logging
from typing import Optional, Dict, Any

from ..screen_types import ScreenType
from ..screen_handler import ScreenHandler

logger = logging.getLogger(__name__)


class YouTubeHandler(ScreenHandler):
    """Handler for YouTube pages."""
    
    SCREEN_TYPE = ScreenType.YOUTUBE_HOME
    
    # Search box coordinates on YouTube
    SEARCH_BOX_COORDS = (960, 80)
    
    def can_handle(self, screen_type: ScreenType) -> bool:
        """Check if this is YouTube."""
        return screen_type in [ScreenType.YOUTUBE_HOME, ScreenType.YOUTUBE_VIDEO]
    
    def handle(self, task: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Handle task on YouTube.
        
        Args:
            task: Task description (e.g., "search for BTS V", "play video")
            screenshot: Current screenshot
            
        Returns:
            Result of handling
        """
        logger.info(f"Handling YouTube task: {task}")
        
        intent = self._parse_youtube_intent(task)
        logger.debug(f"YouTube intent: {intent}")
        
        if intent["action"] == "search":
            return self._search_youtube(intent["query"])
        elif intent["action"] == "play":
            return self._play_video()
        elif intent["action"] == "click_video":
            return self._click_video(intent["title"])
        else:
            return {"success": False, "error": f"Unknown YouTube action: {intent['action']}"}
    
    def _parse_youtube_intent(self, task: str) -> Dict[str, Any]:
        """Parse YouTube task intent.
        
        Args:
            task: Task description
            
        Returns:
            Dict with action and parameters
        """
        task_lower = task.lower()
        
        if any(x in task_lower for x in ["search", "find"]):
            query = task.replace("search for", "").replace("find", "").strip()
            return {"action": "search", "query": query}
        
        elif any(x in task_lower for x in ["play", "watch"]):
            return {"action": "play"}
        
        elif "click" in task_lower:
            title = task.replace("click", "").strip()
            return {"action": "click_video", "title": title}
        
        return {"action": "unknown"}
    
    def _search_youtube(self, query: str) -> Dict[str, Any]:
        """Search on YouTube.
        
        Args:
            query: Search query
            
        Returns:
            Result of search
        """
        if not self.executor:
            return {"success": False, "error": "No executor"}
        
        try:
            # Click search box
            x, y = self.SEARCH_BOX_COORDS
            self.executor.click(x, y)
            
            # Type query
            self.executor.type_keys(query)
            self.executor.press_key("return")
            
            logger.info(f"Searched YouTube for: {query}")
            return {
                "success": True,
                "action_taken": f"Searched for: {query}",
                "next_screen": ScreenType.YOUTUBE_HOME,
                "confidence": 0.9,
            }
        except Exception as e:
            logger.error(f"YouTube search failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _play_video(self) -> Dict[str, Any]:
        """Play a video."""
        if not self.executor:
            return {"success": False, "error": "No executor"}
        
        try:
            # Space bar to play/pause
            self.executor.press_key("space")
            logger.info("Pressed play")
            return {
                "success": True,
                "action_taken": "Started video playback",
                "next_screen": ScreenType.YOUTUBE_VIDEO,
                "confidence": 0.95,
            }
        except Exception as e:
            logger.error(f"Failed to play: {e}")
            return {"success": False, "error": str(e)}
    
    def _click_video(self, title: str) -> Dict[str, Any]:
        """Click a video by title."""
        logger.warning("Video clicking with title matching not yet implemented")
        return {
            "success": False,
            "error": "Video matching requires OCR/detection",
        }
    
    def should_retry(self, attempt: int, last_error: Optional[str]) -> bool:
        return attempt < 3
    
    def get_recovery_action(self) -> Optional[str]:
        return "go home"
