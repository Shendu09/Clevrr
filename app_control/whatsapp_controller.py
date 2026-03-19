"""WhatsApp controller via WhatsApp Web.

Controls WhatsApp without any API or extension.
Uses Playwright for browser automation.
"""

import logging
import time

logger = logging.getLogger(__name__)


class WhatsAppController:
    """WhatsApp Web automation controller."""

    WA_WEB_URL = "https://web.whatsapp.com"

    def __init__(self, browser_controller):
        self.browser = browser_controller
        self.is_logged_in = False

    def initialize(self) -> dict:
        """Initialize WhatsApp Web and check login status."""
        result = self.browser.navigate(self.WA_WEB_URL)
        if not result.get("success"):
            return {"success": False, "reason": "Could not open WhatsApp Web"}

        time.sleep(3)

        # Check if logged in
        content = self.browser.read_content()
        if "qr code" in content.lower():
            return {
                "success": False,
                "reason": "Please scan QR code to login",
                "action_needed": "scan_qr",
            }

        self.is_logged_in = True
        return {"success": True, "message": "WhatsApp ready"}

    def open_chat(self, contact_name: str) -> dict:
        """Open chat with contact."""
        if not self.is_logged_in:
            result = self.initialize()
            if not result["success"]:
                return result

        try:
            # Click search box
            self.browser.click_element("search box")
            time.sleep(0.3)

            # Type contact name
            from app_control.input_controller import InputController

            inp = InputController()
            inp.type_text(contact_name)
            time.sleep(1)

            # Click first result
            self.browser.click_element(f"contact {contact_name}")
            time.sleep(0.5)

            return {"success": True, "message": f"Opened chat with {contact_name}"}
        except Exception as exc:
            logger.error(f"Open chat failed: {exc}")
            return {"success": False, "reason": str(exc)}

    def send_message(self, contact: str, message: str) -> dict:
        """Send message to contact."""
        open_result = self.open_chat(contact)
        if not open_result["success"]:
            return open_result

        try:
            # Click message input
            self.browser.click_element("message input")
            time.sleep(0.2)

            # Type message
            from app_control.input_controller import InputController

            inp = InputController()
            inp.type_text(message)
            time.sleep(0.2)

            # Send with Enter
            inp.press_key("enter")
            time.sleep(0.5)

            return {"success": True, "message": f"Sent '{message}' to {contact}"}
        except Exception as exc:
            logger.error(f"Send message failed: {exc}")
            return {"success": False, "reason": str(exc)}

    def read_messages(self, contact: str, limit: int = 10) -> dict:
        """Read messages from contact."""
        open_result = self.open_chat(contact)
        if not open_result["success"]:
            return open_result

        try:
            content_result = self.browser.read_content()
            return {
                "success": True,
                "messages": content_result.get("content", ""),
                "contact": contact,
            }
        except Exception as exc:
            logger.error(f"Read messages failed: {exc}")
            return {"success": False, "reason": str(exc)}

    def send_file(self, contact: str, file_path: str) -> dict:
        """Send file to contact."""
        open_result = self.open_chat(contact)
        if not open_result["success"]:
            return open_result

        try:
            from app_control.input_controller import InputController

            inp = InputController()

            # Click attachment button
            self.browser.click_element("attach file")
            time.sleep(0.5)

            # Type file path in dialog
            inp.type_text(file_path)
            inp.press_key("enter")
            time.sleep(1)

            # Send
            inp.press_key("enter")

            return {"success": True, "message": f"Sent file to {contact}"}
        except Exception as exc:
            logger.error(f"Send file failed: {exc}")
            return {"success": False, "reason": str(exc)}
