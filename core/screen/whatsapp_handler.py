"""WhatsApp Handler
==================

Handles interactions with WhatsApp application.
Supports:
- Opening WhatsApp
- Finding and opening chats
- Sending messages
"""

import logging
import re
from typing import Optional, Dict, Any

from .screen_types import ScreenType
from .screen_handler import ScreenHandler

logger = logging.getLogger(__name__)


class WhatsAppHandler(ScreenHandler):
    """Handler for WhatsApp interactions."""
    
    SCREEN_TYPE = ScreenType.WHATSAPP
    
    # WhatsApp element coordinates (approximate, may need calibration)
    SEARCH_BOX_COORDS = (960, 100)  # Search/search contacts
    MESSAGE_INPUT_COORDS = (960, 900)  # Message input field
    SEND_BUTTON_COORDS = (1900, 900)  # Send button
    
    def __init__(self, executor=None, vision_agent=None):
        """Initialize WhatsApp handler."""
        super().__init__(executor, vision_agent)
        self._recipient_found = False
        self._message_typed = False
        self._previous_action = None
    
    def can_handle(self, screen_type: ScreenType) -> bool:
        """Check if can handle WhatsApp screens."""
        return screen_type in [
            ScreenType.WHATSAPP,
            ScreenType.WHATSAPP_CHAT,
            ScreenType.WHATSAPP_CONTACT,
        ]
    
    async def get_next_action(
        self,
        task: str,
        screen_state: Any
    ) -> Optional[Dict[str, Any]]:
        """Get next action for WhatsApp task (event loop interface).
        
        Args:
            task: Task description (e.g., "send hi to Papa")
            screen_state: Current screen state
            
        Returns:
            Action dict or None if done
        """
        logger.info(f"WhatsApp get_next_action: {task}")
        
        try:
            # Parse task intent
            recipient = self._extract_recipient(task)
            message = self._extract_message(task)
            
            logger.debug(f"Recipient: {recipient}, Message: {message}")
            
            if not recipient or not message:
                return None  # Can't process task
            
            # Get current screen type
            screen_type = screen_state.screen_type if hasattr(screen_state, 'screen_type') else str(screen_state)
            
            # Step 1: Find and open contact
            if not self._recipient_found:
                action = {
                    "type": "click",
                    "target": "search_box",
                    "coords": self.SEARCH_BOX_COORDS,
                    "retry": True,
                }
                logger.debug(f"Step 1: Click search box")
                return action
            
            # Step 2: Type recipient name
            elif not self._message_typed:
                action = {
                    "type": "type",
                    "target": "recipient_name",
                    "value": recipient,
                    "retry": True,
                }
                logger.debug(f"Step 2: Type recipient name: {recipient}")
                return action
            
            # Step 3: Press Enter to search/open
            elif self._previous_action and self._previous_action.get("type") == "type":
                action = {
                    "type": "key_press",
                    "target": "return",
                    "retry": True,
                }
                logger.debug(f"Step 3: Press Enter to open chat")
                return action
            
            # Step 4: Click message input field
            elif self._previous_action and self._previous_action.get("type") == "key_press":
                action = {
                    "type": "click",
                    "target": "message_input",
                    "coords": self.MESSAGE_INPUT_COORDS,
                    "retry": True,
                }
                logger.debug(f"Step 4: Click message input field")
                return action
            
            # Step 5: Type message
            else:
                action = {
                    "type": "type",
                    "target": "message_text",
                    "value": message,
                    "retry": True,
                }
                logger.debug(f"Step 5: Type message: {message}")
                return action
        
        except Exception as e:
            logger.error(f"get_next_action failed: {e}")
            return None
    
    def handle(self, task: str, screenshot: Optional[bytes]) -> Dict[str, Any]:
        """Handle task on WhatsApp (backward compatibility).
        
        Args:
            task: Task description (e.g., "send hi to Papa")
            screenshot: Current screenshot
            
        Returns:
            Result of handling
        """
        logger.info(f"Handling WhatsApp task: {task}")
        
        try:
            # Parse task intent
            recipient = self._extract_recipient(task)
            message = self._extract_message(task)
            
            logger.debug(f"Recipient: {recipient}, Message: {message}")
            
            if not recipient or not message:
                return {
                    "success": False,
                    "action_taken": None,
                    "next_screen": ScreenType.WHATSAPP,
                    "confidence": 0.5,
                    "error": "Could not parse recipient or message from task",
                }
            
            # Step 1: Search for recipient
            if not self._find_and_open_contact(recipient):
                return {
                    "success": False,
                    "action_taken": None,
                    "next_screen": ScreenType.WHATSAPP,
                    "confidence": 0.7,
                    "error": f"Could not find contact: {recipient}",
                }
            
            # Step 2: Type message
            if not self._type_and_send_message(message):
                return {
                    "success": False,
                    "action_taken": f"Found {recipient} but failed to send message",
                    "next_screen": ScreenType.WHATSAPP_CHAT,
                    "confidence": 0.7,
                    "error": "Failed to send message",
                }
            
            return {
                "success": True,
                "action_taken": f"Sent '{message}' to {recipient}",
                "next_screen": ScreenType.WHATSAPP_CHAT,
                "confidence": 0.9,
            }
            
        except Exception as e:
            logger.error(f"WhatsApp task failed: {e}")
            return {
                "success": False,
                "action_taken": None,
                "next_screen": ScreenType.WHATSAPP,
                "confidence": 0.5,
                "error": str(e),
            }
    
    def _extract_recipient(self, task: str) -> Optional[str]:
        """Extract recipient name from task.
        
        Args:
            task: Task description
            
        Returns:
            Recipient name or None
        """
        task_lower = task.lower()
        
        # Pattern: "send ... to <name>"
        match = re.search(r'(?:send|message|text)\s+(?:.*?)\s+to\s+(\w+)', task_lower)
        if match:
            return match.group(1).capitalize()
        
        # Pattern: "message <name>"
        match = re.search(r'(?:message|text|send|whatsapp)\s+(\w+)', task_lower)
        if match:
            return match.group(1).capitalize()
        
        return None
    
    def _extract_message(self, task: str) -> Optional[str]:
        """Extract message text from task.
        
        Args:
            task: Task description
            
        Returns:
            Message text or None
        """
        # Pattern: "send <message> to ..."
        match = re.search(r'send\s+"?([^"]+?)"?\s+to\s+\w+', task, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Pattern: "send <message>"
        match = re.search(r'send\s+"?([^"]+?)"?(?:\s|$)', task, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Default: everything except the recipient part
        if 'to' in task.lower():
            parts = task.lower().split(' to ')
            if parts:
                message_part = parts[0].replace('send', '').replace('message', '').replace('text', '').strip()
                if message_part:
                    return message_part
        
        return None
    
    def _find_and_open_contact(self, recipient: str) -> bool:
        """Find and open a WhatsApp contact.
        
        Args:
            recipient: Contact name
            
        Returns:
            True if contact found and opened
        """
        if not self.executor:
            logger.warning("No executor available")
            return False
        
        try:
            # Click on search box
            self.executor.click(*self.SEARCH_BOX_COORDS)
            
            # Type recipient name
            self.executor.type_keys(recipient)
            
            # Wait a bit for search results
            import time
            time.sleep(0.5)
            
            # Press Enter or click first result
            self.executor.press_key('return')
            
            logger.info(f"Opened contact: {recipient}")
            return True
        except Exception as e:
            logger.error(f"Failed to find contact {recipient}: {e}")
            return False
    
    def _type_and_send_message(self, message: str) -> bool:
        """Type message and send it.
        
        Args:
            message: Message text to send
            
        Returns:
            True if message sent
        """
        if not self.executor:
            logger.warning("No executor available")
            return False
        
        try:
            # Click on message input field
            self.executor.click(*self.MESSAGE_INPUT_COORDS)
            
            # Type message
            self.executor.type_keys(message)
            
            # Send message (either click send button or press Enter)
            self.executor.press_key('return')
            
            logger.info(f"Sent message: {message}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    def should_retry(self, attempt: int, last_error: Optional[str]) -> bool:
        """Retry strategy for WhatsApp."""
        return attempt < 2
    
    def get_recovery_action(self) -> Optional[str]:
        """Get recovery action if stuck."""
        return "press escape"  # Close any dialogs and go back
