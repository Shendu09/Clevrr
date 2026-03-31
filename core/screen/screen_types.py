"""Screen Type Enumerations
===========================

Defines all recognized screen states in the automation system.
"""

from enum import Enum


class ScreenType(Enum):
    """Enumeration of all screen states the agent can recognize."""
    
    # Desktop
    DESKTOP = "desktop"
    FILE_EXPLORER = "file_explorer"
    
    # Chrome/Browser
    CHROME_START = "chrome_start"
    CHROME_PROFILE = "chrome_profile"
    CHROME_BROWSER = "chrome_browser"
    CHROME_ERROR = "chrome_error"
    
    # Web Pages
    GOOGLE_HOMEPAGE = "google_homepage"
    GOOGLE_SEARCH_RESULTS = "google_search_results"
    YOUTUBE_HOME = "youtube_home"
    YOUTUBE_VIDEO = "youtube_video"
    
    # Common Web Pages
    LOGIN_PAGE = "login_page"
    ERROR_PAGE = "error_page"
    BLANK_PAGE = "blank_page"
    
    # Popups & Dialogs
    POPUP_DIALOG = "popup_dialog"
    SELECTION_DIALOG = "selection_dialog"
    CONFIRMATION_DIALOG = "confirmation_dialog"
    
    # Other Applications
    NOTEPAD = "notepad"
    WORD = "word"
    EXCEL = "excel"
    SETTINGS = "settings"
    
    # Unknown/Unrecognized
    UNKNOWN = "unknown"
    
    def __str__(self) -> str:
        """Return display name."""
        return self.value
    
    def is_browser(self) -> bool:
        """Check if this is a browser-related screen."""
        return self.name.startswith("CHROME") or self.name.startswith("GOOGLE") or self.name.startswith("YOUTUBE")
    
    def is_desktop(self) -> bool:
        """Check if this is a desktop screen."""
        return self in [ScreenType.DESKTOP, ScreenType.FILE_EXPLORER]
    
    def is_dialog(self) -> bool:
        """Check if this is a dialog/popup screen."""
        dialog_screens = [
            ScreenType.POPUP_DIALOG,
            ScreenType.SELECTION_DIALOG,
            ScreenType.CONFIRMATION_DIALOG,
            ScreenType.CHROME_ERROR,
            ScreenType.ERROR_PAGE,
        ]
        return self in dialog_screens
