# Advanced Clevrr Computer

100% local AI computer-control agent built with Python + Ollama.

No cloud APIs are required for core task execution after local setup.
Optional Auth0 integration is available for connected third-party actions.

**Latest: CLOVIS-Level Event Loop Architecture (Phase 5)** — Continuous autonomous operation with persistent models, real-time dashboard, and <1 second task execution.

## Project Description

Advanced Clevrr is a local-first AI assistant framework for automating desktop and browser workflows. It combines:

- **CLOVIS-level continuous event loop** with persistent models and instant task execution
- multi-agent orchestration (planning, execution, validation)
- modular action plugins (Gmail, GitHub, Calendar)
- layered computer control (app-specific, browser automation, UIAutomation, vision)
- persistent episodic and procedural memory with semantic recall
- optional voice interaction and real-time monitoring dashboard
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

**Event Loop Mode (Recommended)** — Continuous AI agent with persistent models:

```bash
python run_event_loop.py                      # Start continuous event loop + dashboard (http://localhost:7862)
python run_event_loop.py --dashboard-port 7863  # Custom dashboard port
python run_event_loop.py --verbose            # Debug logging
```

**Legacy Modes** — Single-task or interactive modes:

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

## Event Loop Architecture (Phase 5)

The Event Loop mode implements CLOVIS-level continuous AI operation:

**Key Features:**
- **Persistent Models**: Ollama models loaded once at startup and stay in memory (zero reload overhead)
- **Continuous Operation**: Async event loop processes tasks from queue in real-time
- **Real-Time Dashboard**: Live monitoring at `http://localhost:7862` with:
  - System status (event loop, models, task queue)
  - Agent health monitoring
  - Memory statistics
  - Task submission form
  - Event history and metrics
- **Sub-Second Execution**: Simple tasks complete in <1 second (no model loading lag)
- **Persistent Session**: Tracks lifetime stats (total tasks, success rate, uptime, average duration)
- **Semantic Memory**: Find similar past episodes and reuse working procedures
- **Self-Healing**: Detects issues and attempts recovery automatically

**How It Works:**
1. Event loop starts and creates persistent session
2. All models load once (`llava`, `llama3`, `codellama`)
3. Dashboard launches and awaits user commands
4. User submits task via dashboard
5. Task enters priority queue
6. Event loop processes task through orchestrator (planning → execution → validation)
7. Result displayed in real-time on dashboard
8. Models remain loaded for next task

**Performance:**
- First task: ~3-5 seconds (initialization)
- Subsequent tasks: <1 second for simple actions (e.g., click, type)
- Complex tasks: 10-30 seconds (planning + multi-step execution)
- No model reload between tasks

## Key Components

**Event Loop & Continuous Operation (Phase 5):**
- `run_event_loop.py`: Main entry point for continuous AI agent
- `core/event_loop.py`: SystemEventLoop with event bus and async processing
- `core/session_manager.py`: PersistentSession for lifetime stats and task queuing
- `core/system_server.py`: Master coordinator for all components
- `ui/enhanced_dashboard.py`: Real-time monitoring dashboard (Gradio-based)
- `core/router_service.py`: Intelligent task routing to appropriate handlers

**Agents & Orchestration:**
- `agents/orchestrator.py`: full orchestrator pipeline (planning → execution → validation)
- `agents/planner_agent.py`: LLM-based multi-step planning
- `agents/executor_agent.py`: Action execution with self-healing
- `agents/validator_agent.py`: Vision-based result validation
- `agents/vision_agent.py`: Screen analysis and intent detection

**Core Systems:**
- `core/security/`: RBAC, threat detection, sandbox execution, audit logging
- `core/service/`: system service runtime components
- `core/bus/`: optimized IPC message bus
- `core/voice/`: voice capture, wake-word, transcription, and pipeline
- `core/auth/`: Auth0 config, token vault, step-up auth, consent manager
- `core/brain/`: intent parser, action router, memory, and brain engine
- `core/ai_layer.py`: high-speed routing layer
- `core/instinct_system.py`: reusable action patterns
- `core/hook_system.py`: async lifecycle hooks
- `core/verification_loop.py`: checkpoints + step verification
- `core/skills_loader.py`: intent-based skill loading
- `core/memory_optimizer.py`: memory compaction

