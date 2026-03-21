from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from core.auth.config import AuthConfig
from core.auth.consent_manager import ConsentManager
from core.auth.step_up_auth import StepUpAuth
from core.auth.token_vault import TokenVault
from core.security import Role, SecurityGateway, User

from .action_router import ActionRouter
from .config import BrainConfig
from .intent_parser import IntentParser
from .memory import BrainMemory


class BrainEngine:
    def __init__(
        self,
        brain_config: BrainConfig,
        auth_config: AuthConfig,
        gateway: SecurityGateway,
        on_response: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self._config = brain_config
        self._gateway = gateway
        self._on_response = on_response

        self._vault = TokenVault(auth_config)
        self._step_up = StepUpAuth(auth_config)
        self._consent = ConsentManager()
        self._memory = BrainMemory(brain_config.max_memory_turns)
        self._parser = IntentParser(brain_config)
        self._router = ActionRouter(gateway, self._vault, self._step_up, self._consent)

        self._bus_client = None
        self._stop_event = threading.Event()
        self._processed = 0
        self._errors = 0
        self.logger = logging.getLogger("clevrr.brain")
        self._ensure_default_user()

    def start(self) -> None:
        try:
            from core.bus import BusClient, Topics

            self._bus_client = BusClient(client_id="ai-brain")
            self._bus_client.connect()
            self._bus_client.subscribe(Topics.VOICE_TRANSCRIPT, self._on_transcript)
            self.logger.info("AI Brain connected to bus. Listening for voice commands...")
        except Exception as exc:
            self.logger.warning(f"Bus unavailable: {exc}. Running in direct mode.")

    def stop(self) -> None:
        self._stop_event.set()
        if self._bus_client:
            self._bus_client.disconnect()
        self.logger.info("AI Brain stopped")

    def process_command(self, command: str, user_id: Optional[str] = None) -> str:
        uid = user_id or self._config.default_user_id
        return self._process(uid, command)

    def get_stats(self) -> dict:
        return {"processed": self._processed, "errors": self._errors, "memory_size": self._memory.size()}

    def _on_transcript(self, msg) -> None:
        payload = msg.payload
        command = payload.get("text", "")
        user_id = payload.get("user_id", self._config.default_user_id)
        if not command:
            return
        threading.Thread(target=self._process, args=(user_id, command), daemon=True).start()

    def _process(self, user_id: str, command: str) -> str:
        self.logger.info(f"Processing: '{command}' (user={user_id})")
        context = self._memory.get_context()
        intent = self._parser.parse(command, context)
        self.logger.info(f"Intent: {intent.intent} (confidence={intent.confidence:.2f})")

        if not intent.is_confident(self._config.confidence_threshold):
            response = intent.response or "I'm not sure what you mean. Could you be more specific?"
            self._memory.add(command, "unknown", response, False)
            self._publish_response(user_id, response)
            return response

        result = self._router.route(user_id, intent)
        self._processed += 1
        if result.success:
            response = intent.response or f"Done! {result.output}"
        else:
            response = f"I couldn't complete that. {result.error or 'Please try again.'}"
            self._errors += 1

        self._memory.add(command, intent.intent, response, result.success)
        self._publish_response(user_id, response)
        self.logger.info(f"Response: '{response}' (success={result.success})")
        return response

    def _publish_response(self, user_id: str, response: str) -> None:
        if self._bus_client:
            try:
                from core.bus import Topics

                self._bus_client.publish(
                    Topics.AI_RESPONSE,
                    {"user_id": user_id, "response": response, "timestamp": time.time()},
                )
            except Exception as exc:
                self.logger.error(f"Publish failed: {exc}")

        if self._on_response:
            self._on_response(user_id, response)

    def _ensure_default_user(self) -> None:
        try:
            self._gateway.get_user(self._config.default_user_id)
        except Exception:
            self._gateway.add_user(
                User(
                    user_id=self._config.default_user_id,
                    username=self._config.default_user_id,
                    role=Role.USER,
                    created_at=time.time(),
                )
            )
