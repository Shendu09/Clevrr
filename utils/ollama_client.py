"""
OllamaClient — Local LLM Communication Layer

Handles ALL AI interactions through the local Ollama instance.
Supports vision (llava) and text (llama3) models.
ZERO external API calls. Everything runs on localhost:11434.
"""

import base64
import json
import logging
import time
import hashlib
import functools
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for communicating with a local Ollama instance.

    All AI inference runs through Ollama on the user's machine.
    No external APIs, no cloud services, no API keys required.
    """

    def __init__(self, config: dict) -> None:
        """Initialize the Ollama client with configuration.

        Args:
            config: Dictionary containing ollama settings from settings.yaml.

        Raises:
            ConnectionError: If Ollama is not running on the configured URL.
        """
        ollama_config = config.get("ollama", {})
        self.base_url: str = ollama_config.get("url", "http://localhost:11434")
        self.url: str = self.base_url
        self.vision_model: str = ollama_config.get("vision_model", "llava:latest")
        self.text_model: str = ollama_config.get("text_model", "llama3")
        self.code_model: str = ollama_config.get("code_model", "qwen2.5-coder:7b")
        self.timeout: int = ollama_config.get("timeout", 60)
        self.max_retries: int = ollama_config.get("max_retries", 3)

        # Persistent session for connection reuse (HTTP keep-alive)
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

        # In-memory prompt cache (avoids re-running identical LLM calls)
        self._cache: Dict[str, str] = {}
        self._cache_max = 128

        # Test connection on init
        if not self.test_connection():
            raise ConnectionError("Ollama connection failed. Start Ollama with: ollama serve")

    def _cache_key(self, payload: dict) -> str:
        """Generate stable hash for prompt + model (for caching).

        Args:
            payload: The request payload.

        Returns:
            16-character hex hash for cache lookup.
        """
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def test_connection(self):
        try:
            response = self.session.get(
                f"{self.base_url}/api/tags",
                timeout=5,
            )
            if response.status_code == 200:
                models = [
                    m["name"]
                    for m in response.json().get("models", [])
                ]
                logger.info("Ollama connected. Models: %s", models)
                return True
        except requests.exceptions.ConnectionError:
            print("ERROR: Ollama is not running!")
            print("Fix: Open a terminal and run: ollama serve")
            return False

        print("ERROR: Could not connect to Ollama API tags endpoint")
        print("Fix: Ensure Ollama is running and reachable at http://localhost:11434")
        return False

    # ------------------------------------------------------------------
    # Connection & Model Management
    # ------------------------------------------------------------------

    def is_running(self) -> bool:
        """Check if Ollama is running on the configured URL.

        Returns:
            True if Ollama responds, False otherwise.
        """
        try:
            resp = self.session.get(self.base_url, timeout=5)
            return resp.status_code == 200
        except requests.ConnectionError:
            return False
        except Exception as exc:
            logger.warning("Unexpected error pinging Ollama: %s", exc)
            return False

    def check_model_available(self, model_name: str) -> bool:
        """Check if a model is pulled and available locally.

        Args:
            model_name: Name of the model to check (e.g. 'llava', 'llama3').

        Returns:
            True if the model exists locally.
        """
        try:
            resp = self.session.get(
                f"{self.base_url}/api/tags",
                timeout=10,
            )
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                available_names = [m.get("name", "") for m in models]
                available_bases = [name.split(":")[0] for name in available_names]
                target_base = model_name.split(":")[0]
                return model_name in available_names or target_base in available_bases
            return False
        except Exception as exc:
            logger.error("Error checking model availability: %s", exc)
            return False

    def pull_model_if_missing(self, model_name: str) -> bool:
        """Pull a model if it is not available locally.

        Args:
            model_name: Name of the model to pull.

        Returns:
            True if model is now available, False on failure.
        """
        if self.check_model_available(model_name):
            logger.info("Model '%s' is already available.", model_name)
            return True

        print(
            f"\n⬇  Model '{model_name}' not found locally. "
            f"Pulling now... (this may take a while)\n"
        )

        try:
            resp = self.session.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name},
                stream=True,
                timeout=600,  # Models can be large
            )

            for line in resp.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        status = data.get("status", "")
                        completed = data.get("completed", 0)
                        total = data.get("total", 0)
                        if total > 0:
                            pct = (completed / total) * 100
                            print(
                                f"\r  ↳ {status}: {pct:.1f}%    ",
                                end="",
                                flush=True,
                            )
                        else:
                            print(
                                f"\r  ↳ {status}              ",
                                end="",
                                flush=True,
                            )
                    except json.JSONDecodeError:
                        pass

            print(f"\n✅ Model '{model_name}' pulled successfully.\n")
            return True

        except Exception as exc:
            logger.error("Failed to pull model '%s': %s", model_name, exc)
            print(f"\n❌ Failed to pull model '{model_name}': {exc}")
            return False

    # ------------------------------------------------------------------
    # Vision — Local llava Model
    # ------------------------------------------------------------------

    def analyze_screen(self, screenshot_path: str, question: str) -> str:
        """Analyze a screenshot using the local llava vision model.

        Args:
            screenshot_path: Path to the screenshot image file.
            question: Question to ask about the screenshot.

        Returns:
            Text response from the vision model.
        """
        try:
            from PIL import Image
            import io

            image_path = Path(screenshot_path)
            if not image_path.exists():
                return f"Error: Screenshot not found at {screenshot_path}"

            # Progressive resize widths per retry
            resize_widths = [1280, 1024, 768]
            jpeg_qualities = [85, 75, 65]

            for attempt in range(1, self.max_retries + 1):
                try:
                    # Resize image
                    img = Image.open(image_path)
                    max_width = resize_widths[
                        min(attempt - 1, len(resize_widths) - 1)
                    ]
                    quality = jpeg_qualities[
                        min(attempt - 1, len(jpeg_qualities) - 1)
                    ]

                    if img.width > max_width:
                        ratio = max_width / img.width
                        new_size = (max_width, int(img.height * ratio))
                        img = img.resize(new_size, Image.LANCZOS)

                    buffer = io.BytesIO()
                    img.save(
                        buffer,
                        format="JPEG",
                        quality=quality,
                        optimize=True,
                    )
                    image_b64 = base64.b64encode(buffer.getvalue()).decode(
                        "utf-8"
                    )

                    payload = {
                        "model": self.vision_model,
                        "messages": [
                            {
                                "role": "user",
                                "content": question,
                                "images": [image_b64],
                            }
                        ],
                        "stream": False,
                    }

                    resp = self.session.post(
                        f"{self.base_url}/api/chat",
                        json=payload,
                        timeout=120,
                    )

                    if resp.status_code == 200:
                        return (
                            resp.json()
                            .get("message", {})
                            .get("content", "")
                        )

                    logger.warning(
                        "Vision attempt %d failed: HTTP %d — %s",
                        attempt,
                        resp.status_code,
                        resp.text[:200],
                    )

                except requests.Timeout:
                    logger.warning("Vision attempt %d timed out.", attempt)
                except Exception as exc:
                    logger.warning("Vision attempt %d error: %s", attempt, exc)

                if attempt < self.max_retries:
                    time.sleep(1)  # Reduced from 2 to 1 second (exponential backoff handled externally)

            # Fallback to llava if primary model failed
            if self.vision_model != "llava:latest":
                logger.warning(
                    "Primary vision model %s failed. Falling back to llava:latest.",
                    self.vision_model,
                )
                original_model = self.vision_model
                self.vision_model = "llava:latest"
                result = self.analyze_screen(screenshot_path, question)
                self.vision_model = original_model
                return result

            return "Error: Vision analysis failed after all retries."

        except Exception as exc:
            logger.error("Error in analyze_screen: %s", exc)
            return f"Error analyzing screen: {exc}"

    def analyze_screen_bytes(self, image_bytes: bytes, question: str) -> str:
        """Analyze a screenshot from bytes directly (no disk I/O).

        This is faster than analyze_screen() for repeated calls since
        it keeps images in memory instead of reading/writing disk.

        Args:
            image_bytes: PNG/JPEG image bytes.
            question: Question to ask about the screenshot.

        Returns:
            Text response from the vision model.
        """
        try:
            from PIL import Image
            import io

            # Progressive resize widths per retry
            resize_widths = [1280, 1024, 768]
            jpeg_qualities = [85, 75, 65]

            for attempt in range(1, self.max_retries + 1):
                try:
                    # Load image from bytes
                    img = Image.open(io.BytesIO(image_bytes))

                    max_width = resize_widths[
                        min(attempt - 1, len(resize_widths) - 1)
                    ]
                    quality = jpeg_qualities[
                        min(attempt - 1, len(jpeg_qualities) - 1)
                    ]

                    if img.width > max_width:
                        ratio = max_width / img.width
                        new_size = (max_width, int(img.height * ratio))
                        img = img.resize(new_size, Image.LANCZOS)

                    buffer = io.BytesIO()
                    img.save(
                        buffer,
                        format="JPEG",
                        quality=quality,
                        optimize=True,
                    )
                    image_b64 = base64.b64encode(buffer.getvalue()).decode(
                        "utf-8"
                    )

                    payload = {
                        "model": self.vision_model,
                        "messages": [
                            {
                                "role": "user",
                                "content": question,
                                "images": [image_b64],
                            }
                        ],
                        "stream": False,
                    }

                    resp = self.session.post(
                        f"{self.base_url}/api/chat",
                        json=payload,
                        timeout=120,
                    )

                    if resp.status_code == 200:
                        return (
                            resp.json()
                            .get("message", {})
                            .get("content", "")
                        )

                    logger.warning(
                        "Vision analysis attempt %d failed: HTTP %d",
                        attempt,
                        resp.status_code,
                    )

                except requests.Timeout:
                    logger.warning("Vision analysis attempt %d timed out.", attempt)
                except Exception as exc:
                    logger.warning("Vision analysis attempt %d error: %s", attempt, exc)

                if attempt < self.max_retries:
                    time.sleep(1)

            return "Error: Vision analysis failed after all retries."

        except Exception as exc:
            logger.error("Error in analyze_screen_bytes: %s", exc)
            return f"Error analyzing screen: {exc}"

    # ------------------------------------------------------------------
    # Text Generation — Local llama3 Model
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 256,
    ) -> str:
        """Generate text using the local llama3 model.

        Args:
            prompt: The user prompt to send.
            system_prompt: Optional system-level instruction.
            max_tokens: Limit response length (default 256 for speed).

        Returns:
            Generated text response.
        """
        payload: Dict[str, Any] = {
            "model": self.text_model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }

        if system_prompt:
            payload["system"] = system_prompt

        # Check cache first (for identical prompts)
        cache_key = self._cache_key(payload)
        if cache_key in self._cache:
            logger.debug("[CACHE HIT] Reusing LLM response for prompt")
            return self._cache[cache_key]

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    result = resp.json().get("response", "")
                    
                    # Store in cache (with simple FIFO eviction)
                    if len(self._cache) >= self._cache_max:
                        oldest_key = next(iter(self._cache))
                        del self._cache[oldest_key]
                    self._cache[cache_key] = result
                    
                    return result
                logger.warning(
                    "Generate attempt %d failed: HTTP %d",
                    attempt,
                    resp.status_code,
                )
            except requests.Timeout:
                logger.warning("Generate attempt %d timed out.", attempt)
            except Exception as exc:
                logger.warning("Generate attempt %d error: %s", attempt, exc)

            if attempt < self.max_retries:
                time.sleep(2)

        return "Error: Text generation failed after all retries."

    def generate_code(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate code using a code-specialized model with text fallback.

        Uses qwen2.5-coder by default for programming tasks.
        Falls back to the text model if the code model is unavailable
        or generation fails.
        """
        code_model = self.code_model or "qwen2.5-coder:7b"

        if not self.check_model_available(code_model):
            logger.warning(
                "Code model %s not found. Run: ollama pull %s",
                code_model,
                code_model,
            )
            return self.generate(prompt, system_prompt)

        payload: Dict[str, Any] = {
            "model": code_model,
            "prompt": prompt,
            "system": system_prompt
            or (
                "You are an expert competitive programmer. "
                "Write optimal, correct code only. "
                "No explanations. No markdown. Raw code only."
            ),
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.95,
                "num_predict": 4096,
                "repeat_penalty": 1.1,
            },
        }

        try:
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=120,
            )
            if response.status_code == 200:
                result = response.json().get("response", "")
                logger.info("Code generated using %s", code_model)
                return result

            logger.error(
                "Code model request failed with HTTP %d; falling back to text model",
                response.status_code,
            )
            return self.generate(prompt, system_prompt)
        except Exception as exc:
            logger.error("Code model failed: %s", exc)
            return self.generate(prompt, system_prompt)

    def extract_json(self, text: str) -> dict:
       # Method 1: direct parse
       try:
           return json.loads(text)
       except:
           pass
       
       # Method 2: find JSON between { and }
       try:
           start = text.index('{')
           end = text.rindex('}') + 1
           return json.loads(text[start:end])
       except:
           pass
       
       # Method 3: find JSON array between [ and ]
       try:
           start = text.index('[')
           end = text.rindex(']') + 1
           return json.loads(text[start:end])
       except:
           pass
       
       # All methods failed
       raise ValueError(f"Could not extract JSON from: {text}")

    def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> dict:
        """Generate a JSON response from the local llama3 model.

        Appends instructions to force valid JSON output.
        Retries up to 3 times if JSON parsing fails.

        Args:
            prompt: The prompt to send.
            system_prompt: Optional system-level instruction.

        Returns:
            Parsed dictionary from the JSON response.
        """
        json_prompt = (
            f"{prompt}\n\n"
            "IMPORTANT: Respond ONLY with valid JSON. "
            "No markdown, no code blocks, no extra text. "
            "Just the raw JSON object."
        )

        for attempt in range(3):
           try:
               response = self.generate(json_prompt, system_prompt)
               return self.extract_json(response)
           except Exception as e:
               logger.warning(f"JSON attempt {attempt+1} failed: {e}")
               time.sleep(1)
        
        raise ValueError("Failed to get JSON after 3 attempts")

    # ------------------------------------------------------------------
    # Health Check
    # ------------------------------------------------------------------

    def health_check(self) -> dict:
        """Return a health report for the local Ollama instance.

        Returns:
            Dictionary with connection status, available models,
            and response times.
        """
        report: Dict[str, Any] = {
            "connected": False,
            "url": self.base_url,
            "models": [],
            "vision_model_ready": False,
            "text_model_ready": False,
            "code_model_ready": False,
            "response_time_ms": None,
        }

        start = time.time()
        try:
            resp = self.session.get(self.base_url, timeout=5)
            elapsed = (time.time() - start) * 1000
            report["connected"] = resp.status_code == 200
            report["response_time_ms"] = round(elapsed, 1)
        except Exception:
            return report

        # List available models
        try:
            resp = self.session.get(f"{self.base_url}/api/tags", timeout=10)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                report["models"] = [
                    {
                        "name": m.get("name", ""),
                        "size": m.get("size", 0),
                        "modified_at": m.get("modified_at", ""),
                    }
                    for m in models
                ]
                model_names = [
                    m.get("name", "").split(":")[0] for m in models
                ]
                report["vision_model_ready"] = (
                    self.vision_model in model_names
                )
                report["text_model_ready"] = (
                    self.text_model in model_names
                )
                report["code_model_ready"] = (
                    self.code_model.split(":")[0] in model_names
                )
        except Exception as exc:
            logger.warning("Error listing models: %s", exc)

        return report
