from __future__ import annotations


class Topics:
    VOICE_TRANSCRIPT = "voice.transcript"
    VOICE_WAKE_WORD = "voice.wake_word"
    VOICE_ERROR = "voice.error"

    VISION_SCREENSHOT = "vision.screenshot"
    VISION_CONTEXT = "vision.context"
    VISION_ERROR = "vision.error"

    AI_DECISION = "ai.decision"
    AI_COMMAND = "ai.command"
    AI_RESPONSE = "ai.response"
    AI_ERROR = "ai.error"

    SYSTEM_HEALTH = "system.health"
    SYSTEM_AUDIT = "system.audit"
    SYSTEM_STARTED = "system.started"
    SYSTEM_STOPPING = "system.stopping"

    ACTION_RESULT = "action.result"
    ACTION_ERROR = "action.error"

    @classmethod
    def all(cls) -> list[str]:
        return [
            value
            for key, value in vars(cls).items()
            if not key.startswith("_") and isinstance(value, str)
        ]

    @classmethod
    def for_layer(cls, layer: str) -> list[str]:
        return [topic for topic in cls.all() if topic.startswith(f"{layer}.")]
