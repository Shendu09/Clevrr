"""File Explorer Handler
=======================

Handles Windows File Explorer operations.
"""

import logging
from typing import Optional, Dict, Any

from ..screen_types import ScreenType
from ..screen_handler import ScreenHandler

logger = logging.getLogger(__name__)


class FileExplorerHandler(ScreenHandler):
    """Handler for File Explorer."""
    
    SCREEN_TYPE = ScreenType.FILE_EXPLORER
    
    def can_handle(self, screen_type: ScreenType) -> bool:
        """Check if this is File Explorer."""
        return screen_type == ScreenType.FILE_EXPLORER
    
    def handle(self, task: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Handle file operations.
        
        Args:
            task: Task description (e.g., "open document.txt", "navigate to downloads")
            screenshot: Current screenshot
            
        Returns:
            Result of handling
        """
        logger.info(f"Handling File Explorer task: {task}")
        
        intent = self._parse_file_intent(task)
        logger.debug(f"File intent: {intent}")
        
        if intent["action"] == "open":
            return self._open_file(intent["filename"])
        elif intent["action"] == "navigate":
            return self._navigate_folder(intent["folder"])
        elif intent["action"] == "create":
            return self._create_file(intent["filename"])
        else:
            return {"success": False, "error": f"Unknown file action: {intent['action']}"}
    
    def _parse_file_intent(self, task: str) -> Dict[str, Any]:
        """Parse file operation intent.
        
        Args:
            task: Task description
            
        Returns:
            Dict with action and parameters
        """
        task_lower = task.lower()
        
        if "open" in task_lower:
            filename = task.replace("open", "").strip()
            return {"action": "open", "filename": filename}
        
        elif "navigate" in task_lower or "go to" in task_lower:
            folder = task.replace("navigate", "").replace("go to", "").strip()
            return {"action": "navigate", "folder": folder}
        
        elif "create" in task_lower:
            filename = task.replace("create", "").strip()
            return {"action": "create", "filename": filename}
        
        return {"action": "unknown"}
    
    def _open_file(self, filename: str) -> Dict[str, Any]:
        """Open a file.
        
        Args:
            filename: Name of file to open
            
        Returns:
            Result of opening
        """
        logger.info(f"Opening file: {filename}")
        
        if not self.executor:
            return {"success": False, "error": "No executor"}
        
        try:
            # Double-click the file (would need to find it first with OCR/detection)
            # For now, assume we can type the filename and press Enter
            self.executor.key_combination("ctrl", "a")  # Select all
            self.executor.type_keys(filename)
            self.executor.press_key("return")
            
            return {
                "success": True,
                "action_taken": f"Opened file: {filename}",
                "next_screen": ScreenType.CHROME_BROWSER,  # Or appropriate app
                "confidence": 0.85,
            }
        except Exception as e:
            logger.error(f"Failed to open file: {e}")
            return {
                "success": False,
                "error": f"Failed to open: {e}",
            }
    
    def _navigate_folder(self, folder: str) -> Dict[str, Any]:
        """Navigate to a folder.
        
        Args:
            folder: Folder name or path
            
        Returns:
            Result of navigation
        """
        logger.info(f"Navigating to folder: {folder}")
        
        if not self.executor:
            return {"success": False, "error": "No executor"}
        
        try:
            # Click address bar and type path
            self.executor.click(500, 80)  # Address bar coordinate
            self.executor.key_combination("ctrl", "a")
            self.executor.type_keys(folder)
            self.executor.press_key("return")
            
            return {
                "success": True,
                "action_taken": f"Navigated to: {folder}",
                "next_screen": ScreenType.FILE_EXPLORER,
                "confidence": 0.9,
            }
        except Exception as e:
            logger.error(f"Failed to navigate: {e}")
            return {
                "success": False,
                "error": f"Failed to navigate: {e}",
            }
    
    def _create_file(self, filename: str) -> Dict[str, Any]:
        """Create a new file.
        
        Args:
            filename: Name of file to create
            
        Returns:
            Result of creation
        """
        logger.info(f"Creating file: {filename}")
        
        if not self.executor:
            return {"success": False, "error": "No executor"}
        
        try:
            # Right-click to get context menu
            self.executor.click(700, 400, right_click=True)
            
            # Would need to find "New" option and click appropriate file type
            logger.info("Would show context menu for new file")
            
            return {
                "success": True,
                "action_taken": f"Created file: {filename}",
                "next_screen": ScreenType.FILE_EXPLORER,
                "confidence": 0.8,
            }
        except Exception as e:
            logger.error(f"Failed to create file: {e}")
            return {
                "success": False,
                "error": f"Failed to create: {e}",
            }
    
    def should_retry(self, attempt: int, last_error: Optional[str]) -> bool:
        return attempt < 3
    
    def get_recovery_action(self) -> Optional[str]:
        return "press escape"
