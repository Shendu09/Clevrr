# 🤖 Advanced Clevrr Computer — Setup Guide

**100% Local AI Computer Control Agent**  
Zero APIs · Zero Cloud · Zero API Keys · Full Offline Operation

---

## 📋 Prerequisites

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **Python** | 3.10+ | 3.11+ |
| **RAM** | 8 GB | 16 GB |
| **Disk Space** | 10 GB (for AI models) | 15 GB |
| **OS** | Windows 10 / Linux | Windows 11 |
| **GPU** | Not required | NVIDIA GPU (faster inference) |

---

## 🛠 Step 1: Install Ollama

Ollama is the local AI runtime that powers all LLM and vision features.  
It runs as a background service on your machine.

### Windows
1. Download the installer from **[https://ollama.ai](https://ollama.ai)**
2. Run the installer and follow the prompts
3. Ollama will start automatically as a system service

### macOS
```bash
brew install ollama
```

### Linux
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### Verify Installation
```bash
ollama --version
```

---

## 🧠 Step 2: Pull Required Models

These models download once and run fully offline afterwards.

```bash
# Start Ollama (if not running)
ollama serve

# Pull the vision model (~4.7 GB)
ollama pull llava

# Pull the text reasoning model (~4.7 GB)
ollama pull llama3
```

### Verify Models
```bash
ollama list
```

You should see both `llava` and `llama3` in the output.

---

## 🐍 Step 3: Install Python Dependencies

```bash
# Navigate to the project directory
cd advanced-clevrr

# Create a virtual environment (recommended)
python -m venv venv

# Activate the virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
```

---

## 🎤 Step 4: Install Voice Support (Optional)

Voice control requires additional setup:

```bash
# Install Whisper for local speech-to-text
pip install openai-whisper

# Install additional audio tools
pip install sounddevice soundfile
```

### FFmpeg (Required for Whisper)

**Windows:**
1. Download from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
2. Add to system PATH

**macOS:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg
```

---

## 🚀 Step 5: First Run

### Quick Setup Wizard
```bash
python main.py --setup
```

This will:
- ✅ Check Python version
- ✅ Verify Ollama is running
- ✅ Check/pull required models
- ✅ Verify all dependencies
- ✅ Create data directories

### Launch the Agent
```bash
# Default: Gradio web dashboard at http://localhost:7860
python main.py

# With voice control
python main.py --voice

# Run a single task
python main.py --task "Open Notepad and type Hello World"

# Floating overlay UI
python main.py --ui floating

# No UI (task mode only)
python main.py --ui none --task "Open Calculator"
```

---

## 📖 Usage Examples

```bash
# Open an application
python main.py --task "Open Google Chrome"

# Type something
python main.py --task "Open Notepad, type 'Meeting at 3pm', and save the file"

# Multi-step task
python main.py --task "Open File Explorer and navigate to Documents"

# Launch dashboard for interactive use
python main.py
```

---

## 🔧 Configuration

All settings are in `config/settings.yaml`:

```yaml
ollama:
  url: "http://localhost:11434"   # Ollama API URL
  vision_model: "llava"           # Vision model name
  text_model: "llama3"            # Text model name
  timeout: 60                     # Request timeout (seconds)

voice:
  enabled: false                  # Enable voice control
  wake_word: "hey computer"       # Wake word phrase
  whisper_model: "base"           # Whisper model size

screen:
  capture_interval: 1.0           # Seconds between captures
  grid_size: 10                   # Grid overlay divisions
  max_screenshots: 50             # Max stored screenshots
```

### Safety Rules

Edit `config/safety_rules.yaml` to customize:
- **always_block**: Actions that are NEVER executed
- **always_confirm**: Actions that require user confirmation

---

## 🔥 Troubleshooting

### ❌ "Ollama is not running"
```bash
# Start the Ollama service
ollama serve

# Or restart it
# Windows: Check system tray, or restart from Services
# Linux: systemctl restart ollama
```

### ❌ "Model not found"
```bash
# Pull the missing model
ollama pull llava
ollama pull llama3

# Verify
ollama list
```

### ❌ "Screenshot not working"
- **Windows**: Run as Administrator if needed
- **Linux**: Install `xdotool` for active window capture:
  ```bash
  sudo apt install xdotool
  ```

### ❌ "Microphone not working"
```bash
# Test microphone access
python -c "import sounddevice; print(sounddevice.query_devices())"

# On Linux, install PortAudio:
sudo apt install portaudio19-dev
pip install sounddevice
```

### ❌ "pyttsx3 not speaking"
```bash
# Windows: Should work out of the box (uses SAPI5)
# Linux: Install espeak
sudo apt install espeak

# macOS: Uses NSSpeechSynthesizer (built-in)
```

### ❌ "Slow inference"
- Ensure you have enough RAM (8 GB minimum, 16 GB recommended)
- Close unnecessary applications
- For faster inference, use a computer with NVIDIA GPU:
  ```bash
  # Ollama auto-detects and uses GPU if available
  nvidia-smi  # Check GPU status
  ```
- Use smaller models if needed:
  ```yaml
  # In settings.yaml
  ollama:
    vision_model: "llava:7b"    # Smaller variant
    text_model: "llama3:8b"     # Smaller variant
  ```

### ❌ "sentence-transformers download fails"
The embedding model downloads once on first run. If it fails:
```bash
# Manual download
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```
After the first download, it works fully offline.

---

## 📁 Project Structure

```
advanced-clevrr/
├── main.py                  # Entry point
├── requirements.txt         # Dependencies
├── SETUP.md                 # This file
├── config/
│   ├── settings.yaml        # Main configuration
│   └── safety_rules.yaml    # Safety rules
├── agents/
│   ├── orchestrator.py      # Master coordinator
│   ├── planner_agent.py     # Task planning (llama3)
│   ├── vision_agent.py      # Screen analysis (llava)
│   ├── executor_agent.py    # Action execution (pyautogui)
│   └── validator_agent.py   # Result validation (llava)
├── utils/
│   ├── ollama_client.py     # Local Ollama communication
│   ├── screen_capture.py    # Screenshot capture (mss)
│   ├── memory_system.py     # SQLite memory (3 types)
│   ├── safety_guard.py      # Action safety filter
│   ├── voice_controller.py  # Voice I/O (Whisper + pyttsx3)
│   ├── self_healer.py       # Auto failure recovery
│   └── element_finder.py    # UI element finder (pywinauto)
├── ui/
│   ├── dashboard.py         # Gradio web dashboard
│   └── floating_ui.py       # Minimal overlay UI
└── data/
    ├── memory.db            # SQLite database (auto-created)
    ├── screenshots/         # Screenshots (auto-managed)
    ├── logs/                # Application logs
    └── safety_log.txt       # Safety decision log
```

---

## 🔒 Privacy & Security

- **100% Local**: All AI processing happens on YOUR machine
- **No Internet Required**: After initial model downloads, works fully offline
- **No API Keys**: Zero external service dependencies
- **No Data Collection**: Nothing leaves your computer
- **Safety Guards**: Dangerous commands are blocked, sensitive ones need approval
- **Logged Actions**: All safety decisions are logged locally

---

## 📝 License

This project is based on [Clevrr-Computer](https://github.com/Clevrr-AI/Clevrr-Computer) 
with significant enhancements for 100% local operation.
