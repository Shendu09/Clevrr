# NVIDIA Setup Guide (RTX 5050 + CUDA)

This guide configures Advanced Clevrr for NVIDIA GPU acceleration using CUDA, Tensor Cores, and local model inference.

## 1) Check NVIDIA GPU and Driver

Run:

```bash
nvidia-smi
```

Expected:
- GPU listed (for example `RTX 5050`)
- Driver installed
- CUDA runtime version shown

If `nvidia-smi` is missing:
- Install latest NVIDIA driver from NVIDIA official site
- Reboot and retry

## 2) Install CUDA Toolkit

Install CUDA toolkit from NVIDIA developer portal:
- https://developer.nvidia.com/cuda-downloads

Recommended for this project:
- CUDA toolkit 12.4+ (project code is compatible with modern CUDA; CUDA 13.0-ready patterns are used)

After install, verify:

```bash
nvcc --version
```

## 3) Install PyTorch with CUDA 12.4 Wheel

From your project virtual environment:

```bash
python -m pip install --upgrade pip
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

Verify:

```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

## 4) Install faster-whisper for GPU Voice Inference

```bash
python -m pip install faster-whisper
```

Quick check:

```bash
python -c "from faster_whisper import WhisperModel; m=WhisperModel('tiny', device='cuda', compute_type='float16'); print('faster-whisper CUDA ready')"
```

## 5) Install pynvml for GPU Monitoring

```bash
python -m pip install pynvml
```

Check:

```bash
python -c "import pynvml; pynvml.nvmlInit(); h=pynvml.nvmlDeviceGetHandleByIndex(0); print(pynvml.nvmlDeviceGetName(h))"
```

## 6) Verify Clevrr CUDA Layer

```bash
python -c "from cuda.gpu_kernels import CUDAKernels; k=CUDAKernels(); print('CUDA ready:', k.device_name)"
python -c "from cuda.tensorrt_optimizer import TensorRTOptimizer; t=TensorRTOptimizer(); print('Precision:', t.get_optimal_precision())"
```

## Troubleshooting

### CUDA not available in PyTorch
- Ensure CUDA PyTorch wheel was installed (cu124 index URL)
- Check driver compatibility with installed CUDA runtime
- Restart shell/IDE after installation

### `nvidia-smi` works but Python still uses CPU
- Confirm you are in the correct virtual environment
- Reinstall torch with CUDA wheel
- Run check command again

### faster-whisper fails on GPU
- Ensure `torch.cuda.is_available()` is `True`
- Use `compute_type='float16'`
- Update NVIDIA driver and retry

### NVML errors (`pynvml`)
- Update driver
- Verify GPU visibility with `nvidia-smi`
- Retry from elevated shell if access is restricted
