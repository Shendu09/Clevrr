# Clevrr Hardware Guide

This guide explains how Advanced Clevrr uses RTX 5050, Radeon 780M, and Ryzen AI NPU together.

## 1) RTX 5050 Usage in Clevrr

Primary role:
- LLM inference
- Vision AI analysis
- Speech-to-text acceleration
- CUDA/Tensor Core workloads

Typical modules:
- `cuda/gpu_kernels.py`
- `cuda/tensorrt_optimizer.py`

## 2) Radeon 780M Usage in Clevrr

Primary role:
- Background image/screen compare workloads
- Offloading non-critical compute from RTX 5050

Typical modules:
- `amd/rocm_layer.py`

APIs:
- DirectML (Windows)
- OpenCL (cross-platform)

## 3) Ryzen AI NPU Usage in Clevrr

Primary role:
- Always-on wake-word detection
- Ultra-low-power inference loop

Typical module:
- `amd/npu_layer.py`

API:
- ONNX Runtime DirectML provider (XDNA-oriented runtime path)

## 4) Power Consumption Comparison

| Processor | Typical Clevrr Role | Estimated Power |
|---|---|---:|
| Ryzen AI NPU | Always-on wake word | < 1W |
| CPU fallback | Wake-word fallback | ~5W |
| Radeon 780M iGPU | Screen/background tasks | 5-20W |
| RTX 5050 | Heavy AI inference | 60W+ (workload dependent) |

## 5) VRAM / Memory Usage Breakdown

| Workload | Preferred Processor | Memory Focus |
|---|---|---|
| Screen compare | Radeon 780M | Shared iGPU memory |
| Vision model inference | RTX 5050 | Dedicated VRAM |
| LLM generation | RTX 5050 | Dedicated VRAM |
| Wake-word always-on | Ryzen AI NPU | NPU/runtime buffers |

## 6) When to Use Colab Hybrid Mode

Use Colab hybrid mode when:
- Local VRAM is insufficient for selected model size
- You need temporary burst capacity for large inference jobs
- Local thermals/power budget must stay low

Prefer local mode when:
- Latency and privacy are top priorities
- Models fit local hardware comfortably

## 7) Performance Benchmarks (Reference Layout)

| Benchmark | CPU | Radeon 780M | RTX 5050 |
|---|---:|---:|---:|
| Screen compare (ms) | baseline | improved | fastest |
| Voice inference (ms) | baseline | n/a/assist | fastest |
| Tensor transfer (GB/s) | n/a | moderate | highest |

Run project benchmark script:

```bash
python benchmarks/gpu_benchmark.py
```

Use generated numbers from your machine to replace reference values.
