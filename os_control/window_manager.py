import ctypes


class WindowManager:

    def close_window(self, target: str) -> bool:
        import pyautogui

        if target:
            windows = pyautogui.getWindowsWithTitle(target)
            if windows:
                windows[0].activate()
                pyautogui.hotkey("alt", "f4")
                return True
            return False

        pyautogui.hotkey("alt", "f4")
        return True

    def get_all_windows(self) -> list:
        import pyautogui

        windows = []
        for window in pyautogui.getAllWindows():
            title = getattr(window, "title", "")
            if title and title.strip():
                windows.append({"title": title.strip()})
        return windows

    def arrange_windows(self, mode: str):
        shell = ctypes.windll.user32
        if mode == "side_by_side":
            shell.keybd_event(0x5B, 0, 0, 0)
            shell.keybd_event(0x44, 0, 0, 0)
            shell.keybd_event(0x44, 0, 2, 0)
            shell.keybd_event(0x5B, 0, 2, 0)
