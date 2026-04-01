# Adapted from OpenClaw (https://github.com/openclaw/openclaw)
# Production-ready event loop with priority queue

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Dict
from enum import Enum
from datetime import datetime
import logging
import heapq

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Priority levels matching OpenClaw's event ordering"""
    CRITICAL = 0       # System shutdown, fatal errors
    VOICE = 1          # Voice input commands
    INTENT = 2         # Intent classification
    TASK = 3           # User task requests
    SCREENSHOT = 4     # Screen state updates
    GESTURE = 5        # Gesture/interaction
    BACKGROUND = 10    # Cron, maintenance, low-priority tasks


@dataclass
class Event:
    """Exact pattern from OpenClaw's Event type"""
    type: str
    priority: EventPriority
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp_ms: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    source: Optional[str] = None
    
    def __lt__(self, other: "Event") -> bool:
        """For heap ordering: by priority first, then by timestamp"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.timestamp_ms < other.timestamp_ms
    
    def __eq__(self, other):
        return (self.type == other.type and
                self.priority == other.priority and
                self.timestamp_ms == other.timestamp_ms)
    
    def __hash__(self):
        return hash((self.type, self.priority.value, self.timestamp_ms))


class EventLoopService:
    """
    Async event loop with priority queue
    Adapted from OpenClaw's event handling patterns
    From: src/gateway/server-chat.ts and related
    """
    
    def __init__(self, max_queue_size: int = 1000, name: str = "EventLoop"):
        self.name = name
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self.handlers: Dict[str, Callable[[Event], Any]] = {}
        self.is_running = False
        self.event_counter = 0  # For stable ordering
    
    def register_handler(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Register handler for event type"""
        if not asyncio.iscoroutinefunction(handler) and not callable(handler):
            raise TypeError(f"Handler must be callable: {event_type}")
        self.handlers[event_type] = handler
    
    async def post_event(self, event: Event) -> bool:
        """
        Post event to queue (non-blocking)
        Returns True if enqueued, False if queue full
        """
        try:
            # Use tuple for heap ordering: (priority, timestamp, counter, event)
            self.event_counter += 1
            priority_tuple = (
                event.priority.value,
                event.timestamp_ms,
                self.event_counter,
                event
            )
            self.queue.put_nowait(priority_tuple)
            return True
        except asyncio.QueueFull:
            logger.warning(f"[{self.name}] Queue full, dropping event: {event.type}")
            return False
    
    async def start(self) -> None:
        """Start event loop (blocking)"""
        self.is_running = True
        logger.info(f"[{self.name}] Started")
        
        try:
            while self.is_running:
                try:
                    # Get next event with 1-second timeout
                    _, _, _, event = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=1.0
                    )
                    await self._handle_event(event)
                except asyncio.TimeoutError:
                    # Queue empty, continue waiting
                    continue
                except asyncio.CancelledError:
                    logger.info(f"[{self.name}] Cancelled")
                    raise
        except Exception as e:
            logger.exception(f"[{self.name}] Unexpected error")
        finally:
            self.is_running = False
            logger.info(f"[{self.name}] Stopped")
    
    async def _handle_event(self, event: Event) -> None:
        """Route event to handler"""
        handler = self.handlers.get(event.type)
        
        if not handler:
            logger.warning(f"[{self.name}] No handler for event: {event.type}")
            return
        
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                # Run sync handler in thread pool
                await asyncio.to_thread(handler, event)
        except asyncio.CancelledError:
            logger.debug(f"[{self.name}] Handler cancelled: {event.type}")
            raise
        except Exception as e:
            logger.error(
                f"[{self.name}] Handler error ({event.type}, priority={event.priority.name}): {e}",
                exc_info=True
            )
    
    async def stop(self) -> None:
        """Gracefully stop event loop"""
        logger.info(f"[{self.name}] Stopping")
        self.is_running = False
        
        # Drain and process remaining events
        try:
            while not self.queue.empty():
                _, _, _, event = self.queue.get_nowait()
                try:
                    await self._handle_event(event)
                except Exception as e:
                    logger.warning(f"Error processing final event: {e}")
        except asyncio.QueueEmpty:
            pass
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        return self.queue.qsize()


# Example usage
async def example():
    loop = EventLoopService()
    
    # Register handlers
    async def handle_voice(event: Event):
        logger.info(f"Processing voice event: {event.data}")
    
    async def handle_task(event: Event):
        logger.info(f"Processing task event: {event.data}")
    
    def handle_screenshot(event: Event):
        logger.info(f"Processing screenshot event")
    
    loop.register_handler("voice_input", handle_voice)
    loop.register_handler("task_command", handle_task)
    loop.register_handler("screenshot", handle_screenshot)
    
    # Start loop in background
    loop_task = asyncio.create_task(loop.start())
    
    # Post some events
    await loop.post_event(Event(
        type="voice_input",
        priority=EventPriority.VOICE,
        data={"transcript": "hello"}
    ))
    
    await loop.post_event(Event(
        type="task_command",
        priority=EventPriority.TASK,
        data={"query": "open browser"}
    ))
    
    # Let it run briefly then stop
    await asyncio.sleep(0.5)
    await loop.stop()
    await loop_task