**Memory & Computer Control:**
- `utils/memory_system.py`: persistent episodic & procedural memory with embeddings
- `app_control/universal_controller.py`: multi-controller fallback router

**Security & Safety:**
- `core/security/threat_detector.py`: prompt/threat scanning
- `utils/safety_guard.py`: allow/confirm/block policy enforcement

**Actions & Integrations:**
- `actions/`: Gmail/GitHub/Calendar action implementations

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

**Event Loop Mode:**
- If dashboard port is already in use, specify a different port: `python run_event_loop.py --dashboard-port 7863`
- If models fail to load, check: `ollama list` (should show `llava`, `llama3`, `codellama`)
- If task execution hangs, check the event loop logs for "ERROR" messages
- Memory KeyError fixed: Using `.get()` for safe dictionary access in orchestrator
- If memory database is corrupted, delete `data/memory.db` and restart (it will recreate automatically)

**General:**
- If startup fails, run `python main.py --setup` first.
- If Ollama check fails, ensure `ollama serve` is running.
- If model pull fails, run pulls manually (`ollama pull llava`, `ollama pull llama3`).
- If browser control fails, reinstall Playwright Chromium.

## Project Structure

```text
advanced-clevrr/
  main.py                  # legacy CLI entrypoint
  run_event_loop.py        # CLOVIS event loop entrypoint (RECOMMENDED)
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
    event_loop.py          # continuous async operation + event bus
    session_manager.py     # persistent session + task queue + stats
    system_server.py       # master coordinator
    router_service.py      # intelligent task routing
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
  ui/                      # user-facing UI
    enhanced_dashboard.py  # real-time monitoring dashboard (event loop)
    floating_ui.py         # floating window overlay
  utils/                   # shared utilities
    memory_system.py       # persistent episodic & procedural memory
    safety_guard.py        # policy enforcement
    screen_capture.py      # screenshot utilities
    voice_controller.py    # voice control utilities
    self_healer.py         # automatic recovery
    ollama_client.py       # Ollama integration
  config/                  # settings.yaml and safety_rules.yaml
  data/                    # logs and runtime artifacts
    memory.db              # persistent memory database
    logs/                  # application logs
    screenshots/           # captured screenshots
  clevrr_data/             # local model/runtime data cache
  docs/                    # setup/hardware documentation
  installer/               # platform-specific installers
  skills/                  # skill packs (app launch, system control, voice)
  tests/                   # automated test suite
    test_computer_use.py
```

## Recent Improvements (Phase 5)

**Bug Fixes & Robustness:**
- Fixed KeyError in orchestrator memory lookup by adding defensive `.get()` access for procedure dictionary keys
- Fixed memory system keyword search fallback to properly format results for each table type (procedures, episodes, knowledge)
- Improved error handling in orchestrator with safe dictionary access and default values

**Performance Enhancements:**
- Persistent model loading: Models stay in memory between tasks (zero reload overhead)
- Optimized event loop with priority-based task scheduling
- Screenshot caching for rapid diff detection
- Semantic similarity search for reusing past procedures
- Sub-second task execution for simple actions

**New Dashboard Features:**
- Real-time system status monitoring
- Task queue visualization
- Agent health status display
- Memory statistics and event history
- Task submission form with instant results

## Performance Benchmarks

On typical hardware (GPU or high-end CPU):

| Task Type | First Run | Subsequent Runs |
|-----------|-----------|-----------------|
| Simple click | ~4s | <1s |
| Type text | ~4s | <1s |
| Open app | ~5s | 2-3s |
| Complex sequence | ~15-30s | 10-20s |
| Browser navigation | ~8-12s | 4-6s |

*Times include vision analysis, planning, and execution. No model loading after first task.*

## License

This project is provided as-is for educational and research purposes.

## Contributing

Contributions are welcome. Please review the codebase structure and test suite before submitting pull requests.
