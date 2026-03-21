from agents.orchestrator import Orchestrator
import threading
from os_control.app_launcher import AppLauncher
from os_control.file_manager import FileManager
from os_control.process_manager import ProcessManager
from os_control.window_manager import WindowManager
from security.threat_detector import ThreatDetector
from security.voice_authenticator import VoiceAuthenticator
from core.hook_system import HookEvent, HookSystem
from core.instinct_system import InstinctSystem
from core.memory_optimizer import MemoryOptimizer
from core.skills_loader import SkillsLoader
from core.verification_loop import VerificationLoop
from app_control.universal_controller import UniversalController
from agents.competitive_programmer import CompetitiveProgrammer
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

        self.ollama = self.orchestrator.ollama
        self.memory = self.orchestrator.memory

        self.app_launcher = AppLauncher()
        self.voice = VoiceController(config, self.app_launcher)

        self.threat_detector = ThreatDetector()
        self.voice_auth = VoiceAuthenticator()

        self.window_manager = WindowManager()
        self.process_manager = ProcessManager()
        self.file_manager = FileManager()
        self.screen_capture = ScreenCapture(config)
        self.cp_agent = CompetitiveProgrammer(self.ollama, self.screen_capture)

        self.instincts = InstinctSystem(self.ollama, self.memory)
        self.hooks = HookSystem()
        self.verification = VerificationLoop(
            self.ollama,
            self.screen_capture,
            self.hooks,
        )
        self.skills = SkillsLoader()
        self.memory_optimizer = MemoryOptimizer(self.memory)

        self.universal_controller = UniversalController(self.ollama)

        self.completed_tasks = 0
        self.successful_tasks = 0

        self.hooks.fire(HookEvent.SESSION_START, {"mode": "ai_layer"})

        self.overlay = _OverlayProxy()

    def _on_task_complete(self, task: str, plan: dict, success: bool):
        self.hooks.fire(
            HookEvent.TASK_COMPLETE,
            {
                "task": task,
                "success": success,
                "plan": plan,
            },
        )

        if not success:
            self.hooks.fire(
                HookEvent.TASK_FAILED,
                {
                    "task": task,
                    "plan": plan,
                },
            )

        threading.Thread(
            target=self.instincts.extract_instinct,
            args=(task, plan, success),
            daemon=True,
        ).start()

        def _compact_if_needed():
            if self.memory_optimizer.should_compact():
                self.memory_optimizer.compact_memory()

        threading.Thread(target=_compact_if_needed, daemon=True).start()

    def _build_plan_snapshot(self) -> dict:
        try:
            history = self.orchestrator.get_history(limit=1)
            if history:
                return {"steps": history[0].get("steps", [])}
        except Exception:
            pass
        return {"steps": []}

    def _normalize_result(self, result) -> dict:
        if isinstance(result, dict):
            if "success" not in result:
                result["success"] = True
            return result
        return {
            "success": bool(result),
            "outcome": result,
        }

    def run_task(
        self,
        task_text: str,
        auth_result: dict = None,
    ) -> dict:
        self.hooks.fire(HookEvent.PRE_VOICE_COMMAND, {"task": task_text})

        try:
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
            self.hooks.fire(
                HookEvent.POST_VOICE_COMMAND,
                {"task": task_text, "parsed_type": command_result.get("type")},
            )

            if command_result["type"] == "app_action":
                result = self.handle_app_action(
                    command_result["action"],
                    command_result.get("target", ""),
                    command_result.get("original", task_text),
                )
                self.hooks.fire(
                    HookEvent.POST_TASK,
                    {
                        "task": task_text,
                        "success": result.get("success", False),
                    },
                )
                return result

            if command_result["type"] == "instinct_management":
                action = command_result["action"]

                if action == "instinct_status":
                    status = self.instincts.get_status()
                    msg = (
                        f"I have learned {status['total']} patterns. "
                        f"{status['high_confidence']} are high confidence."
                    )
                    self.voice.speak(msg)
                    return {"success": True, "outcome": status}

                if action == "export_instincts":
                    self.instincts.export_instincts("data/my_instincts.json")
                    self.voice.speak("Instincts exported")
                    return {"success": True}

                if action == "clear_last_instinct":
                    removed = self.instincts.clear_last_instinct()
                    self.voice.speak(
                        "Last instinct removed" if removed else "No instincts to remove"
                    )
                    return {"success": True, "removed": removed}

                if action == "save_current_instinct":
                    self.instincts.save_manual_instinct(task_text)
                    self.voice.speak("Saved this as a memory pattern")
                    return {"success": True}

            if command_result["type"] == "app_launch":
                self.hooks.fire(HookEvent.PRE_APP_LAUNCH, {"task": task_text})
                result = command_result["result"]
                if result.get("success"):
                    self.voice.speak(f"Opening {result.get('app', 'app')}")
                else:
                    suggestion = result.get("suggestion", "")
                    self.voice.speak(f"App not found. {suggestion}")
                self.hooks.fire(HookEvent.POST_APP_LAUNCH, {"task": task_text, "result": result})
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

            instinct = self.instincts.find_instinct(task_text)
            if instinct and instinct["confidence"] > 0.8:
                print(
                    f"[INSTINCT] Using learned pattern: "
                    f"{instinct['trigger']} "
                    f"({instinct['confidence']:.0%} confidence)"
                )

                before = self.screen_capture.capture_primary()
                result = self._normalize_result(self._execute_instinct(instinct, task_text))
                after = self.screen_capture.capture_primary()

                verification = self.verification.verify_step(
                    {
                        "action_type": instinct.get("action_type", "ai_task"),
                        "expected_outcome": instinct.get("action", ""),
                    },
                    before,
                    after,
                )
                result["verification"] = verification

                final_success = bool(result.get("success", False) and verification.get("success", False))
                result["success"] = final_success

                self.instincts.update_instinct_result(instinct["id"], final_success)
                return result

            skill_context = self.skills.find_relevant_skill(task_text)
            self.hooks.fire(
                HookEvent.PRE_TASK,
                {
                    "task": task_text,
                    "skill_loaded": bool(skill_context),
                },
            )

            self.overlay.update_status(f"Running: {task_text[:30]}...")
            result = self.orchestrator.run_task(task_text)

            self.completed_tasks += 1
            if result.get("success"):
                self.successful_tasks += 1

            plan = self._build_plan_snapshot()
            self._on_task_complete(task_text, plan, bool(result.get("success")))

            checkpoint_shot = self.screen_capture.capture_primary()
            self.verification.save_checkpoint(
                step_number=result.get("steps_completed", 0),
                task=task_text,
                completed_steps=plan.get("steps", []),
                screenshot_path=checkpoint_shot,
            )

            self.hooks.fire(
                HookEvent.POST_TASK,
                {
                    "task": task_text,
                    "success": result.get("success", False),
                },
            )

            status = "Done!" if result.get("success") else "Failed"
            self.voice.speak(status)
            return result

        except Exception as exc:
            self.hooks.fire(
                HookEvent.ERROR_DETECTED,
                {
                    "task": task_text,
                    "error": str(exc),
                },
            )
            return {
                "success": False,
                "outcome": f"Unexpected layer error: {exc}",
            }

    def _execute_instinct(self, instinct: dict, original_task: str) -> dict:
        action_type = instinct.get("action_type", "ai_task")
        action = instinct.get("action", "")

        if action_type == "app_launch":
            return self.app_launcher.launch_app(action)

        if action_type == "system":
            return self._handle_system_command(action)

        return self.orchestrator.run_task(action or original_task)

    def handle_app_action(
        self, action: str, target: str, original_text: str
    ) -> dict:
        """Handle universal app actions."""
        ctrl = self.universal_controller

        if action in ["solve_screen", "solve_python", "solve_java", "solve_cpp"]:
            language = "python"

            if action == "solve_java" or "java" in original_text.lower():
                language = "java"
            elif action == "solve_cpp" or "c++" in original_text.lower():
                language = "cpp"
            elif action == "solve_python":
                language = "python"

            self.voice.speak(f"Reading question and solving in {language}")
            result = self.cp_agent.solve_from_screen(language=language, max_attempts=3)

            if result.get("success"):
                self.voice.speak("Solution found and all test cases passed")
            else:
                self.voice.speak("Solution written but some test cases failed")
            return result

        # WhatsApp actions
        if action == "whatsapp_send":
            parts = target.split(" ", 1)
            contact = parts[0] if parts else ""
            message = parts[1] if len(parts) > 1 else ""

            if not message:
                self.voice.speak("What message should I send?")
                message = self.voice.listen_once()

            result = ctrl.control_app("whatsapp", "send_message", contact, message)
            if result.get("success"):
                self.voice.speak(f"Message sent to {contact}")
            return result

        elif action == "whatsapp_read":
            result = ctrl.control_app("whatsapp", "read_messages", target)
            if result.get("success"):
                self.voice.speak(
                    f"Messages from {target}: {result.get('messages', '')[:200]}"
                )
            return result

        # Spotify actions
        elif action == "spotify_play":
            result = ctrl.control_app("spotify", "play", target)
            if result.get("success"):
                self.voice.speak(f"Playing {target or 'music'}")
            return result

        elif action == "spotify_pause":
            result = ctrl.control_app("spotify", "pause")
            self.voice.speak("Music paused")
            return result

        elif action == "spotify_skip":
            result = ctrl.control_app("spotify", "skip")
            self.voice.speak("Skipped")
            return result

        elif action == "spotify_previous":
            result = ctrl.control_app("spotify", "previous")
            self.voice.speak("Previous track")
            return result

        elif action == "spotify_volume_up":
            result = ctrl.control_app("spotify", "volume_up")
            self.voice.speak("Volume up")
            return result

        elif action == "spotify_volume_down":
            result = ctrl.control_app("spotify", "volume_down")
            self.voice.speak("Volume down")
            return result

        # Browser actions
        elif action == "browser_navigate":
            result = ctrl.control_app("browser", "navigate", target)
            self.voice.speak(f"Going to {target}")
            return result

        elif action == "browser_search":
            result = ctrl.control_app("browser", "search", target)
            self.voice.speak(f"Searching for {target}")
            return result

        elif action == "browser_read":
            result = ctrl.control_app("browser", "read")
            if result.get("success"):
                summary = result.get("content", "")[:300]
                self.voice.speak(summary)
            return result

        elif action == "browser_new_tab":
            result = ctrl.control_app("browser", "new_tab")
            self.voice.speak("New tab opened")
            return result

        elif action == "browser_close_tab":
            result = ctrl.control_app("browser", "close_tab")
            self.voice.speak("Tab closed")
            return result

        # Generic app launcher
        elif action in ["open_whatsapp"]:
            app_name = action.replace("open_", "")
            result = self.app_launcher.launch_app(app_name)
            if result.get("success"):
                self.voice.speak(f"Opening {app_name}")
            return result

        return {"success": False, "reason": f"Unknown app action: {action}"}

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
        success_rate = (
            (self.successful_tasks / self.completed_tasks) * 100
            if self.completed_tasks > 0
            else 0
        )
        self.hooks.fire(
            HookEvent.SESSION_END,
            {
                "task_count": self.completed_tasks,
                "success_rate": round(success_rate, 1),
            },
        )
        self.voice.stop()
