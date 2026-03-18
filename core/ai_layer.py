from agents.orchestrator import Orchestrator
from os_control.app_launcher import AppLauncher
from os_control.file_manager import FileManager
from os_control.process_manager import ProcessManager
from os_control.window_manager import WindowManager
from security.threat_detector import ThreatDetector
from security.voice_authenticator import VoiceAuthenticator
from utils.safety_guard import SafetyGuard
from utils.screen_capture import ScreenCapture
from utils.voice_controller import VoiceController


class _OverlayProxy:

    def update_status(self, _text: str):
        return None


class AILayer:

    def __init__(self, config: dict):
        self.config = config
        self.orchestrator = Orchestrator(config)
        self.safety = SafetyGuard("config/safety_rules.yaml")

        self.app_launcher = AppLauncher()
        self.voice = VoiceController(config, self.app_launcher)

        self.threat_detector = ThreatDetector()
        self.voice_auth = VoiceAuthenticator()

        self.window_manager = WindowManager()
        self.process_manager = ProcessManager()
        self.file_manager = FileManager()
        self.screen_capture = ScreenCapture(config)

        self.overlay = _OverlayProxy()

    def run_task(
        self,
        task_text: str,
        auth_result: dict = None,
    ) -> dict:
        threat_scan = self.threat_detector.scan(task_text)
        if not threat_scan["clean"]:
            severity = threat_scan["highest_severity"]
            if severity in ["CRITICAL", "HIGH"]:
                return {
                    "success": False,
                    "outcome": (
                        "BLOCKED: Security threat detected — "
                        f"{threat_scan['threats'][0]['description']}"
                    ),
                }

        if auth_result:
            safety_check = self.safety.check_voice_command(task_text, auth_result)
        else:
            safety_check = self.safety.check_action(task_text)

        if safety_check["decision"] == "BLOCKED":
            return {
                "success": False,
                "outcome": f"BLOCKED: {safety_check['reason']}",
            }

        if safety_check["decision"] == "CONFIRM":
            confirmed = self.safety.request_confirmation(task_text)
            if not confirmed:
                return {
                    "success": False,
                    "outcome": "Cancelled by user",
                }

        command_result = self.voice.process_command(task_text)

        if command_result["type"] == "app_launch":
            result = command_result["result"]
            if result.get("success"):
                self.voice.speak(f"Opening {result.get('app', 'app')}")
            else:
                suggestion = result.get("suggestion", "")
                self.voice.speak(f"App not found. {suggestion}")
            return result

        if command_result["type"] == "app_close":
            success = self.window_manager.close_window(command_result["target"])
            msg = (
                f"Closed {command_result['target']}"
                if success
                else "Could not find that window"
            )
            self.voice.speak(msg)
            return {
                "success": success,
                "outcome": msg,
            }

        if command_result["type"] == "system":
            return self._handle_system_command(command_result["action"])

        self.overlay.update_status(f"Running: {task_text[:30]}...")
        result = self.orchestrator.run_task(task_text)
        status = "Done!" if result.get("success") else "Failed"
        self.voice.speak(status)
        return result

    def _handle_system_command(self, action: str) -> dict:
        if action == "screenshot":
            path = self.screen_capture.capture_primary()
            self.voice.speak("Screenshot taken")
            return {"success": True, "outcome": path}

        if action == "show_desktop":
            import pyautogui

            pyautogui.hotkey("win", "d")
            self.voice.speak("Showing desktop")
            return {"success": True}

        if action == "lock":
            import ctypes

            ctypes.windll.user32.LockWorkStation()
            return {"success": True}

        if action == "organize_downloads":
            self.file_manager.organize_downloads()
            self.voice.speak("Downloads organized")
            return {"success": True}

        if action == "system_health":
            health = self.process_manager.get_system_health()
            msg = (
                f"CPU {health['cpu_percent']} percent. "
                f"RAM {health['memory_percent']} percent."
            )
            self.voice.speak(msg)
            return {"success": True, "outcome": health}

        if action == "list_windows":
            windows = self.window_manager.get_all_windows()
            names = [item["title"] for item in windows[:5]]
            msg = "Open windows: " + ", ".join(names)
            self.voice.speak(msg)
            return {"success": True, "outcome": names}

        if action == "arrange_side_by_side":
            self.window_manager.arrange_windows("side_by_side")
            self.voice.speak("Windows arranged side by side")
            return {"success": True}

        return {"success": False, "outcome": "Unknown command"}

    def start_voice(self):
        self.voice.start_listening(lambda command: self.run_task(command))

    def stop_voice(self):
        self.voice.stop()
