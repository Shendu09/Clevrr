#!/usr/bin/env python3
"""
Clevrr Event Loop Mode — Continuous AI Agent Operation
========================================================

This is the new CLOVIS-level architecture featuring:
- Persistent session with models always loaded
- Continuous event loop processing
- Real-time dashboard monitoring
- Instant task execution (<1 sec)

Usage:
    python run_event_loop.py              # Start with dashboard
    python run_event_loop.py --verbose    # Debug logging
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

import yaml

# ── Imports ──

from agents.orchestrator import Orchestrator
from core.event_loop import SystemEventLoop, Event
from core.session_manager import get_session
from core.system_server import get_system_server
from core.router_service import RouterService
from ui.enhanced_dashboard import launch_dashboard
from utils.memory_system import MemorySystem

# ── Setup ──

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
║       CLEVRR EVENT LOOP — CLOVIS-Level Architecture          ║
║           Continuous AI Agent with Local Models              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""

def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s │ %(levelname)-8s │ %(name)-25s │ %(message)s",
        datefmt="%H:%M:%S",
    )
    
    # Quiet noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("gradio").setLevel(logging.WARNING)


def load_config(config_path: str = "config/settings.yaml") -> dict:
    """Load configuration from YAML file."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"⚠  Config not found: {config_path}")
        return {
            "ollama": {
                "url": "http://localhost:11434",
                "vision_model": "llava",
                "text_model": "llama3",
            }
        }


def main():
    """Main entry point with event loop architecture."""
    
    parser = argparse.ArgumentParser(
        description="Clevrr Event Loop — Continuous AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=7861,
        help="Port for enhanced dashboard",
    )
    
    args = parser.parse_args()
    
    # Print banner
    print(BANNER)
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger("main")
    
    # Load config
    logger.info("Loading configuration...")
    config = load_config()
    
    # Initialize memory
    logger.info("Initializing memory system...")
    memory = MemorySystem(config)
    
    # Initialize orchestrator (loads all agents + models)
    logger.info("Initializing orchestrator (this keeps models loaded)...")
    orchestrator = Orchestrator(config)
    logger.info("✅ Orchestrator ready - models will stay in memory")
    
    # Initialize persistent session
    logger.info("Creating persistent session...")
    session = get_session(orchestrator, config)
    session.mark_agents_ready()
    session.mark_models_loaded()
    
    # Initialize router service
    logger.info("Initializing router service...")
    router_service = RouterService(config, orchestrator=orchestrator)
    
    # Create event loop
    logger.info("Creating system event loop...")
    event_loop = SystemEventLoop(orchestrator, session, config)
    
    # Create system server
    logger.info("Initializing system server...")
    system_server = get_system_server(
        orchestrator=orchestrator,
        router_service=router_service,
        event_loop_instance=event_loop,
        config=config,
    )
    
    # Start system
    logger.info("Starting system...")
    system_server.start()
    
    logger.info("✅ EVENT LOOP RUNNING")
    logger.info(f"📊 Dashboard: http://localhost:{args.dashboard_port}")
    logger.info("⏸️  Press Ctrl+C to stop")
    
    # Launch dashboard in background thread
    import threading
    
    def run_dashboard():
        try:
            launch_dashboard(
                orchestrator=orchestrator,
                router_service=router_service,
                session=session,
                event_loop=event_loop,
                port=args.dashboard_port,
            )
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
    
    dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
    dashboard_thread.start()
    
    # Keep system running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("  Shutting down...")
        print("=" * 60)
        system_server.shutdown()
        logger.info("Goodbye!")


if __name__ == "__main__":
    main()
