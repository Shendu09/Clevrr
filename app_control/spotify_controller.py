"""Spotify desktop app controller.

Controls Spotify via UIAutomation + keyboard shortcuts.
Fast, reliable, no external API required.
"""

import logging

logger = logging.getLogger(__name__)


class SpotifyController:
    """Spotify desktop automation controller."""

    SHORTCUTS = {
        "play_pause": "space",
        "skip": "ctrl+right",
        "previous": "ctrl+left",
        "volume_up": "ctrl+up",
        "volume_down": "ctrl+down",
        "mute": "ctrl+shift+down",
        "like": "alt+shift+b",
        "shuffle": "ctrl+shift+s",
        "repeat": "ctrl+shift+r",
    }

    def __init__(self, uia_controller, input_controller):
        self.uia = uia_controller
        self.input = input_controller

    def play(self, track_name: str = None) -> dict:
        """Play music, optionally search for specific track."""
        if track_name:
            result = self._search(track_name)
            if not result["success"]:
                return result

        self.input.press_key("space")
        return {"success": True, "message": f"Playing {track_name or 'music'}"}

    def pause(self) -> dict:
        """Pause playback."""
        self.input.press_key("space")
        return {"success": True, "message": "Paused"}

    def skip(self) -> dict:
        """Skip to next track."""
        self.input.press_key("ctrl+right")
        return {"success": True, "message": "Skipped"}

    def previous(self) -> dict:
        """Go to previous track."""
        self.input.press_key("ctrl+left")
        return {"success": True, "message": "Previous track"}

    def volume_up(self) -> dict:
        """Increase volume."""
        self.input.press_key("ctrl+up")
        return {"success": True, "message": "Volume up"}

    def volume_down(self) -> dict:
        """Decrease volume."""
        self.input.press_key("ctrl+down")
        return {"success": True, "message": "Volume down"}

    def toggle_shuffle(self) -> dict:
        """Toggle shuffle mode."""
        self.input.press_key("ctrl+shift+s")
        return {"success": True, "message": "Shuffle toggled"}

    def toggle_repeat(self) -> dict:
        """Toggle repeat mode."""
        self.input.press_key("ctrl+shift+r")
        return {"success": True, "message": "Repeat toggled"}

    def _search(self, query: str) -> dict:
        """Search for track."""
        try:
            if self.uia:
                window = self.uia.get_app_window("Spotify")
                if window:
                    window.SetFocus()
                    import time

                    time.sleep(0.2)

            # Open search
            self.input.press_key("ctrl+l")
            import time

            time.sleep(0.3)
            self.input.type_text(query)
            time.sleep(0.5)
            self.input.press_key("enter")
            time.sleep(1)
            return {"success": True}
        except Exception as exc:
            logger.error(f"Spotify search failed: {exc}")
            return {"success": False, "reason": str(exc)}

    def get_current_track(self) -> dict:
        """Get currently playing track info."""
        if not self.uia:
            return {"success": False, "reason": "UIAutomation not available"}

        try:
            window = self.uia.get_app_window("Spotify")
            if window:
                return {"success": True, "track": window.Name}
        except Exception as exc:
            logger.error(f"Get current track failed: {exc}")

        return {"success": False}
