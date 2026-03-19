# AMD Setup Guide (Radeon 780M + Ryzen AI NPU)

This guide configures Advanced Clevrr for AMD iGPU acceleration (Radeon 780M) and Ryzen AI NPU usage through DirectML/OpenCL paths.

## 1) Check Radeon 780M Detection

Windows PowerShell:

```powershell
Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion
```

Expected:
- `AMD Radeon 780M` appears in the output

## 2) Install AMD Ryzen AI Software

Install AMD Ryzen AI Software SDK and required runtime from AMD official channels.

After installation, reboot and verify ONNX Runtime providers in Python.

## 3) Install ONNX Runtime DirectML (for NPU/DirectML)

```bash
python -m pip install onnxruntime-directml
```

Verify provider list:

```bash
python -c "import onnxruntime as ort; print(ort.get_available_providers())"
```

Expected provider includes:
- `DmlExecutionProvider`

## 4) Install PyOpenCL (for Radeon 780M OpenCL)

```bash
python -m pip install pyopencl
```

Verify OpenCL:

```bash
python -c "import pyopencl as cl; print([p.name for p in cl.get_platforms()])"
```

Expected:
- At least one platform containing `AMD` or `Radeon`

## 5) Verify Clevrr AMD Layers

```bash
python -c "from amd.rocm_layer import ROCmLayer; r=ROCmLayer(); print(r.get_status())"
python -c "from amd.npu_layer import NPULayer; n=NPULayer({}); print(n.get_power_usage())"
```

## Troubleshooting

### `DmlExecutionProvider` missing
- Install `onnxruntime-directml` (not plain `onnxruntime`)
- Update AMD graphics and chipset drivers
- Reboot and retry

### OpenCL platforms not found
- Install/update AMD Adrenalin driver
- Confirm Radeon 780M appears in Device Manager
- Reopen terminal after driver install

### NPU fallback to CPU
- Ensure Ryzen AI Software is installed
- Confirm DirectML provider availability
- Check model path exists for NPU inference (`data/npu_models/wake_word.onnx`)

### Performance lower than expected
- Use latest AMD graphics driver
- Close heavy background apps
- Keep power profile on `Best performance`
