"""Hardware router for RTX 5050 + Radeon 780M + Ryzen AI NPU.

Routes tasks across NVIDIA CUDA, AMD iGPU (ROCm/DirectML/OpenCL), and
AMD Ryzen AI NPU with resilient fallback behavior and CPU-safe operation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class HardwareRouter:
    """Three-way processor router for Clevrr AI OS layer.

    - RTX 5050 (CUDA 13.0 path): LLM/vision/speech heavy workloads
    - Radeon 780M (RDNA3): screen compare/background compute
    - Ryzen AI NPU (XDNA): always-on wake-word tasks
    """

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

        self.cuda = None
        self.rocm = None
        self.npu = None

        self.rtx_available = False
        self.igpu_available = False
        self.npu_available = False

        self._init_all_processors()

    def _init_all_processors(self) -> None:
        """Initialize CUDA/ROCm/NPU processors and print startup status."""
        try:
            from cuda.gpu_kernels import CUDAKernels

            self.cuda = CUDAKernels()
            self.rtx_available = True
        except Exception as exc:
            logger.info("RTX processor unavailable: %s", exc)

        try:
            from amd.rocm_layer import ROCmLayer

            self.rocm = ROCmLayer()
            self.igpu_available = True
        except Exception as exc:
            logger.info("Radeon iGPU processor unavailable: %s", exc)

        try:
            from amd.npu_layer import NPULayer

            self.npu = NPULayer(self.config)
            self.npu_available = bool(getattr(self.npu, "available", False))
        except Exception as exc:
            logger.info("Ryzen AI NPU unavailable: %s", exc)

        status = self.get_full_status()
        startup_line = (
            "HardwareRouter startup => "
            f"NPU:{status['npu']['available']} "
            f"iGPU:{status['igpu']['available']} "
            f"RTX:{status['rtx']['available']}"
        )
        print(startup_line)
        logger.info(startup_line)

    def route(self, task_type: str) -> str:
        """Route task type to processor with fallback chain npu→igpu→rtx→cpu."""
        task_map = {
            "wake_word": "npu",
            "screen_compare": "igpu",
            "llm_inference": "rtx",
            "vision_ai": "rtx",
            "speech_to_text": "rtx",
        }

        preferred = task_map.get(task_type, "cpu")

        if preferred == "npu":
            if self.npu_available:
                return "npu"
            if self.igpu_available:
                return "igpu"
            if self.rtx_available:
                return "rtx"
            return "cpu"

        if preferred == "igpu":
            if self.igpu_available:
                return "igpu"
            if self.rtx_available:
                return "rtx"
            if self.npu_available:
                return "npu"
            return "cpu"

        if preferred == "rtx":
            if self.rtx_available:
                return "rtx"
            if self.igpu_available:
                return "igpu"
            if self.npu_available:
                return "npu"
            return "cpu"

        return "cpu"

    def screen_compare(self, img1: str, img2: str) -> Dict[str, Any]:
        """Compare screenshots using iGPU first, then RTX, then CPU.

        Returns diff score and selected processor name.
        """
        processor = self.route("screen_compare")

        if processor == "igpu" and self.rocm is not None:
            score = float(self.rocm.screen_compare_igpu(img1, img2))
            return {
                "processor": "igpu",
                "diff_score": score,
                "changed": score > 5.0,
            }

        if processor == "rtx" and self.cuda is not None:
            result = self.cuda.screen_diff_gpu(img1, img2)
            return {
                "processor": "rtx",
                "diff_score": float(result.get("diff_score", 100.0)),
                "changed": bool(result.get("changed", True)),
            }

        score = self._cpu_screen_compare(img1, img2)
        return {
            "processor": "cpu",
            "diff_score": score,
            "changed": score > 5.0,
        }

    def detect_wake_word(self, audio_data) -> bool:
        """Detect wake word using NPU first, then CPU fallback."""
        processor = self.route("wake_word")

        if processor == "npu" and self.npu is not None:
            try:
                return bool(self.npu.is_wake_word(audio_data, sample_rate=16000))
            except Exception as exc:
                logger.warning("NPU wake-word detection failed: %s", exc)

        return self._cpu_wake_word(audio_data)

    def get_full_status(self) -> Dict[str, Any]:
        """Return complete status for RTX 5050, Radeon 780M, and Ryzen AI NPU."""
        rtx_info: Dict[str, Any] = {
            "available": self.rtx_available,
            "architecture": "Blackwell",
            "role": "llm_inference/vision_ai/speech_to_text",
            "api": "CUDA 13.0",
            "vram": None,
        }
        if self.rtx_available and self.cuda is not None:
            try:
                torch = self.cuda.torch
                if torch is not None and torch.cuda.is_available():
                    props = torch.cuda.get_device_properties(0)
                    rtx_info["vram"] = int(props.total_memory // 1024**3)
                    rtx_info["device_name"] = torch.cuda.get_device_name(0)
            except Exception:
                pass

        igpu_info: Dict[str, Any] = {
            "available": self.igpu_available,
            "architecture": "RDNA3",
            "role": "screen_compare",
            "api": "DirectML/OpenCL",
            "device_name": "AMD Radeon 780M",
        }
        if self.rocm is not None:
            try:
                igpu_info.update(self.rocm.get_status())
            except Exception:
                pass

        npu_info: Dict[str, Any] = {
            "available": self.npu_available,
            "architecture": "XDNA",
            "role": "wake_word",
            "api": "DirectML",
            "device_name": "AMD Ryzen AI NPU",
        }
        if self.npu is not None:
            try:
                npu_info.update(self.npu.get_power_usage())
                npu_info["available"] = bool(getattr(self.npu, "available", False))
            except Exception:
                pass

        return {
            "rtx": rtx_info,
            "igpu": igpu_info,
            "npu": npu_info,
        }

    @staticmethod
    def _cpu_screen_compare(img1_path: str, img2_path: str) -> float:
        try:
            import cv2
            import numpy as np

            img1 = cv2.imread(img1_path)
            img2 = cv2.imread(img2_path)
            if img1 is None or img2 is None:
                return 100.0
            if img1.shape != img2.shape:
                img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
            diff = cv2.absdiff(img1, img2)
            return float(np.mean(diff))
        except Exception:
            return 100.0

    @staticmethod
    def _cpu_wake_word(audio_data) -> bool:
        try:
            import os
            import tempfile

            import soundfile as sf
            import whisper

            model = whisper.load_model("tiny")
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                temp_path = tmp.name
            sf.write(temp_path, audio_data, 16000)
            result = model.transcribe(temp_path, language="en")
            text = str(result.get("text", "")).lower()
            return "hey clevrr" in text
        except Exception:
            return False
        finally:
            try:
                if "temp_path" in locals() and os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
