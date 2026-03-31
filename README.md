# Advanced Clevrr Computer

100% local AI computer-control agent built with Python + Ollama.

No cloud APIs are required for core task execution after local setup.
Optional Auth0 integration is available for connected third-party actions.

## Project Description

Advanced Clevrr is a local-first AI assistant framework for automating desktop and browser workflows. It combines:

- multi-agent orchestration (planning, execution, validation)
- modular action plugins (Gmail, GitHub, Calendar)
- layered computer control (app-specific, browser automation, UIAutomation, vision)
- optional voice interaction and dashboard UI
- built-in safety, policy checks, and optional Auth0-backed connected actions

The architecture is organized so core runtime systems (`core/`), action integrations (`actions/`), and control adapters (`app_control/`, `os_control/`) stay decoupled and extensible.

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
python main.py                                    # Orchestrator mode + Gradio dashboard
python main.py --mode orchestrator --ui overlay   # Orchestrator + Electron overlay
python main.py --mode layer --voice               # AILayer + voice control
python main.py --task "Open Notepad"              # Single task (with intelligent routing)
python main.py --setup                            # First-time setup wizard
```

## UI Modes

```bash
python main.py --ui gradio      # Web-based dashboard (default)
python main.py --ui overlay     # Transparent Electron overlay (hotkey: Win+Shift+Space)
python main.py --ui floating    # Floating window overlay
python main.py --ui none        # No UI (use --task for commands)
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
- `tests/test_computer_use.py`

## Troubleshooting

- If startup fails, run `python main.py --setup` first.
- If Ollama check fails, ensure `ollama serve` is running.
- If model pull fails, run pulls manually (`ollama pull llava`, `ollama pull llama3`).
- If browser control fails, reinstall Playwright Chromium.

## Project Structure

```text
advanced-clevrr/
  main.py                  # main CLI entrypoint
  run_dashboard.py         # launch dashboard mode
  clevrr_service.py        # service runtime integration
  cleanup.py               # maintenance/cleanup helpers
  README.md
  SETUP.md
  requirements.txt
  clevrr.ini

  actions/                 # connected service actions
    base_action.py
    gmail_action.py
    github_action.py
    calendar_action.py

  agents/                  # agent pipeline components
    orchestrator.py
    planner_agent.py
    executor_agent.py
    validator_agent.py
    vision_agent.py
    competitive_programmer.py

  app_control/             # UI/browser/app-level control adapters
    universal_controller.py
    browser_controller.py
    uia_controller.py
    vision_controller.py
    spotify_controller.py
    whatsapp_controller.py
    input_controller.py

  os_control/              # OS-level app/process/window/file operations
    app_launcher.py
    process_manager.py
    window_manager.py
    file_manager.py

  core/                    # core runtime subsystems
    ai_layer.py
    instinct_system.py
    hook_system.py
    verification_loop.py
    skills_loader.py
    memory_optimizer.py
    auth/                  # Auth0 + token vault + step-up auth
    brain/                 # intent parsing, routing, memory, brain engine
    bus/                   # IPC transport, queues, topics, metrics
    computer_use/          # computer-use abstractions
    security/              # policy, threat, and access-control systems
    service/               # service-layer runtime components
    voice/                 # speech/wake-word pipeline

  dashboard/               # dashboard app + templates
  ui/                      # user-facing dashboard/floating UI
  utils/                   # shared utilities (safety, memory, capture, voice)
  config/                  # settings.yaml and safety_rules.yaml
  data/                    # logs and runtime artifacts
  clevrr_data/             # local model/runtime data cache
  docs/                    # setup/hardware documentation
  installer/               # platform-specific installers
  skills/                  # skill packs (app launch, system control, voice)
  tests/                   # automated test suite
    test_computer_use.py
```
