# Advanced Clevrr

Local AI computer automation powered by Ollama and Python.

## Overview

Advanced Clevrr runs computer-control automation locally and supports two runtime paths:

- Orchestrator mode: full planning + execution loop
- Layer mode: fast direct routing for common voice commands

## Core Features

- 100% local inference after first-time model downloads
- Fast app launch with startup app indexing (Windows Start Menu + common install paths)
- Voice control pipeline using Whisper tiny for low-latency routing
- Threat scanning and optional voice-auth checks before execution
- Safety guard decisions for block / confirm / allow behavior
- ECC-inspired task intelligence layer with instincts, hooks, checkpoints, and dynamic skills
- Universal app control with automatic fallback chain (App-specific → Browser → UIAutomation → Vision)

## New AI Layer Systems

The layer mode now includes five integrated intelligence modules:

- Instinct System (`core/instinct_system.py`): learns successful task patterns and reuses high-confidence actions instantly
- Hook System (`core/hook_system.py`): non-blocking lifecycle events for task start, completion, failures, and session activity
- Verification Loop (`core/verification_loop.py`): saves checkpoints and verifies task-step outcomes
- Skills Loader (`core/skills_loader.py`): loads relevant `SKILL.md` guidance based on task intent
- Memory Optimizer (`core/memory_optimizer.py`): compacts old memory episodes when storage pressure rises

These are orchestrated in `core/ai_layer.py` and run asynchronously where possible to keep command response fast.

## Universal App Control

Advanced Clevrr can control any app through layered routing in `app_control/universal_controller.py`:

- WhatsApp: web automation through Playwright (`app_control/whatsapp_controller.py`)
- Spotify: desktop media control and shortcuts (`app_control/spotify_controller.py`)
- Browser actions: navigate/search/read/new-tab/click/type (`app_control/browser_controller.py`)
- Desktop UI control: Windows UI Automation for app windows/elements (`app_control/uia_controller.py`)
- Vision fallback: screenshot + local vision model guidance when semantic control is unavailable (`app_control/vision_controller.py`)

## Runtime Modes

### 1) Orchestrator Mode (default)

```bash
python main.py
python main.py --voice
```

### 2) Layer Mode (fast routing)

```bash
python main.py --mode layer
python main.py --mode layer --voice
```

Layer mode routes common voice actions directly (open/close apps, screenshot, show desktop, system health, window layout, messaging/media/browser control), checks instincts first, and falls back to orchestrator for complex tasks.

## Voice Command Examples (Layer Mode)

- Open/launch apps: open chrome, launch notepad, start calculator
- Close apps/windows: close chrome, quit notepad
- System actions: take screenshot, show desktop, lock computer
- Utility actions: organize downloads, system health, what is open
- Window layout: side by side
- Browser control: go to youtube.com, search for python tutorials, open new tab, close tab
- Spotify control: play spotify, pause spotify, skip song, volume up
- WhatsApp control: send whatsapp to mom hello, read whatsapp messages
- Instinct control: what have you learned, remember this pattern, forget that instinct

## Security and Safety Flow

Before task execution in layer mode:

1. Threat detector scans command text for high-risk patterns
2. Voice command is checked for injection-like content
3. Safety rules apply block/confirm/allow policy
4. Optional voice authentication can be enforced via settings

Main components:

- security/threat_detector.py
- security/voice_authenticator.py
- utils/safety_guard.py

## First Run Downloads (One Time Only)

The following are downloaded automatically on first run:

- Ollama models (llava + llama3) ~8GB total
  - Equivalent manual setup: ollama pull llava and ollama pull llama3
- Sentence Transformers model (all-MiniLM-L6-v2) ~90MB
  - Pulled from Hugging Face once; after this, semantic features run offline

## Quick Setup

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

Then run from the project folder:

```bash
cd advanced-clevrr
python main.py --mode layer --voice
```

Note (Windows): use UTF-8 terminal output when possible to avoid Unicode banner rendering issues in legacy console encodings.

## Validation

Current test status:

```bash
.venv\Scripts\python.exe -m pytest -v
```

Expected result: all tests passing.

## Notes

- If you run python main.py from the parent folder, Windows will show file not found for main.py.
- Use the project directory as the working directory before launching.
