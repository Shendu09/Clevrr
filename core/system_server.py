"""
Server for running event loop in background + coordinating services.

This server brings together:
- Event loop (continuous operation)
- Session manager (persistent state)
- Router service (task routing)
- Dashboard (monitoring)
- Overlay WebSocket (UI)
"""

import asyncio
import logging
import threading
import time
from typing import Optional

from core.event_loop import SystemEventLoop, Event
from core.session_manager import get_session, PersistentSession

logger = logging.getLogger(__name__)


class ClevrSystemServer:
    """
    Master server coordinating all system components.
    
    Runs:
    - Event loop (background async)
    - Session manager (persistent)
    - Dashboard (web UI)
    - Overlay WebSocket (transparent UI)
    - Router service (task distribution)
    """
    
    def __init__(
        self,
        orchestrator=None,
        router_service=None,
        event_loop_instance=None,
        config: dict = None,
    ):
        """
        Initialize system server.
        
        Args:
            orchestrator: Orchestrator with all agents.
            router_service: Router service for task routing.
            event_loop_instance: System event loop.
            config: Configuration dictionary.
        """
        self.orchestrator = orchestrator
        self.router_service = router_service
        self.event_loop_instance = event_loop_instance
        self.config = config or {}
        
        # Create persistent session if not provided
        self.session: Optional[PersistentSession] = None
        self._init_session()
        
        self.running = False
        self.threads = []
        
        logger.info("[SYSTEM SERVER] Initialized")
    
    def _init_session(self):
        """Initialize or reuse persistent session."""
        self.session = get_session(self.orchestrator, self.config)
        
        if self.orchestrator:
            self.session.mark_agents_ready()
        
        logger.info("[SYSTEM SERVER] Session ready")
    
    def start(self):
        """Start all system components."""
        logger.info("[SYSTEM SERVER] Starting system")
        self.running = True
        
        # Mark models as loaded
        if self.session:
            self.session.mark_models_loaded()
        
        # Start event loop in background thread
        if self.event_loop_instance:
            self._start_event_loop()
        
        logger.info("[SYSTEM SERVER] All components started ✅")
    
    def _start_event_loop(self):
        """Start event loop in background thread."""
        def run_loop():
            logger.info("[SYSTEM SERVER] Event loop thread starting")
            
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.event_loop_instance.loop = loop
            
            try:
                loop.run_until_complete(self.event_loop_instance.start())
            except Exception as e:
                logger.error(f"[SYSTEM SERVER] Event loop error: {e}")
            finally:
                loop.close()
                logger.info("[SYSTEM SERVER] Event loop thread stopped")
        
        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
        self.threads.append(thread)
        time.sleep(0.5)  # Give loop time to start
        logger.info("[SYSTEM SERVER] Event loop thread started")
    
    def submit_task_from_api(self, query: str, source: str = "api") -> dict:
        """
        Submit task from external API/trigger.
        
        Args:
            query: Task query string.
            source: Source identifier ("api", "webhook", etc).
        
        Returns:
            Result dictionary.
        """
        if not self.running:
            return {"success": False, "error": "System not running"}
        
        # Use session if available
        if self.session:
            self.session.queue_task({
                "query": query,
                "source": source,
            })
        
        # Route through router service
        if self.router_service:
            result = self.router_service.handle_task(query)
            return result
        
        return {"success": False, "error": "No router service"}
    
    def post_event(self, event_type: str, data: dict, source: str, priority: int = 0):
        """
        Post event to system event loop.
        
        Args:
            event_type: Type of event.
            data: Event data.
            source: Event source.
            priority: Event priority (0=normal, 1=high).
        """
        if not self.event_loop_instance:
            logger.warning("[SYSTEM SERVER] No event loop to post to")
            return
        
        event = Event(
            type=event_type,
            source=source,
            data=data,
            priority=priority,
        )
        
        self.event_loop_instance.post_event(event)
    
    def get_status(self) -> dict:
        """Get comprehensive system status."""
        return {
            "running": self.running,
            "session": self.session.get_stats() if self.session else None,
            "event_loop": self.event_loop_instance.running if self.event_loop_instance else False,
            "timestamp": time.time(),
        }
    
    def shutdown(self):
        """Gracefully shutdown all components."""
        logger.info("[SYSTEM SERVER] Shutting down")
        self.running = False
        
        if self.event_loop_instance:
            self.event_loop_instance.stop()
        
        if self.session:
            self.session.shutdown()
        
        # Wait for threads
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        logger.info("[SYSTEM SERVER] Shutdown complete")


# Global server instance
_global_server: Optional[ClevrSystemServer] = None


def get_system_server(
    orchestrator=None,
    router_service=None,
    event_loop_instance=None,
    config: dict = None,
) -> ClevrSystemServer:
    """Get or create global system server."""
    global _global_server
    
    if _global_server is None:
        _global_server = ClevrSystemServer(
            orchestrator=orchestrator,
            router_service=router_service,
            event_loop_instance=event_loop_instance,
            config=config,
        )
    
    return _global_server
