#!/usr/bin/env python3
"""
Advanced Clevrr Computer — 100% Local AI Agent
===============================================

Control your computer with natural language using AI that runs
ENTIRELY on your machine. Zero external APIs. Zero cloud dependencies.
Zero API keys needed.

Tech: Ollama (llava + llama3) · pyautogui · Whisper · pyttsx3 · SQLite

Usage:
    python main.py              # Launch with Gradio dashboard
    python main.py --voice      # Enable voice control
    python main.py --mode layer --voice   # Run AILayer voice mode
    python main.py --task "Open Notepad"   # Run a single task
    python main.py --setup      # First-time setup wizard
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml


# ── Banner ────────────────────────────────────────────────────────────

BANNER = r"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║    █████╗ ██████╗ ██╗   ██╗ █████╗ ███╗   ██╗ ██████╗███████║
║   ██╔══██╗██╔══██╗██║   ██║██╔══██╗████╗  ██║██╔════╝██╔════║
║   ███████║██║  ██║██║   ██║███████║██╔██╗ ██║██║     █████╗ ║
║   ██╔══██║██║  ██║╚██╗ ██╔╝██╔══██║██║╚██╗██║██║     ██╔══╝ ║
║   ██║  ██║██████╔╝ ╚████╔╝ ██║  ██║██║ ╚████║╚██████╗███████║
║   ╚═╝  ╚═╝╚═════╝   ╚═══╝  ╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝╚══════║
║                                                              ║
║           CLEVRR COMPUTER — 100% Local AI Agent              ║
║       Zero APIs · Zero Cloud · Full Computer Control         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""


# ── Logging Setup ─────────────────────────────────────────────────────

def setup_logging() -> None:
    """Configure logging for the application."""
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s │ %(levelname)-8s │ %(name)-25s │ %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                log_dir / "clevrr.log", encoding="utf-8"
            ),
        ],
    )
    # Quiet noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("gradio").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)


# ── Configuration ─────────────────────────────────────────────────────

def load_config(config_path: str = "config/settings.yaml") -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Path to the settings YAML file.

    Returns:
        Configuration dictionary.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        return config
    except FileNotFoundError:
        print(f"⚠  Config file not found: {config_path}")
        print("   Using default configuration.")
        return {
            "ollama": {
                "url": "http://localhost:11434",
                "vision_model": "llava",
                "text_model": "llama3",
                "timeout": 60,
                "max_retries": 3,
            },
            "voice": {"enabled": False},
            "screen": {
                "screenshot_dir": "data/screenshots",
                "max_screenshots": 50,
                "grid_size": 10,
            },
            "memory": {"db_path": "data/memory.db"},
            "agent": {
                "max_retries": 3,
                "step_timeout": 30,
                "heal_attempts": 3,
                "confidence_threshold": 0.7,
            },
            "ui": {"port": 7860, "theme": "dark", "refresh_interval": 1},
        }


# ── Setup Wizard ──────────────────────────────────────────────────────

def run_setup_wizard() -> None:
    """Run the first-time setup wizard."""
    print("\n" + "=" * 60)
    print("  🔧 FIRST-TIME SETUP WIZARD")
    print("=" * 60)
    print()

    # Check Python version
    py_version = sys.version_info
    print(f"  Python version: {py_version.major}.{py_version.minor}.{py_version.micro}")
    if py_version < (3, 10):
        print("  ⚠  Python 3.10+ recommended. Some features may not work.")
    else:
        print("  ✅ Python version OK.")

    # Check Ollama
    print("\n  Checking Ollama...")
    try:
        import requests

        resp = requests.get("http://localhost:11434", timeout=5)
        if resp.status_code == 200:
            print("  ✅ Ollama is running.")
        else:
            print("  ❌ Ollama responded but with unexpected status.")
    except Exception:
        print(
            "  ❌ Ollama is NOT running.\n"
            "     Please install and start Ollama:\n"
            "       1. Download from https://ollama.ai\n"
            "       2. Run: ollama serve\n"
        )

    # Check models
    print("\n  Checking required models...")
    try:
        from utils.ollama_client import OllamaClient

        config = load_config()
        # Don't raise on missing connection for setup check
        try:
            client = OllamaClient(config)

            for model in ["llava", "llama3"]:
                if client.check_model_available(model):
                    print(f"  ✅ Model '{model}' available.")
                else:
                    print(f"  ⬇  Model '{model}' not found. Pulling...")
                    client.pull_model_if_missing(model)
        except ConnectionError:
            print(
                "  ❌ Cannot check models — Ollama not running.\n"
                "     Start Ollama first, then run setup again."
            )
    except ImportError as exc:
        print(f"  ⚠  Cannot check models: {exc}")

    # Check key dependencies
    print("\n  Checking dependencies...")
    deps = {
        "pyautogui": "pyautogui",
        "mss": "mss",
        "cv2": "opencv-python",
        "gradio": "gradio",
        "yaml": "pyyaml",
        "PIL": "Pillow",
        "numpy": "numpy",
        "sentence_transformers": "sentence-transformers",
    }

    for module, package in deps.items():
        try:
            __import__(module)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} — install with: pip install {package}")

    # Optional dependencies
    print("\n  Checking optional dependencies...")
    optional = {
        "whisper": "openai-whisper (voice input)",
        "pyttsx3": "pyttsx3 (voice output)",
        "sounddevice": "sounddevice (microphone)",
    }

    for module, desc in optional.items():
        try:
            __import__(module)
            print(f"  ✅ {desc}")
        except ImportError:
            print(f"  ⏭  {desc} — not installed (optional)")

    # Create directories
    print("\n  Creating directories...")
    for d in ["data", "data/screenshots", "data/logs"]:
        Path(d).mkdir(parents=True, exist_ok=True)
        print(f"  📁 {d}/")

    print()
    print("=" * 60)
    print("  ✅ Setup complete! Run: python main.py")
    print("=" * 60)
    print()


# ── Ollama Check ──────────────────────────────────────────────────────

def check_ollama(config: dict) -> bool:
    """Check that Ollama is running and required models are available.

    Args:
        config: Configuration dictionary.

    Returns:
        True if Ollama is ready, False otherwise.
    """
    import requests

    ollama_url = config.get("ollama", {}).get("url", "http://localhost:11434")

    try:
        resp = requests.get(ollama_url, timeout=5)
        if resp.status_code != 200:
            return False
    except Exception:
        print(
            "\n╔══════════════════════════════════════════════════════╗\n"
            "║          Ollama is NOT running!                      ║\n"
            "║                                                      ║\n"
            "║  Please start Ollama first:                          ║\n"
            "║    1. Install from https://ollama.ai                 ║\n"
            "║    2. Run: ollama serve                              ║\n"
            "║    3. Run: ollama pull llava                         ║\n"
            "║    4. Run: ollama pull llama3                        ║\n"
            "║                                                      ║\n"
            "║  Then restart this program.                          ║\n"
            "╚══════════════════════════════════════════════════════╝\n"
        )
        return False

    return True


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    """Main entry point for Advanced Clevrr Computer."""
    parser = argparse.ArgumentParser(
        description="Advanced Clevrr Computer — 100% Local AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py                        Launch with dashboard\n"
            "  python main.py --voice                 Enable voice mode\n"
            "  python main.py --mode layer --voice    Enable AILayer voice mode\n"
            "  python main.py --task 'Open Notepad'   Run a single task\n"
            "  python main.py --setup                  First-time setup\n"
        ),
    )

    parser.add_argument(
        "--mode",
        choices=["orchestrator", "layer"],
        default="orchestrator",
        help="Runtime mode: orchestrator (default) or layer",
    )

    parser.add_argument(
        "--ui",
        choices=["gradio", "floating", "overlay", "none"],
        default="gradio",
        help="UI mode: gradio (web dashboard), floating (overlay), overlay (Electron transparent UI), none",
    )
    parser.add_argument(
        "--voice",
        action="store_true",
        help="Enable voice control mode",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the vision model name (default: from config)",
    )
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Run a single task and exit",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run the first-time setup wizard",
    )

    args = parser.parse_args()

    # ── Set UTF-8 encoding for Windows console ──
    import sys
    if sys.stdout.encoding != 'utf-8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    # ── Print banner ──
    print(BANNER)

    # ── Setup wizard ──
    if args.setup:
        run_setup_wizard()
        return

    # ── Initialize logging ──
    setup_logging()
    logger = logging.getLogger("main")

    # ── Load config ──
    config = load_config()

    # ── Override model if specified ──
    if args.model:
        config.setdefault("ollama", {})["vision_model"] = args.model

    # ── Enable voice in config if flag set ──
    if args.voice:
        config.setdefault("voice", {})["enabled"] = True

    # ── Check Ollama ──
    logger.info("Checking Ollama connection...")
    if not check_ollama(config):
        sys.exit(1)

    # ── Pull models if missing ──
    try:
        from utils.ollama_client import OllamaClient

        logger.info("Checking required models...")
        client = OllamaClient(config)
        vision_model = config.get("ollama", {}).get("vision_model", "llava")
        text_model = config.get("ollama", {}).get("text_model", "llama3")
        client.pull_model_if_missing(vision_model)
        client.pull_model_if_missing(text_model)
    except ConnectionError as exc:
        logger.error("Ollama connection failed: %s", exc)
        sys.exit(1)

    # ── Initialize Memory (creates DB if new) ──
    logger.info("Initializing memory system...")
    from utils.memory_system import MemorySystem

    memory = MemorySystem(config)
    stats = memory.get_stats()
    logger.info(
        "Memory: %d episodes, %d knowledge, %d procedures",
        stats["total_episodes"],
        stats["total_knowledge"],
        stats["total_procedures"],
    )

    orchestrator = None
    ai_layer = None
    voice_controller = None
    router_service = None

    if args.mode == "layer":
        logger.info("Initializing AI Layer...")
        from core.ai_layer import AILayer

        ai_layer = AILayer(config)
        if config.get("voice", {}).get("enabled", False):
            ai_layer.start_voice()
            logger.info(
                "AI Layer voice control active. Wake word: '%s'",
                config["voice"].get("wake_word", "hey clevrr"),
            )
    else:
        logger.info("Initializing orchestrator...")
        from agents.orchestrator import Orchestrator

        orchestrator = Orchestrator(config)

        if config.get("voice", {}).get("enabled", False):
            logger.info("Initializing voice controller...")
            from utils.voice_controller import VoiceController

            voice_controller = VoiceController(config)
            voice_controller.start_background_listening(
                callback=lambda cmd: router_service.handle_task(cmd) if router_service else orchestrator.run_task(cmd)
            )
            logger.info(
                "Voice control active. Wake word: '%s'",
                config["voice"].get("wake_word", "hey computer"),
            )
    
    # ── Initialize Router Service (intelligent routing layer) ──
    logger.info("Initializing Router Service...")
    from core.router_service import RouterService
    
    router_service = RouterService(
        config,
        orchestrator=orchestrator,
        ai_layer=ai_layer,
    )
    logger.info("Router Service ready. Fast routing enabled.")

    # ── Single task mode ──
    if args.task:
        logger.info("Running single task: %s", args.task)
        result = router_service.handle_task(args.task)

        print("\n" + "=" * 60)
        status = "✅ SUCCESS" if result["success"] else "❌ FAILED"
        print(f"  {status}")
        print(f"  Action: {result.get('action', 'unknown')}")
        print(f"  Task: {args.task}")
        if "duration_seconds" in result:
            print(f"  Duration: {result['duration_seconds']:.1f}s")
        print(f"  Response: {result.get('response', 'N/A')}")
        print("=" * 60 + "\n")

        # Cleanup
        if voice_controller:
            voice_controller.stop()
        return

    # ── Launch UI ──
    if args.ui == "gradio":
        logger.info("Launching Gradio dashboard...")
        from ui.dashboard import launch_dashboard

        launch_dashboard(orchestrator or ai_layer.orchestrator, voice_controller, config)

    elif args.ui == "overlay":
        logger.info("Launching Electron overlay with WebSocket server...")
        from ui.overlay.server import get_overlay_server
        import subprocess
        import time
        
        # Initialize overlay server
        overlay_server = get_overlay_server(host="localhost", port=9999)
        overlay_server.set_router_service(router_service)
        overlay_server.start_background()
        
        # Give server time to start
        time.sleep(1)
        
        # Launch Electron app
        try:
            overlay_path = Path("ui/overlay")
            if (overlay_path / "node_modules").exists():
                logger.info("Launching Electron...")
                subprocess.Popen(
                    ["npm", "start"],
                    cwd=str(overlay_path),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                logger.error(
                    "Electron dependencies not installed.\n"
                    "  Run: cd ui/overlay && npm install"
                )
                return
        except Exception as e:
            logger.error(f"Failed to launch Electron: {e}")
            return
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            overlay_server.is_running = False

    elif args.ui == "floating":
        logger.info("Launching floating UI...")
        from ui.floating_ui import FloatingUI

        floating = FloatingUI(
            on_task=lambda task: router_service.handle_task(task),
            on_cancel=lambda: (orchestrator.cancel_task() if orchestrator else "No orchestrator cancel in layer mode"),
        )
        floating.launch()

        # Keep main thread alive
        try:
            while True:
                import time

                time.sleep(1)
        except KeyboardInterrupt:
            floating.close()

    elif args.ui == "none":
        logger.info("No UI mode. Use --task to run tasks.")
        print(
            "\n  No UI selected. Use --task 'your task' to run tasks.\n"
            "  Or change --ui to 'gradio', 'floating', or 'overlay'.\n"
        )

    # Cleanup
    if voice_controller:
        voice_controller.stop()
    if ai_layer:
        ai_layer.stop_voice()


if __name__ == "__main__":
    main()
