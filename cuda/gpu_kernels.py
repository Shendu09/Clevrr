"""NVIDIA CUDA 13.0 GPU kernels for screenshot processing on RTX 5050.

This module follows CUDA best practices for memory throughput, compute
throughput, and safe fallback behavior when GPU libraries are unavailable.
Target hardware: NVIDIA GeForce RTX 5050 (Blackwell).
"""

from __future__ import annotations

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class CUDAKernels:
    """CUDA helper kernels for RTX 5050 screenshot and memory operations.

    Designed for CUDA 13.0-style workflows with explicit runtime checks and
    CPU-safe fallbacks when CUDA or optional NVIDIA tooling is unavailable.
    """

    def __init__(self) -> None:
        self.torch = None
        self.device = "cpu"
        self.cuda_available = False
        self.device_name = "cpu"

        try:
            import torch

            self.torch = torch
            self.cuda_available = bool(torch.cuda.is_available())
            if self.cuda_available:
                self.device = "cuda:0"
                self.device_name = torch.cuda.get_device_name(0)
                try:
                    torch.backends.cuda.matmul.allow_tf32 = True
                    torch.backends.cudnn.allow_tf32 = True
                except Exception:
                    pass
                logger.info(
                    "CUDAKernels initialized on %s (RTX 5050/CUDA 13.0 compatible path).",
                    self.device_name,
                )
            else:
                logger.warning("CUDA unavailable. CUDAKernels using CPU fallback.")
        except ImportError:
            logger.warning("PyTorch not installed. CUDAKernels using CPU fallback.")

    def screen_diff_gpu(self, img1_path: str, img2_path: str) -> Dict[str, float | bool | str]:
        """Compare two screenshots on GPU (RTX 5050) with CPU fallback.

        Args:
            img1_path: Path to first image.
            img2_path: Path to second image.

        Returns:
            Dictionary with diff score, changed flag, and processor used.
        """
        try:
            import cv2
            import numpy as np
        except ImportError:
            return {
                "changed": True,
                "diff_score": 100.0,
                "processor": "cpu",
                "reason": "opencv/numpy missing",
            }

        img1 = cv2.imread(img1_path)
        img2 = cv2.imread(img2_path)
        if img1 is None or img2 is None:
            return {
                "changed": True,
                "diff_score": 100.0,
                "processor": "cpu",
                "reason": "image_load_failed",
            }

        if img1.shape != img2.shape:
            img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))

        if self.cuda_available and self.torch is not None:
            try:
                torch = self.torch
                t1 = torch.from_numpy(img1).to(self.device, non_blocking=True).float()
                t2 = torch.from_numpy(img2).to(self.device, non_blocking=True).float()
                diff = torch.abs(t1 - t2)
                mean_diff = float(diff.mean().item())
                del t1, t2, diff
                return {
                    "changed": mean_diff > 5.0,
                    "diff_score": mean_diff,
                    "processor": self.device_name,
                }
            except Exception as exc:
                logger.warning("GPU diff failed, using CPU fallback: %s", exc)

        diff = cv2.absdiff(img1, img2)
        mean_diff = float(np.mean(diff))
        return {
            "changed": mean_diff > 5.0,
            "diff_score": mean_diff,
            "processor": "cpu",
        }

    def get_gpu_utilization(self) -> Dict[str, int | float | str]:
        """Return GPU utilization using NVIDIA NVML when available.

        Intended for RTX 5050 monitoring under CUDA 13.0-compatible setups.
        """
        if not self.cuda_available:
            return {
                "gpu_utilization": 0,
                "memory_used_mb": 0,
                "memory_total_mb": 0,
                "device": "cpu",
            }

        try:
            import pynvml

            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            return {
                "gpu_utilization": int(util.gpu),
                "memory_utilization": int(util.memory),
                "memory_used_mb": int(mem.used // 1024**2),
                "memory_total_mb": int(mem.total // 1024**2),
                "temperature_c": int(temp),
                "device": self.device_name,
            }
        except Exception as exc:
            logger.warning("NVML unavailable: %s", exc)
            return {
                "gpu_utilization": 0,
                "memory_used_mb": 0,
                "memory_total_mb": 0,
                "device": self.device_name,
            }

    def optimize_memory(self) -> None:
        """Optimize CUDA memory state for RTX 5050 workloads.

        Safely clears CUDA cache and synchronizes only when CUDA is available.
        """
        if self.cuda_available and self.torch is not None:
            try:
                self.torch.cuda.empty_cache()
                self.torch.cuda.synchronize()
            except Exception as exc:
                logger.warning("CUDA memory optimization skipped: %s", exc)
