"""
ElementFinder — Semantic UI Element Locator

Uses pywinauto on Windows for accessible UI element discovery.
Falls back to vision-based search when pywinauto is unavailable.
No external APIs — all processing is local.
"""

import logging
import sys
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ElementFinder:
    """Finds UI elements using platform-specific accessibility APIs.

    On Windows, uses pywinauto to query the UI Automation tree.
    On other platforms, falls back to vision-based element search.
    """

    def __init__(self) -> None:
        """Initialize the ElementFinder."""
        self._pywinauto_available = False

        if sys.platform == "win32":
            try:
                from pywinauto import Desktop

                self._desktop = Desktop(backend="uia")
                self._pywinauto_available = True
                logger.info("ElementFinder using pywinauto (UIA backend).")
            except ImportError:
                logger.warning(
                    "pywinauto not installed. Element finding will "
                    "rely on vision-based search."
                )
            except Exception as exc:
                logger.warning("pywinauto init failed: %s", exc)

    def find_by_name(
        self, name: str, control_type: Optional[str] = None
    ) -> Optional[Tuple[int, int]]:
        """Find a UI element by its name/text.

        Args:
            name: Text or name of the element to find.
            control_type: Optional control type filter (e.g. 'Button', 'Edit').

        Returns:
            Tuple of (x, y) center coordinates, or None if not found.
        """
        if not self._pywinauto_available:
            return None

        try:
            from pywinauto import Desktop

            desktop = Desktop(backend="uia")
            windows = desktop.windows()

            for win in windows:
                try:
                    if control_type:
                        elements = win.descendants(
                            title_re=f".*{name}.*",
                            control_type=control_type,
                        )
                    else:
                        elements = win.descendants(title_re=f".*{name}.*")

                    for elem in elements:
                        rect = elem.rectangle()
                        cx = (rect.left + rect.right) // 2
                        cy = (rect.top + rect.bottom) // 2
                        logger.info(
                            "Found element '%s' at (%d, %d)", name, cx, cy
                        )
                        return (cx, cy)

                except Exception:
                    continue

        except Exception as exc:
            logger.warning("Element search failed: %s", exc)

        return None

    def find_all_elements(
        self, window_title: Optional[str] = None
    ) -> List[Dict]:
        """List all UI elements in the active or specified window.

        Args:
            window_title: Optional window title to search in.

        Returns:
            List of element dictionaries with name, type, and position.
        """
        elements: List[Dict] = []

        if not self._pywinauto_available:
            return elements

        try:
            from pywinauto import Desktop

            desktop = Desktop(backend="uia")

            if window_title:
                windows = desktop.windows(title_re=f".*{window_title}.*")
            else:
                windows = desktop.windows()

            for win in windows[:3]:  # Limit to avoid huge trees
                try:
                    for child in win.descendants():
                        try:
                            rect = child.rectangle()
                            elements.append(
                                {
                                    "name": child.window_text() or "",
                                    "control_type": child.element_info.control_type or "",
                                    "x": (rect.left + rect.right) // 2,
                                    "y": (rect.top + rect.bottom) // 2,
                                    "width": rect.right - rect.left,
                                    "height": rect.bottom - rect.top,
                                }
                            )
                        except Exception:
                            continue

                    # Limit element count
                    if len(elements) > 200:
                        break

                except Exception:
                    continue

        except Exception as exc:
            logger.warning("Failed to enumerate elements: %s", exc)

        return elements

    def find_button(self, text: str) -> Optional[Tuple[int, int]]:
        """Find a button element by its text.

        Args:
            text: Button text to search for.

        Returns:
            Center coordinates or None.
        """
        return self.find_by_name(text, control_type="Button")

    def find_text_field(self, label: str) -> Optional[Tuple[int, int]]:
        """Find a text input field by its label.

        Args:
            label: Label or placeholder text near the field.

        Returns:
            Center coordinates or None.
        """
        return self.find_by_name(label, control_type="Edit")

    def is_available(self) -> bool:
        """Check if pywinauto element finding is available.

        Returns:
            True if pywinauto is loaded and working.
        """
        return self._pywinauto_available
