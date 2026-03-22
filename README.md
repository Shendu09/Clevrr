# Advanced Clevrr Computer

100% local AI computer-control agent built with Python + Ollama.

No cloud APIs are required for core task execution after local setup.
Optional Auth0 integration is available for connected third-party actions.

## What It Does

- Runs natural-language computer tasks through an orchestrator agent
- Supports a fast AI Layer mode for common voice/system actions
- Controls apps via a fallback chain: app-specific → browser → UIAutomation → vision
- Adds local memory, semantic recall, safety rules, and threat checks
- Supports optional always-on voice control with wake word routing
- Supports optional Auth0 Token Vault-based action execution (Gmail/GitHub/Calendar)
- Includes an AI Brain layer for intent parsing, routing, and response publishing

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

## Optional Auth0 Setup (Token Vault)

If you want connected service actions (Gmail/GitHub/Calendar), configure Auth0 credentials:

```bash
copy .env.example .env
```

Set these keys in `.env`:

- `AUTH0_DOMAIN`
- `AUTH0_CLIENT_ID`
- `AUTH0_CLIENT_SECRET`
- `AUTH0_AUDIENCE`

Security note: never commit `.env`.

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

- `core/security/`: RBAC, threat detection, sandbox execution, audit logging
- `core/service/`: system service runtime components
- `core/bus/`: optimized IPC message bus
- `core/voice/`: voice capture, wake-word, transcription, and pipeline
- `core/auth/`: Auth0 config, token vault, step-up auth, consent manager
- `core/brain/`: intent parser, action router, memory, and brain engine
- `actions/`: Gmail/GitHub/Calendar action implementations
- `core/ai_layer.py`: high-speed routing layer
- `core/instinct_system.py`: reusable action patterns
- `core/hook_system.py`: async lifecycle hooks
- `core/verification_loop.py`: checkpoints + step verification
- `core/skills_loader.py`: intent-based skill loading
- `core/memory_optimizer.py`: memory compaction
- `agents/orchestrator.py`: full orchestrator pipeline
- `app_control/universal_controller.py`: multi-controller fallback router
- `core/security/threat_detector.py`: prompt/threat scanning
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

Current suite includes:

- `tests/test_security.py`
- `tests/test_bus.py`
- `tests/test_voice.py`
- `tests/test_auth.py`
- `tests/test_brain.py`

## Troubleshooting

- If startup fails, run `python main.py --setup` first.
- If Ollama check fails, ensure `ollama serve` is running.
- If model pull fails, run pulls manually (`ollama pull llava`, `ollama pull llama3`).
- If browser control fails, reinstall Playwright Chromium.

## Project Structure (High Level)

```text
advanced-clevrr/
  actions/       # connected service actions (gmail/github/calendar)
  agents/        # planning/execution/validation agents
  app_control/   # app/browser/uia/vision controllers
  core/          # security, service, bus, voice, auth, brain, ai-layer systems
  ui/            # gradio dashboard + floating UI
  utils/         # ollama, memory, safety, voice, capture utilities
  config/        # settings + safety rules
  data/          # logs, screenshots, runtime data
```
