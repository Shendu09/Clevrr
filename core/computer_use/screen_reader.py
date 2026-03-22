from __future__ import annotations

import base64
import io
import json
import logging
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from .config import ComputerUseConfig

try:
    import mss
    from PIL import Image

    _HAS_CAPTURE = True
except ImportError:
    _HAS_CAPTURE = False


@dataclass(slots=True)
class ScreenUnderstanding:
    raw_description: str
    active_app: str
    page_title: str
    visible_text: str
    clickable_elements: list[str] = field(default_factory=list)
    input_fields: list[str] = field(default_factory=list)
    current_url: str = ""
    task_relevant: str = ""
    screenshot_b64: str = ""
    timestamp: float = 0.0


class ScreenReader:
    def __init__(self, config: ComputerUseConfig) -> None:
        self._config = config
        self._sct = None
        self.logger = logging.getLogger("clevrr.cu.reader")

    def capture_and_understand(self, task_context: str = "") -> ScreenUnderstanding:
        img_bytes = self._capture_screen()
        if not img_bytes:
            return self._empty_understanding()
        img_b64 = base64.b64encode(img_bytes).decode()
        prompt = (
            "Analyze this screenshot carefully.\n"
            f"Current task: {task_context or 'General analysis'}\n\n"
            "Return a JSON object with these exact keys:\n"
            "{\"active_app\":\"\",\"page_title\":\"\",\"visible_text\":\"\","
            "\"clickable_elements\":[],\"input_fields\":[],\"current_url\":\"\","
            "\"task_relevant\":\"\"}\n"
            "Be specific and accurate. Focus on UI elements. Return ONLY JSON."
        )
        try:
            payload = json.dumps(
                {
                    "model": self._config.vision_model,
                    "prompt": prompt,
                    "images": [img_b64],
                    "stream": False,
                    "format": "json",
                }
            ).encode()
            req = urllib.request.Request(
                f"{self._config.ollama_host}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read())
            raw = result.get("response", "{}")
            data = json.loads(raw)
            return ScreenUnderstanding(
                raw_description=raw,
                active_app=data.get("active_app", "unknown"),
                page_title=data.get("page_title", ""),
                visible_text=data.get("visible_text", ""),
                clickable_elements=data.get("clickable_elements", []),
                input_fields=data.get("input_fields", []),
                current_url=data.get("current_url", ""),
                task_relevant=data.get("task_relevant", ""),
                screenshot_b64=img_b64,
                timestamp=time.time(),
            )
        except Exception as exc:
            self.logger.warning("Vision analysis failed: %s", exc)
            return ScreenUnderstanding(
                raw_description="Vision unavailable",
                active_app="unknown",
                page_title="",
                visible_text="",
                clickable_elements=[],
                input_fields=[],
                current_url="",
                task_relevant="",
                screenshot_b64=img_b64,
                timestamp=time.time(),
            )

    def _capture_screen(self) -> Optional[bytes]:
        if not _HAS_CAPTURE:
            return None
        try:
            if self._sct is None:
                self._sct = mss.mss()
            monitor = self._sct.monitors[1]
            raw = self._sct.grab(monitor)
            img = Image.frombytes("RGB", (raw.width, raw.height), raw.bgra, "raw", "BGRX")
            if img.width > self._config.max_width:
                ratio = self._config.max_width / float(img.width)
                img = img.resize((self._config.max_width, int(img.height * ratio)), Image.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=self._config.screenshot_quality)
            return buffer.getvalue()
        except Exception as exc:
            self.logger.error("Screenshot failed: %s", exc)
            return None

    def _empty_understanding(self) -> ScreenUnderstanding:
        return ScreenUnderstanding(
            raw_description="No screenshot available",
            active_app="unknown",
            page_title="",
            visible_text="",
            clickable_elements=[],
            input_fields=[],
            current_url="",
            task_relevant="",
            screenshot_b64="",
            timestamp=time.time(),
        )
