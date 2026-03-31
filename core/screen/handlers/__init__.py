"""Screen Handlers
=================

Implementations of handlers for different screen states.
"""

from .chrome_profile_handler import ChromeProfileHandler
from .chrome_browser_handler import ChromeBrowserHandler
from .google_homepage_handler import GoogleHomepageHandler
from .google_search_results_handler import GoogleSearchResultsHandler
from .desktop_handler import DesktopHandler

__all__ = [
    "ChromeProfileHandler",
    "ChromeBrowserHandler",
    "GoogleHomepageHandler",
    "GoogleSearchResultsHandler",
    "DesktopHandler",
]
