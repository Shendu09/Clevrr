"""GPU benchmark suite for Clevrr hardware paths.

Compares CPU and accelerator paths (RTX 5050 CUDA and Radeon 780M/OpenCL where
available) for screen diff, voice inference, and host-device memory transfer.
"""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class TimingResult:
    mean_ms: float
    min_ms: float
    max_ms: float


class GPUBenchmark:
    """Benchmark utilities for CPU, RTX 5050, and Radeon 780M paths."""

    def __init__(self) -> None:
        self.results: Dict[str, Any] = {}

    def benchmark_screen_compare(self) -> Dict[str, Any]:
        """Benchmark screenshot comparison on CPU vs GPU across 10 iterations."""
        import cv2
        import numpy as np

        h, w = 1080, 1920
        img1 = (np.random.rand(h, w, 3) * 255).astype(np.uint8)
        img2 = img1.copy()
        img2[200:300, 300:500] = 255 - img2[200:300, 300:500]

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f1, tempfile.NamedTemporaryFile(
            suffix=".png", delete=False
        ) as f2:
            p1, p2 = f1.name, f2.name

        cv2.imwrite(p1, img1)
        cv2.imwrite(p2, img2)

        try:
            cpu_times = []
            for _ in range(10):
                start = time.perf_counter()
                diff = cv2.absdiff(img1, img2)
                _ = float(np.mean(diff))
                end = time.perf_counter()
                cpu_times.append((end - start) * 1000.0)

            cpu_result = {
                "mean_ms": float(np.mean(cpu_times)),
                "min_ms": float(np.min(cpu_times)),
                "max_ms": float(np.max(cpu_times)),
            }

            gpu_result: Dict[str, Any] = {"available": False}
            try:
                from cuda.gpu_kernels import CUDAKernels

                kernels = CUDAKernels()
                gpu_times = []
                for _ in range(10):
                    start = time.perf_counter()
                    _ = kernels.screen_diff_gpu(p1, p2)
                    end = time.perf_counter()
                    gpu_times.append((end - start) * 1000.0)

                gpu_result = {
                    "available": True,
                    "mean_ms": float(np.mean(gpu_times)),
                    "min_ms": float(np.min(gpu_times)),
                    "max_ms": float(np.max(gpu_times)),
                    "processor": getattr(kernels, "device_name", "gpu"),
                }
            except Exception as exc:
                gpu_result = {"available": False, "reason": str(exc)}

            result = {"cpu": cpu_result, "gpu": gpu_result}
            self.results["screen_compare"] = result
            self._print_table(
                "Screen Compare (10 runs)",
                [
                    ("CPU", cpu_result["mean_ms"], cpu_result["min_ms"], cpu_result["max_ms"]),
                    (
                        "GPU",
                        gpu_result.get("mean_ms", 0.0),
                        gpu_result.get("min_ms", 0.0),
                        gpu_result.get("max_ms", 0.0),
                    ),
                ],
            )
            return result
        finally:
            for path in (p1, p2):
                try:
                    os.remove(path)
                except Exception:
                    pass

    def benchmark_voice_recognition(self) -> Dict[str, Any]:
        """Benchmark whisper tiny CPU vs faster-whisper GPU on 5s sample."""
        import numpy as np
        import soundfile as sf

        sample_rate = 16000
        duration_sec = 5
        audio = np.zeros(sample_rate * duration_sec, dtype=np.float32)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
            audio_path = temp.name
        sf.write(audio_path, audio, sample_rate)

        try:
            cpu_ms = None
            gpu_ms = None

            try:
                import whisper

                model = whisper.load_model("tiny")
                start = time.perf_counter()
                _ = model.transcribe(audio_path, language="en")
                end = time.perf_counter()
                cpu_ms = (end - start) * 1000.0
            except Exception:
                cpu_ms = None

            try:
                from faster_whisper import WhisperModel

                device = "cuda"
                compute_type = "float16"
                model = WhisperModel("tiny", device=device, compute_type=compute_type)
                start = time.perf_counter()
                _segments, _info = model.transcribe(audio_path, language="en")
                end = time.perf_counter()
                gpu_ms = (end - start) * 1000.0
            except Exception:
                gpu_ms = None

            speedup = None
            if cpu_ms and gpu_ms and gpu_ms > 0:
                speedup = cpu_ms / gpu_ms

            result = {
                "cpu_ms": cpu_ms,
                "gpu_ms": gpu_ms,
                "speedup_factor": speedup,
            }
            self.results["voice_recognition"] = result

            print("\nVoice Recognition (5s sample)")
            print("-" * 46)
            print(f"CPU whisper tiny : {cpu_ms if cpu_ms is not None else 'unavailable'} ms")
            print(f"GPU faster-whisper: {gpu_ms if gpu_ms is not None else 'unavailable'} ms")
            print(f"Speedup factor    : {speedup if speedup is not None else 'n/a'}")
            return result
        finally:
            try:
                os.remove(audio_path)
            except Exception:
                pass

    def benchmark_memory_transfer(self) -> Dict[str, Any]:
        """Measure numpy-to-GPU transfer throughput in GB/s."""
        import numpy as np

        size_mb = 256
        arr = np.random.rand((size_mb * 1024 * 1024) // 4).astype(np.float32)

        try:
            import torch

            if not torch.cuda.is_available():
                result = {"available": False, "throughput_gbps": 0.0, "reason": "cuda_unavailable"}
                self.results["memory_transfer"] = result
                return result

            torch.cuda.synchronize()
            start = time.perf_counter()
            tensor = torch.from_numpy(arr).to("cuda", non_blocking=False)
            torch.cuda.synchronize()
            end = time.perf_counter()

            elapsed = max(end - start, 1e-9)
            gb_transferred = arr.nbytes / (1024**3)
            throughput = gb_transferred / elapsed
            _ = tensor

            result = {"available": True, "size_mb": size_mb, "throughput_gbps": float(throughput)}
            self.results["memory_transfer"] = result
            return result
        except Exception as exc:
            result = {"available": False, "throughput_gbps": 0.0, "reason": str(exc)}
            self.results["memory_transfer"] = result
            return result

    def run_all(self) -> Dict[str, Any]:
        """Run all benchmark groups and return aggregated results."""
        self.results = {}
        self.benchmark_screen_compare()
        self.benchmark_voice_recognition()
        self.benchmark_memory_transfer()
        return self.results

    @staticmethod
    def _print_table(title: str, rows: list[tuple[str, float, float, float]]) -> None:
        print(f"\n{title}")
        print("-" * 68)
        print(f"{'Path':<12} {'Mean(ms)':>12} {'Min(ms)':>12} {'Max(ms)':>12}")
        print("-" * 68)
        for path, mean, min_v, max_v in rows:
            print(f"{path:<12} {mean:>12.3f} {min_v:>12.3f} {max_v:>12.3f}")


if __name__ == "__main__":
    benchmark = GPUBenchmark()
    results = benchmark.run_all()

    print("\nOverall Benchmark Summary")
    print("=" * 68)
    for key, value in results.items():
        print(f"{key}: {value}")
