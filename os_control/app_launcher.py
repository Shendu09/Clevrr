import glob
import os
import subprocess


class AppLauncher:

    def __init__(self):
        self.app_catalog = {}
        self.aliases = {}
        self._build_catalog()

    def _build_catalog(self):
        search_paths = [
            os.path.expandvars(
                r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"
            ),
            r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
            r"C:\Program Files",
            r"C:\Program Files (x86)",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs"),
        ]

        for base_path in search_paths[:2]:
            if not os.path.exists(base_path):
                continue
            for lnk in glob.glob(f"{base_path}/**/*.lnk", recursive=True):
                name = os.path.splitext(os.path.basename(lnk))[0].lower()
                self.app_catalog[name] = {
                    "type": "shortcut",
                    "path": lnk,
                    "display_name": os.path.splitext(os.path.basename(lnk))[0],
                }

        for base_path in search_paths[2:]:
            if not os.path.exists(base_path):
                continue
            for exe in glob.glob(f"{base_path}/**/*.exe", recursive=True):
                name = os.path.splitext(os.path.basename(exe))[0].lower()
                if name not in self.app_catalog:
                    self.app_catalog[name] = {
                        "type": "exe",
                        "path": exe,
                        "display_name": os.path.splitext(os.path.basename(exe))[0],
                    }

        builtin_apps = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "paint": "mspaint.exe",
            "wordpad": "wordpad.exe",
            "explorer": "explorer.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "task manager": "taskmgr.exe",
            "settings": "ms-settings:",
            "control panel": "control.exe",
            "snipping tool": "snippingtool.exe",
            "clock": "ms-clock:",
            "calendar": "outlookcal:",
            "camera": "microsoft.windows.camera:",
            "photos": "ms-photos:",
            "maps": "bingmaps:",
            "weather": "bingweather:",
            "store": "ms-windows-store:",
            "spotify": "spotify.exe",
            "chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "edge": "msedge.exe",
            "vlc": "vlc.exe",
            "vscode": "code.exe",
            "vs code": "code.exe",
            "visual studio code": "code.exe",
            "discord": "discord.exe",
            "telegram": "telegram.exe",
            "whatsapp": "whatsapp.exe",
            "zoom": "zoom.exe",
            "teams": "ms-teams.exe",
            "word": "winword.exe",
            "excel": "excel.exe",
            "powerpoint": "powerpnt.exe",
            "outlook": "outlook.exe",
        }

        for name, cmd in builtin_apps.items():
            self.app_catalog[name] = {
                "type": "builtin",
                "path": cmd,
                "display_name": name.title(),
            }

        self._build_aliases()
        print(f"[AppLauncher] Indexed {len(self.app_catalog)} apps")

    def _build_aliases(self):
        nickname_map = {
            "browser": "chrome",
            "internet": "chrome",
            "web": "chrome",
            "email": "outlook",
            "mail": "outlook",
            "music": "spotify",
            "songs": "spotify",
            "video": "vlc",
            "movies": "vlc",
            "text editor": "notepad",
            "notes": "notepad",
            "code editor": "vscode",
            "coding": "vscode",
            "spreadsheet": "excel",
            "presentation": "powerpoint",
            "slides": "powerpoint",
            "document": "word",
            "docs": "word",
            "chat": "discord",
            "messaging": "telegram",
            "meetings": "zoom",
            "terminal": "cmd",
            "console": "cmd",
            "files": "explorer",
            "file manager": "explorer",
        }
        self.aliases.update(nickname_map)

    def find_app(self, voice_command: str) -> dict | None:
        query = voice_command.lower().strip()

        stop_words = [
            "open",
            "launch",
            "start",
            "run",
            "please",
            "can you",
            "could you",
            "the",
            "app",
            "application",
            "program",
        ]
        for word in stop_words:
            query = query.replace(word, "").strip()

        query = query.strip()

        if query in self.app_catalog:
            return self.app_catalog[query]

        if query in self.aliases:
            alias_key = self.aliases[query]
            if alias_key in self.app_catalog:
                return self.app_catalog[alias_key]

        for app_name, app_info in self.app_catalog.items():
            if query in app_name or app_name in query:
                return app_info

        query_words = set(query.split())
        best_match = None
        best_score = 0

        for app_name, app_info in self.app_catalog.items():
            app_words = set(app_name.split())
            overlap = len(query_words & app_words)
            if overlap > best_score:
                best_score = overlap
                best_match = app_info

        if best_score > 0:
            return best_match

        return None

    def launch_app(self, app_name: str) -> dict:
        app = self.find_app(app_name)

        if not app:
            return {
                "success": False,
                "message": f"App not found: {app_name}",
                "suggestion": self._suggest_similar(app_name),
            }

        try:
            path = app["path"]
            app_type = app["type"]

            if app_type == "shortcut":
                os.startfile(path)
            elif app_type == "builtin":
                if path.startswith("ms-") or path.endswith(":"):
                    os.startfile(path)
                else:
                    subprocess.Popen(path)
            elif app_type == "exe":
                subprocess.Popen(path)

            return {
                "success": True,
                "message": f"Launched {app['display_name']}",
                "app": app["display_name"],
            }

        except Exception as error:
            return {
                "success": False,
                "message": f"Failed to launch: {str(error)}",
            }

    def _suggest_similar(self, query: str) -> str:
        query_lower = query.lower()
        suggestions = []

        for app_name in self.app_catalog:
            common = sum(1 for char in query_lower if char in app_name)
            if common > 2:
                suggestions.append(app_name)

        if suggestions:
            return f"Did you mean: {suggestions[0]}?"
        return "No similar apps found"

    def get_all_apps(self) -> list:
        return [
            {"name": info["display_name"], "type": info["type"]}
            for info in self.app_catalog.values()
        ]

    def refresh_catalog(self):
        self.app_catalog.clear()
        self.aliases.clear()
        self._build_catalog()
        return len(self.app_catalog)
