"""AMD ROCm/DirectML/OpenCL layer for Radeon 780M (RDNA3).

Implements AMD-standard hardware detection and iGPU screenshot comparison with
OpenCL acceleration and safe CPU fallback behavior.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ROCmLayer:
    """AMD processing layer for Radeon 780M using DirectML/OpenCL/ROCm.

    Target hardware: AMD Radeon 780M iGPU (RDNA3).
    Target APIs: ONNX Runtime DirectML, PyOpenCL, PyTorch ROCm-compatible path.
    """

    def __init__(self) -> None:
        self.directml_available = False
        self.opencl_available = False
        self.rocm_available = False
        self.opencl_platform = None
        self._detect_amd_hardware()

    def _detect_amd_hardware(self) -> None:
        """Detect AMD acceleration APIs and log availability."""
        try:
            import onnxruntime as ort

            providers = ort.get_available_providers()
            if "DmlExecutionProvider" in providers:
                self.directml_available = True
                logger.info("AMD DirectML available for Radeon 780M.")
        except Exception as exc:
            logger.debug("DirectML detection skipped: %s", exc)

        try:
            import pyopencl as cl

            platforms = cl.get_platforms()
            for platform in platforms:
                name = getattr(platform, "name", "")
                if "AMD" in name or "Radeon" in name:
                    self.opencl_available = True
                    self.opencl_platform = platform
                    logger.info("AMD OpenCL available: %s", name)
                    break
        except Exception as exc:
            logger.debug("OpenCL detection skipped: %s", exc)

        try:
            import torch

            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                if "AMD" in device_name or "Radeon" in device_name:
                    self.rocm_available = True
                    logger.info("AMD ROCm-compatible torch device: %s", device_name)
        except Exception as exc:
            logger.debug("ROCm torch detection skipped: %s", exc)

    def screen_compare_igpu(self, img1_path: str, img2_path: str) -> float:
        """Compare screenshots using Radeon 780M OpenCL with CPU fallback.

        Returns mean absolute pixel difference score.
        """
        try:
            import cv2
            import numpy as np
        except ImportError:
            return 100.0

        img1 = cv2.imread(img1_path)
        img2 = cv2.imread(img2_path)
        if img1 is None or img2 is None:
            return 100.0

        if img1.shape != img2.shape:
            img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))

        if self.opencl_available and self.opencl_platform is not None:
            try:
                import pyopencl as cl

                devices = self.opencl_platform.get_devices()
                if not devices:
                    raise RuntimeError("No OpenCL devices available")

                ctx = cl.Context(devices=devices)
                queue = cl.CommandQueue(ctx)

                a = img1.astype(np.float32).ravel()
                b = img2.astype(np.float32).ravel()
                out = np.zeros(1, dtype=np.float32)

                mf = cl.mem_flags
                a_buf = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=a)
                b_buf = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=b)
                out_buf = cl.Buffer(ctx, mf.WRITE_ONLY, out.nbytes)

                program = cl.Program(
                    ctx,
                    """
                    __kernel void diff_mean(
                        __global const float *a,
                        __global const float *b,
                        __global float *out,
                        const int n
                    ) {
                        float sum = 0.0f;
                        for (int i = 0; i < n; ++i) {
                            sum += fabs(a[i] - b[i]);
                        }
                        out[0] = sum / (float)n;
                    }
                    """,
                ).build()

                program.diff_mean(
                    queue,
                    (1,),
                    None,
                    a_buf,
                    b_buf,
                    out_buf,
                    np.int32(a.size),
                )
                cl.enqueue_copy(queue, out, out_buf)
                queue.finish()
                return float(out[0])
            except Exception as exc:
                logger.warning("OpenCL compare failed, using CPU: %s", exc)

        diff = cv2.absdiff(img1, img2)
        return float(np.mean(diff))

    def get_status(self) -> dict:
        """Return AMD device capability status for Radeon 780M."""
        return {
            "device": "AMD Radeon 780M",
            "architecture": "RDNA3",
            "directml": self.directml_available,
            "opencl": self.opencl_available,
            "rocm": self.rocm_available,
            "recommended": (
                "DirectML"
                if self.directml_available
                else "OpenCL"
                if self.opencl_available
                else "CPU fallback"
            ),
        }
