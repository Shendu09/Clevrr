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
        self.vision_model: str = ollama_config.get("vision_model", "llava")
        self.text_model: str = ollama_config.get("text_model", "llama3")
        self.timeout: int = ollama_config.get("timeout", 60)
        self.max_retries: int = ollama_config.get("max_retries", 3)

        # Test connection on init
        if not self.test_connection():
            raise ConnectionError("Ollama connection failed. Start Ollama with: ollama serve")

    def test_connection(self):
        try:
            response = requests.get(
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
            resp = requests.get(self.base_url, timeout=5)
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
            resp = requests.get(
                f"{self.base_url}/api/tags",
                timeout=10,
            )
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                available = [m.get("name", "").split(":")[0] for m in models]
                return model_name in available
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
            resp = requests.post(
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
            image_path = Path(screenshot_path)
            if not image_path.exists():
                return f"Error: Screenshot not found at {screenshot_path}"

            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")

            payload = {
                "model": self.vision_model,
                "prompt": question,
                "images": [image_b64],
                "stream": False,
            }

            for attempt in range(1, self.max_retries + 1):
                try:
                    resp = requests.post(
                        f"{self.base_url}/api/generate",
                        json=payload,
                        timeout=self.timeout,
                    )
                    if resp.status_code == 200:
                        return resp.json().get("response", "")
                    logger.warning(
                        "Vision request attempt %d failed: HTTP %d",
                        attempt,
                        resp.status_code,
                    )
                except requests.Timeout:
                    logger.warning(
                        "Vision request attempt %d timed out.", attempt
                    )

                if attempt < self.max_retries:
                    time.sleep(2)

            return "Error: Vision analysis failed after all retries."

        except Exception as exc:
            logger.error("Error in analyze_screen: %s", exc)
            return f"Error analyzing screen: {exc}"

    # ------------------------------------------------------------------
    # Text Generation — Local llama3 Model
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate text using the local llama3 model.

        Args:
            prompt: The user prompt to send.
            system_prompt: Optional system-level instruction.

        Returns:
            Generated text response.
        """
        payload: Dict[str, Any] = {
            "model": self.text_model,
            "prompt": prompt,
            "stream": False,
        }

        if system_prompt:
            payload["system"] = system_prompt

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    return resp.json().get("response", "")
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
            "response_time_ms": None,
        }

        start = time.time()
        try:
            resp = requests.get(self.base_url, timeout=5)
            elapsed = (time.time() - start) * 1000
            report["connected"] = resp.status_code == 200
            report["response_time_ms"] = round(elapsed, 1)
        except Exception:
            return report

        # List available models
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=10)
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
        except Exception as exc:
            logger.warning("Error listing models: %s", exc)

        return report
