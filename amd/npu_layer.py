"""AMD Ryzen AI NPU layer for always-on wake-word detection.

Implements XDNA-oriented behavior using ONNX Runtime DirectML when available,
with CPU whisper-tiny fallback when NPU acceleration is unavailable.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class NPULayer:
    """Ryzen AI NPU runtime helper for always-on voice detection.

    Target hardware: AMD Ryzen AI NPU (XDNA).
    Primary API: ONNX Runtime DirectML.
    Fallback: CPU whisper-tiny transcription path.
    """

    WAKE_WORD = "hey clevrr"
    MODEL_DIR = "data/npu_models"

    def __init__(self, config: dict):
        os.makedirs(self.MODEL_DIR, exist_ok=True)
        self.config = config
        self.session = None
        self.available = False
        self.providers = ["CPUExecutionProvider"]
        self._init_npu()

    def _init_npu(self):
        """Initialize NPU via ONNX Runtime DirectML provider."""
        try:
            import onnxruntime as ort

            providers = ort.get_available_providers()
            logger.info("Available providers: %s", providers)

            if "DmlExecutionProvider" in providers:
                self.available = True
                self.providers = [
                    "DmlExecutionProvider",
                    "CPUExecutionProvider",
                ]
                logger.info("NPU initialized via DirectML")
            else:
                logger.warning(
                    "NPU not available — install AMD Ryzen AI Software"
                )

        except ImportError:
            logger.warning(
                "onnxruntime not installed: pip install onnxruntime-directml"
            )

    def is_wake_word(self, audio_data, sample_rate: int = 16000) -> bool:
        """Detect wake word using NPU/DirectML first, then CPU fallback."""
        if not self.available:
            return self._cpu_wake_word(audio_data)

        try:
            import onnxruntime as ort

            features = self._extract_features(audio_data, sample_rate)

            if self.session is None:
                model_path = f"{self.MODEL_DIR}/wake_word.onnx"
                if os.path.exists(model_path):
                    opts = ort.SessionOptions()
                    opts.graph_optimization_level = (
                        ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                    )
                    self.session = ort.InferenceSession(
                        model_path,
                        sess_options=opts,
                        providers=self.providers,
                    )

            if self.session:
                result = self.session.run(None, {"input": features})
                confidence = float(result[0][0])
                return confidence > 0.85

            return self._cpu_wake_word(audio_data)

        except Exception as exc:
            logger.error("NPU inference error: %s", exc)
            return self._cpu_wake_word(audio_data)

    def _cpu_wake_word(self, audio_data) -> bool:
        """CPU fallback for wake word detection via whisper tiny."""
        import tempfile

        import soundfile as sf
        import whisper

        try:
            model = whisper.load_model("tiny")
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
                temp_path = temp.name
            sf.write(temp_path, audio_data, 16000)
            result = model.transcribe(temp_path, language="en")
            text = str(result.get("text", "")).lower()
            return self.WAKE_WORD in text
        except Exception:
            return False
        finally:
            try:
                if "temp_path" in locals() and os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass

    def _extract_features(self, audio, sample_rate: int):
        """Extract float32 energy features as ONNX input shape (1, 1, 100)."""
        import numpy as np

        frame_size = 512
        hop_size = 256
        frames = []

        for i in range(0, max(0, len(audio) - frame_size), hop_size):
            frame = audio[i : i + frame_size]
            energy = float(np.sum(frame ** 2))
            frames.append(energy)

        features = np.array(frames[:100], dtype=np.float32)
        if len(features) < 100:
            features = np.pad(features, (0, 100 - len(features)))

        return features.reshape(1, 1, 100)

    def get_power_usage(self) -> dict:
        """Return estimated power profile for NPU vs CPU fallback."""
        return {
            "device": "AMD Ryzen AI NPU",
            "architecture": "XDNA",
            "status": "active" if self.available else "cpu_fallback",
            "estimated_power": "< 1W" if self.available else "~5W CPU",
            "provider": "DirectML" if self.available else "CPU",
        }
