"""TensorRT-style optimization utilities for RTX 5050 (Blackwell).

Provides CUDA-aware optimization hooks for faster-whisper and generic
inference benchmarking with robust CPU-safe fallback behavior.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)


class TensorRTOptimizer:
    """Optimization and profiling helper for CUDA 13.0 / RTX 5050 paths."""

    def __init__(self) -> None:
        try:
            import torch

            self.torch = torch
            self.cuda_available = bool(torch.cuda.is_available())
        except ImportError:
            self.torch = None
            self.cuda_available = False

    def optimize_whisper(self, model_size: str = "small") -> Any:
        """Load faster-whisper using float16 on CUDA, with CPU fallback.

        Args:
            model_size: faster-whisper model size.

        Returns:
            Initialized `WhisperModel` instance.
        """
        from faster_whisper import WhisperModel

        if self.cuda_available:
            logger.info("Loading faster-whisper '%s' on CUDA float16.", model_size)
            return WhisperModel(model_size, device="cuda", compute_type="float16")

        logger.warning("CUDA unavailable. Loading faster-whisper '%s' on CPU.", model_size)
        return WhisperModel(model_size, device="cpu", compute_type="int8")

    def get_optimal_precision(self) -> str:
        """Detect optimal precision from GPU compute capability.

        Returns one of: float8, float16, bfloat16, float32.
        """
        if not self.cuda_available or self.torch is None:
            return "float32"

        major, _minor = self.torch.cuda.get_device_capability(0)
        if major >= 10:
            return "float8"
        if major >= 8:
            return "bfloat16"
        if major >= 7:
            return "float16"
        return "float32"

    def profile_inference(self, func: Callable[..., Any], warmup: int = 3, runs: int = 10) -> Dict[str, float]:
        """Benchmark an inference callable using GPU-safe timing.

        Args:
            func: Callable to benchmark.
            warmup: Warmup invocation count.
            runs: Timed invocation count.

        Returns:
            Dictionary with mean/min/max/std in milliseconds.
        """
        import numpy as np

        if warmup < 0:
            warmup = 0
        if runs <= 0:
            runs = 1

        for _ in range(warmup):
            func()
        if self.cuda_available and self.torch is not None:
            self.torch.cuda.synchronize()

        times = []
        for _ in range(runs):
            if self.cuda_available and self.torch is not None:
                self.torch.cuda.synchronize()
            start = time.perf_counter()
            func()
            if self.cuda_available and self.torch is not None:
                self.torch.cuda.synchronize()
            end = time.perf_counter()
            times.append((end - start) * 1000.0)

        arr = np.array(times, dtype=np.float64)
        return {
            "mean_ms": float(arr.mean()),
            "min_ms": float(arr.min()),
            "max_ms": float(arr.max()),
            "std_ms": float(arr.std()),
        }
