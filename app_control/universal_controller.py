"""Universal app controller.

Master router that selects the best control method for each app:
1. App-specific controllers (WhatsApp, Spotify, Discord, etc.)
2. Browser controller (for web apps)
3. UIAutomation (for Windows desktop apps)
4. Vision AI (universal fallback)
"""

import logging
import sys

logger = logging.getLogger(__name__)


class UniversalController:
    """Master controller that routes to the best method for each app."""

    def __init__(self, ollama_client):
        self.ollama = ollama_client
        self.platform = sys.platform
        self.controllers = {}
        self._init_controllers()

    def _init_controllers(self):
        """Initialize available controllers."""
        from app_control.input_controller import InputController
        from app_control.vision_controller import VisionController

        self.input = InputController()
        self.vision = VisionController(self.ollama)

        # Windows only
        if self.platform == "win32":
            try:
                from app_control.uia_controller import UIAController

                self.uia = UIAController()
                logger.info("UIAutomation controller ready")
            except Exception as exc:
                logger.warning(f"UIAutomation not available: {exc}")
                self.uia = None
        else:
            self.uia = None

        # Browser controller (all platforms)
        try:
            from app_control.browser_controller import BrowserController

            self.browser = BrowserController()
            logger.info("Browser controller ready")
        except Exception as exc:
            logger.warning(f"Browser controller not available: {exc}")
            self.browser = None

    def control_app(
        self,
        app_name: str,
        action: str,
        target: str = None,
        value: str = None,
    ) -> dict:
        """Route to best controller for this app."""
        app_lower = app_name.lower()

        # Route to browser actions
        if any(
            b in app_lower
            for b in ["chrome", "firefox", "edge", "brave", "opera", "browser"]
        ):
            return self._browser_action(app_name, action, target, value)

        # Route to messaging apps
        elif any(
            w in app_lower
            for w in [
                "whatsapp",
                "telegram",
                "discord",
                "slack",
                "teams",
                "zoom",
            ]
        ):
            return self._messaging_action(app_name, action, target, value)

        # Route to media apps
        elif any(
            m in app_lower
            for m in [
                "spotify",
                "music",
                "vlc",
                "media player",
                "youtube music",
            ]
        ):
            return self._media_action(app_name, action, target, value)

        # Try UIAutomation for Windows apps
        elif self.uia:
            return self._uia_action(app_name, action, target, value)

        # Fall back to vision AI
        else:
            return self._vision_action(app_name, action, target, value)

    def _browser_action(
        self, app: str, action: str, target: str = None, value: str = None
    ) -> dict:
        """Handle browser-specific actions."""
        if not self.browser:
            return {
                "success": False,
                "reason": "Browser controller unavailable",
            }

        if action == "navigate":
            return self.browser.navigate(target or "")
        elif action == "search":
            return self.browser.search(value or target or "")
        elif action == "click":
            return self.browser.click_element(target or "")
        elif action == "type":
            return self.browser.fill_field(target or "", value or "")
        elif action == "read":
            return self.browser.read_content()
        elif action == "new_tab":
            return self.browser.new_tab()
        elif action == "close_tab":
            return self.browser.close_tab()

        return {"success": False, "reason": "Unknown browser action"}

    def _messaging_action(
        self, app: str, action: str, target: str = None, value: str = None
    ) -> dict:
        """Handle messaging app actions."""
        app_lower = app.lower()

        if "whatsapp" in app_lower:
            try:
                from app_control.whatsapp_controller import WhatsAppController

                wa = WhatsAppController(self.browser)
                if action == "send_message":
                    return wa.send_message(target or "", value or "")
                elif action == "read_messages":
                    return wa.read_messages(target or "")
                elif action == "open_chat":
                    return wa.open_chat(target or "")
            except Exception as exc:
                logger.error(f"WhatsApp action failed: {exc}")

        # Generic messaging via UIA or vision
        return self._uia_action(app, action, target, value)

    def _media_action(
        self, app: str, action: str, target: str = None, value: str = None
    ) -> dict:
        """Handle media player actions."""
        if "spotify" in app.lower():
            try:
                from app_control.spotify_controller import SpotifyController

                sp = SpotifyController(self.uia, self.input)
                if action == "play":
                    return sp.play(value or target)
                elif action == "pause":
                    return sp.pause()
                elif action == "skip":
                    return sp.skip()
                elif action == "previous":
                    return sp.previous()
                elif action == "volume_up":
                    return sp.volume_up()
                elif action == "volume_down":
                    return sp.volume_down()
            except Exception as exc:
                logger.error(f"Spotify action failed: {exc}")

        # Generic media playback
        if action == "play":
            self.input.press_key("space")
        elif action == "pause":
            self.input.press_key("space")
        elif action == "skip":
            self.input.press_key("ctrl+right")
        elif action == "volume_up":
            self.input.press_key("ctrl+up")
        elif action == "volume_down":
            self.input.press_key("ctrl+down")

        return {"success": True}

    def _uia_action(
        self, app: str, action: str, target: str = None, value: str = None
    ) -> dict:
        """Handle UIAutomation actions."""
        if not self.uia:
            return self._vision_action(app, action, target, value)

        return self.uia.perform_action(app, action, target, value)

    def _vision_action(
        self, app: str, action: str, target: str = None, value: str = None
    ) -> dict:
        """Handle vision AI fallback actions."""
        return self.vision.perform_action(action, target, value)
