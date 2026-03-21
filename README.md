# Advanced Clevrr Computer

100% local AI computer-control agent built with Python + Ollama.

No cloud APIs are required for task execution after local setup.

## What It Does

- Runs natural-language computer tasks through an orchestrator agent
- Supports a fast AI Layer mode for common voice/system actions
- Controls apps via a fallback chain: app-specific → browser → UIAutomation → vision
- Adds local memory, semantic recall, safety rules, and threat checks
- Supports optional always-on voice control with wake word routing

## Runtime Modes

- `orchestrator` (default): full planning/execution loop
- `layer`: fast routing path with instincts/hooks/checkpoints + orchestrator fallback

Run modes:

```bash
python main.py
python main.py --mode orchestrator
python main.py --mode layer
python main.py --mode layer --voice
```

## Prerequisites

- Python 3.10+
- Ollama installed and running locally (`http://localhost:11434`)
- Required Ollama models:
  - `llava`
  - `llama3`

Install and verify Ollama:

```bash
ollama serve
ollama pull llava
ollama pull llama3
ollama list
```

## Installation

From the `advanced-clevrr` folder:

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

## First-Time Setup Wizard

Use built-in setup checks for Python, Ollama, models, dependencies, and directories:

```bash
python main.py --setup
```

## CLI Usage

Main options from `main.py`:

```bash
python main.py --help
```

Examples:

```bash
# Dashboard (default)
python main.py

# Voice-enabled orchestrator mode
python main.py --voice

# Layer mode with voice
python main.py --mode layer --voice

# Run one task and exit
python main.py --task "Open Notepad and type hello"

# Floating overlay UI
python main.py --ui floating

# No UI (usually with --task)
python main.py --ui none --task "Take screenshot"

# Override vision model from config
python main.py --model llava
```

## Key Components

- `core/ai_layer.py`: high-speed routing layer
- `core/instinct_system.py`: reusable action patterns
- `core/hook_system.py`: async lifecycle hooks
- `core/verification_loop.py`: checkpoints + step verification
- `core/skills_loader.py`: intent-based skill loading
- `core/memory_optimizer.py`: memory compaction
- `agents/orchestrator.py`: full orchestrator pipeline
- `app_control/universal_controller.py`: multi-controller fallback router
- `security/threat_detector.py`: prompt/threat scanning
- `utils/safety_guard.py`: allow/confirm/block policy enforcement

## Voice and Safety

Voice behavior and auth are configured in `config/settings.yaml`:

- `voice.enabled`
- `voice.wake_word`
- `voice.require_voice_auth`
- `voice.auth_threshold`

Safety rules are defined in:

- `config/safety_rules.yaml`

## Tests

Run tests from the project root:

```bash
python -m pytest -v
```

## Troubleshooting

- If startup fails, run `python main.py --setup` first.
- If Ollama check fails, ensure `ollama serve` is running.
- If model pull fails, run pulls manually (`ollama pull llava`, `ollama pull llama3`).
- If browser control fails, reinstall Playwright Chromium.

## Project Structure (High Level)

```text
advanced-clevrr/
  agents/        # planning/execution/validation agents
  app_control/   # app/browser/uia/vision controllers
  core/          # AI layer systems, hooks, verification, memory optimizer
  security/      # threat detection + voice auth
  ui/            # gradio dashboard + floating UI
  utils/         # ollama, memory, safety, voice, capture utilities
  config/        # settings + safety rules
  data/          # logs, screenshots, runtime data
```
