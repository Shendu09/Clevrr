"""Windows UI Automation controller.

Uses Microsoft UIAutomation which supports MFC, Windows Forms, WPF,
Modern UI, Qt, Firefox, Chrome, Electron apps, and more.
Fast and reliable for Windows apps.
"""

import logging
import sys

logger = logging.getLogger(__name__)


class UIAController:
    """Windows UIAutomation controller for app control."""

    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("UIAController only works on Windows")

        try:
            import uiautomation as auto

            self.auto = auto
            logger.info("UIA Controller initialized")
        except ImportError:
            raise ImportError(
                "uiautomation not installed. Run: pip install uiautomation"
            )

    def get_app_window(self, app_name: str):
        """Find the app window by name."""
        try:
            window = self.auto.WindowControl(searchDepth=1, Name=app_name)
            if window.Exists(3):
                return window

            # Try partial match
            desktop = self.auto.GetRootControl()
            for w in desktop.GetChildren():
                if app_name.lower() in (w.Name or "").lower():
                    return w
        except Exception as exc:
            logger.error(f"Window not found: {app_name}: {exc}")

        return None

    def find_element(
        self, window, element_type: str, name: str = None
    ):
        """Find element by type and optional name."""
        try:
            type_map = {
                "button": self.auto.ButtonControl,
                "edit": self.auto.EditControl,
                "text": self.auto.TextControl,
                "list": self.auto.ListControl,
                "checkbox": self.auto.CheckBoxControl,
                "menu": self.auto.MenuControl,
                "tab": self.auto.TabControl,
                "link": self.auto.HyperlinkControl,
            }

            control_class = type_map.get(
                element_type.lower(), self.auto.Control
            )

            if name:
                element = control_class(searchFromControl=window, Name=name)
            else:
                element = control_class(searchFromControl=window)

            if element.Exists(2):
                return element
        except Exception as exc:
            logger.error(f"Element not found: {exc}")

        return None

    def perform_action(
        self, app_name: str, action: str, target: str = None, value: str = None
    ) -> dict:
        """Perform action on app window."""
        window = self.get_app_window(app_name)
        if not window:
            return {
                "success": False,
                "reason": f"App window not found: {app_name}",
            }

        try:
            window.SetFocus()
            import time

            time.sleep(0.2)

            if action == "click":
                element = self.find_element(window, "button", target)
                if element:
                    element.Click()
                    return {"success": True}

            elif action == "type":
                element = self.find_element(window, "edit", target)
                if element:
                    element.SetFocus()
                    element.SendKeys(value or "")
                    return {"success": True}

            elif action == "read":
                texts = []
                for control in window.GetChildren():
                    if control.Name:
                        texts.append(control.Name)
                return {"success": True, "content": "\n".join(texts)}

            elif action == "get_all_elements":
                elements = []
                for control in window.GetChildren():
                    elements.append(
                        {
                            "name": control.Name,
                            "type": control.ControlTypeName,
                            "value": getattr(control, "CurrentValue", None),
                        }
                    )
                return {"success": True, "elements": elements}

        except Exception as exc:
            logger.error(f"UIA action failed: {exc}")
            return {"success": False, "reason": str(exc)}

        return {"success": False, "reason": "Action not handled"}

    def list_all_windows(self) -> list:
        """List all visible windows."""
        windows = []
        try:
            desktop = self.auto.GetRootControl()
            for window in desktop.GetChildren():
                if window.Name and window.IsEnabled:
                    windows.append(
                        {
                            "name": window.Name,
                            "class": window.ClassName,
                            "handle": window.NativeWindowHandle,
                        }
                    )
        except Exception as exc:
            logger.error(f"List windows failed: {exc}")

        return windows
