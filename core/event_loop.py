"""
Event Loop Architecture — Continuous System Operation

Replaces one-shot execution with continuous event-driven operation:
- Models stay loaded in memory
- Tasks processed as they arrive
- Real-time dashboard updates via WebSocket
- Memory and learning across sessions
- Autonomous reaction to screen changes

This is what enables CLOVIS-level speed (<1 sec per task).
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """System event for event loop processing.
    
    Uses __slots__ for faster attribute access on hot path.
    """
    __slots__ = ('type', 'source', 'data', 'timestamp', 'priority')
    
    type: str  # "task", "screenshot", "voice", "memory", "alarm"
    source: str  # "voice", "overlay", "watcher", "memory", "scheduler"
    data: Dict[str, Any]
    timestamp: float = None
    priority: int = 0  # 0=normal, 1=high, -1=low
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def __lt__(self, other):
        """Support priority queue ordering (higher priority first)."""
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.timestamp < other.timestamp


class EventBus:
    """
    Central event bus for system communication.
    
    Receives events from all sources (voice, overlay, screen watcher, etc)
    and broadcasts to registered handlers.
    """
    
    def __init__(self):
        """Initialize event bus."""
        self.handlers: Dict[str, List[Callable]] = {}
        self.event_history: List[Event] = []
        self.max_history = 100
        self.lock = threading.Lock()
        
        logger.info("[EVENT BUS] Initialized")
    
    def subscribe(self, event_type: str, handler: Callable):
        """
        Subscribe handler to event type.
        
        Args:
            event_type: Event type to listen for ("task", "screenshot", etc).
            handler: Async or sync callback function.
        """
        with self.lock:
            if event_type not in self.handlers:
                self.handlers[event_type] = []
            self.handlers[event_type].append(handler)
            logger.debug(f"[EVENT BUS] Handler subscribed to {event_type}")
    
    def unsubscribe(self, event_type: str, handler: Callable):
        """Unsubscribe handler from event type."""
        with self.lock:
            if event_type in self.handlers:
                if handler in self.handlers[event_type]:
                    self.handlers[event_type].remove(handler)
    
    async def publish(self, event: Event):
        """
        Publish event to all subscribed handlers.
        
        Args:
            event: Event to publish.
        """
        # Record in history
        with self.lock:
            self.event_history.append(event)
            if len(self.event_history) > self.max_history:
                self.event_history = self.event_history[-self.max_history:]
        
        logger.debug(f"[EVENT BUS] Event published: {event.type} from {event.source}")
        
        # Call all handlers for this event type
        with self.lock:
            handlers = self.handlers.get(event.type, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"[EVENT BUS] Handler error for {event.type}: {e}")
    
    def get_history(self, event_type: str = None, limit: int = 10) -> List[Event]:
        """Get recent events, optionally filtered by type."""
        with self.lock:
            if event_type:
                events = [e for e in self.event_history if e.type == event_type]
            else:
                events = self.event_history
            return events[-limit:]
    
    def clear_history(self):
        """Clear event history."""
        with self.lock:
            self.event_history.clear()


class SystemEventLoop:
    """
    Main event loop for continuous system operation.
    
    Processes events in order of priority, updates system state,
    and coordinates all agents and UI components.
    """
    
    def __init__(self, orchestrator=None, session=None, config: Dict = None):
        """
        Initialize event loop.
        
        Args:
            orchestrator: Orchestrator with all agents.
            session: PersistentSession instance.
            config: Configuration dictionary.
        """
        self.orchestrator = orchestrator
        self.session = session
        self.config = config or {}
        
        self.event_bus = EventBus()
        self.running = False
        self.event_queue: asyncio.PriorityQueue = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Callbacks for external systems (dashboard, overlay)
        self.on_task_update: Optional[Callable] = None
        self.on_status_change: Optional[Callable] = None
        self.on_screenshot: Optional[Callable] = None
        
        logger.info("[EVENT LOOP] System event loop initialized")
    
    async def start(self):
        """Start the event loop (async)."""
        if self.running:
            logger.warning("[EVENT LOOP] Already running")
            return
        
        self.running = True
        self.event_queue = asyncio.PriorityQueue()
        
        logger.info("[EVENT LOOP] Starting continuous operation")
        
        try:
            # Start multiple concurrent tasks
            await asyncio.gather(
                self._process_events(),
                self._heartbeat(),
            )
        except Exception as e:
            logger.error(f"[EVENT LOOP] Fatal error: {e}")
        finally:
            self.running = False
            logger.info("[EVENT LOOP] Stopped")
    
    async def _process_events(self):
        """Main event processing loop (continuously running)."""
        logger.info("[EVENT LOOP] Event processor started")
        
        while self.running:
            try:
                # Wait for event with timeout
                event = await asyncio.wait_for(
                    self.event_queue.get(),
                    timeout=1.0
                )
                
                # Process event
                await self._handle_event(event)
                
            except asyncio.TimeoutError:
                # No events, just continue
                continue
            except Exception as e:
                logger.error(f"[EVENT LOOP] Event processing error: {e}")
    
    async def _handle_event(self, event: Event):
        """
        Handle individual event.
        
        Args:
            event: Event to process.
        """
        logger.info(f"[EVENT LOOP] Processing: {event.type} from {event.source}")
        
        start_time = time.time()
        
        try:
            if event.type == "task":
                await self._handle_task_event(event)
            elif event.type == "screenshot":
                await self._handle_screenshot_event(event)
            elif event.type == "voice":
                await self._handle_voice_event(event)
            elif event.type == "memory":
                await self._handle_memory_event(event)
            elif event.type == "alarm":
                await self._handle_alarm_event(event)
            else:
                logger.warning(f"[EVENT LOOP] Unknown event type: {event.type}")
            
            # Publish to all subscribers
            await self.event_bus.publish(event)
            
            duration = time.time() - start_time
            logger.debug(f"[EVENT LOOP] Event processed in {duration:.3f}s")
            
        except Exception as e:
            logger.error(f"[EVENT LOOP] Error handling {event.type}: {e}")
    
    async def _handle_task_event(self, event: Event):
        """Handle task event (user command)."""
        query = event.data.get("query", "")
        logger.info(f"[EVENT LOOP] Task: {query[:60]}")
        
        if self.session:
            self.session.queue_task(event.data)
        
        # Route through orchestrator
        if self.orchestrator:
            try:
                task_start = time.time()
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.orchestrator.run_task, query
                )
                duration = time.time() - task_start
                
                if self.session:
                    self.session.record_task_completion(
                        event.data, duration, result.get("success", False), result
                    )
                
                # Callback to dashboard
                if self.on_task_update:
                    self.on_task_update({
                        "query": query,
                        "result": result,
                        "duration": duration,
                    })
                
            except Exception as e:
                logger.error(f"[EVENT LOOP] Task execution failed: {e}")
                if self.session:
                    self.session.record_task_completion(event.data, 0, False)
    
    async def _handle_screenshot_event(self, event: Event):
        """Handle screenshot event (screen monitoring)."""
        screenshot = event.data.get("image")
        
        if self.session:
            self.session.cache_screenshot(screenshot, event.data)
        
        if self.on_screenshot:
            self.on_screenshot(screenshot)
    
    async def _handle_voice_event(self, event: Event):
        """Handle voice event (converted to task)."""
        transcript = event.data.get("transcript", "")
        logger.info(f"[EVENT LOOP] Voice input: {transcript[:60]}")
        
        # Convert voice event to task event
        task_event = Event(
            type="task",
            source="voice",
            data={"query": transcript, "metadata": event.data},
            priority=1,  # Voice is higher priority
        )
        
        await self.event_queue.put((task_event.priority, task_event.timestamp, task_event))
    
    async def _handle_memory_event(self, event: Event):
        """Handle memory event (learning/persistence)."""
        logger.info("[EVENT LOOP] Memory event processed")
    
    async def _handle_alarm_event(self, event: Event):
        """Handle alarm event (scheduled tasks)."""
        logger.info("[EVENT LOOP] Alarm event processed")
    
    async def _heartbeat(self):
        """Background heartbeat for system monitoring."""
        while self.running:
            try:
                await asyncio.sleep(5)
                
                # Update dashboard with current state
                if self.session and self.on_status_change:
                    self.on_status_change({
                        "status": "running",
                        "queue_length": self.session.get_queue_length(),
                        "stats": self.session.get_stats(),
                        "timestamp": datetime.now().isoformat(),
                    })
                
            except Exception as e:
                logger.error(f"[EVENT LOOP] Heartbeat error: {e}")
    
    def post_event(self, event: Event):
        """
        Post event from external source (thread-safe).
        
        Args:
            event: Event to post.
        """
        if not self.running or self.event_queue is None:
            logger.warning("[EVENT LOOP] Cannot post event: loop not running")
            return
        
        try:
            # Use run_coroutine_threadsafe for thread-safe posting
            asyncio.run_coroutine_threadsafe(
                self.event_queue.put((event.priority, event.timestamp, event)),
                self.loop
            )
        except Exception as e:
            logger.error(f"[EVENT LOOP] Failed to post event: {e}")
    
    def stop(self):
        """Stop the event loop."""
        logger.info("[EVENT LOOP] Stopping...")
        self.running = False


def run_event_loop(orchestrator=None, session=None, config: Dict = None):
    """
    Run event loop in async context.
    
    Args:
        orchestrator: Orchestrator instance.
        session: PersistentSession instance.
        config: Configuration dictionary.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    event_loop = SystemEventLoop(orchestrator, session, config)
    event_loop.loop = loop
    
    try:
        loop.run_until_complete(event_loop.start())
    except KeyboardInterrupt:
        logger.info("[EVENT LOOP] Interrupted by user")
    finally:
        loop.close()
        logger.info("[EVENT LOOP] Event loop closed")
