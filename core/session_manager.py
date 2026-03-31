"""
Persistent Session Manager — Keep Models Loaded & Ready

Maintains continuous system state:
- Agents stay loaded (instant execution)
- Screenshot cache for diff detection
- Memory persistence across tasks
- Event tracking for replay
- Resource pooling and reuse
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionStats:
    """Session metrics and performance tracking."""
    start_time: datetime = field(default_factory=datetime.now)
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    total_duration_seconds: float = 0.0
    avg_task_duration: float = 0.0
    last_task_time: Optional[datetime] = None
    models_loaded: bool = False
    agents_ready: bool = False
    uptime_seconds: float = 0.0
    
    def update_uptime(self):
        """Update uptime counter."""
        self.uptime_seconds = (datetime.now() - self.start_time).total_seconds()
    
    def record_task(self, duration: float, success: bool):
        """Record task completion."""
        self.total_tasks += 1
        if success:
            self.successful_tasks += 1
        else:
            self.failed_tasks += 1
        
        self.total_duration_seconds += duration
        self.avg_task_duration = self.total_duration_seconds / self.total_tasks
        self.last_task_time = datetime.now()
    
    def success_rate(self) -> float:
        """Get task success rate percentage."""
        if self.total_tasks == 0:
            return 0.0
        return (self.successful_tasks / self.total_tasks) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        self.update_uptime()
        return {
            "start_time": self.start_time.isoformat(),
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "total_duration_seconds": self.total_duration_seconds,
            "avg_task_duration": round(self.avg_task_duration, 2),
            "success_rate": round(self.success_rate(), 1),
            "uptime_seconds": round(self.uptime_seconds, 1),
            "models_loaded": self.models_loaded,
            "agents_ready": self.agents_ready,
            "last_task_time": self.last_task_time.isoformat() if self.last_task_time else None,
        }


class ScreenshotCache:
    """Cache recent screenshots for diff detection."""
    
    def __init__(self, max_cache_size: int = 5):
        """
        Initialize screenshot cache.
        
        Args:
            max_cache_size: Maximum number of screenshots to keep.
        """
        self.max_cache_size = max_cache_size
        self.cache: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
    
    def add(self, screenshot: Any, metadata: Dict[str, Any]):
        """
        Add screenshot to cache.
        
        Args:
            screenshot: Screenshot image object.
            metadata: Screenshot metadata (timestamp, resolution, etc).
        """
        with self.lock:
            self.cache.append({
                "image": screenshot,
                "metadata": metadata,
                "timestamp": time.time(),
            })
            
            # Keep only recent screenshots
            if len(self.cache) > self.max_cache_size:
                self.cache = self.cache[-self.max_cache_size:]
            
            logger.debug(f"Screenshot cached. Total cached: {len(self.cache)}")
    
    def get_latest(self) -> Optional[Dict[str, Any]]:
        """Get most recent screenshot."""
        with self.lock:
            if self.cache:
                return self.cache[-1]
            return None
    
    def get_previous(self) -> Optional[Dict[str, Any]]:
        """Get second-most recent screenshot (for diff detection)."""
        with self.lock:
            if len(self.cache) >= 2:
                return self.cache[-2]
            return None
    
    def clear(self):
        """Clear cache."""
        with self.lock:
            self.cache.clear()
    
    def size(self) -> int:
        """Get current cache size."""
        with self.lock:
            return len(self.cache)


class PersistentSession:
    """
    Manage continuous system session.
    
    Keeps models loaded, tracks state, caches resources for fast execution.
    """
    
    def __init__(self, orchestrator=None, config: Optional[Dict] = None):
        """
        Initialize persistent session.
        
        Args:
            orchestrator: Orchestrator instance with all agents.
            config: Configuration dictionary.
        """
        self.orchestrator = orchestrator
        self.config = config or {}
        self.stats = SessionStats()
        self.screenshot_cache = ScreenshotCache(max_cache_size=5)
        self.task_queue: List[Dict[str, Any]] = []
        self.running = False
        self.lock = threading.Lock()
        
        # Agent caching
        self.agents_loaded = False
        self.models_loaded = False
        
        logger.info("[SESSION] Persistent session initialized")
    
    def mark_models_loaded(self):
        """Mark that models are loaded and ready."""
        self.models_loaded = True
        self.stats.models_loaded = True
        logger.info("[SESSION] Models marked as loaded and persistent")
    
    def mark_agents_ready(self):
        """Mark that agents are initialized and ready."""
        self.agents_loaded = True
        self.stats.agents_ready = True
        logger.info("[SESSION] All agents marked as ready")
    
    def queue_task(self, task_dict: Dict[str, Any]):
        """
        Queue a task for execution.
        
        Args:
            task_dict: Task with 'query', 'source', optional 'metadata'.
        """
        with self.lock:
            self.task_queue.append({
                "query": task_dict.get("query", ""),
                "source": task_dict.get("source", "unknown"),  # "voice", "overlay", "api", etc
                "metadata": task_dict.get("metadata", {}),
                "queued_at": time.time(),
                "status": "queued",
            })
            logger.info(f"[SESSION] Task queued: {task_dict.get('query', '')[:60]}")
    
    def get_next_task(self) -> Optional[Dict[str, Any]]:
        """Get next task from queue (FIFO)."""
        with self.lock:
            if self.task_queue:
                task = self.task_queue.pop(0)
                task["status"] = "processing"
                return task
            return None
    
    def record_task_completion(self, task_dict: Dict[str, Any], duration: float, success: bool, result: Any = None):
        """
        Record task completion.
        
        Args:
            task_dict: Original task dict.
            duration: Task execution time in seconds.
            success: Whether task succeeded.
            result: Task result data.
        """
        self.stats.record_task(duration, success)
        
        status = "success" if success else "failed"
        logger.info(f"[SESSION] Task completed ({status}): {duration:.2f}s")
    
    def cache_screenshot(self, screenshot: Any, metadata: Dict[str, Any] = None):
        """
        Cache current screenshot for fast diff detection.
        
        Args:
            screenshot: Screenshot image object.
            metadata: Screenshot metadata.
        """
        self.screenshot_cache.add(screenshot, metadata or {})
    
    def has_screen_changed(self, image_comparator=None) -> bool:
        """
        Check if screen has changed since last screenshot.
        
        Args:
            image_comparator: ImageComparator instance for diff detection.
        
        Returns:
            True if screen changed, False if same or no previous screenshot.
        """
        if image_comparator is None:
            return True  # Assume changed if no comparator
        
        current = self.screenshot_cache.get_latest()
        previous = self.screenshot_cache.get_previous()
        
        if current is None or previous is None:
            return True
        
        try:
            result = image_comparator.compare(
                previous["image"],
                current["image"]
            )
            return result.is_different
        except Exception as e:
            logger.warning(f"[SESSION] Screenshot comparison failed: {e}")
            return True
    
    def get_queue_length(self) -> int:
        """Get number of pending tasks in queue."""
        with self.lock:
            return len(self.task_queue)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        return self.stats.to_dict()
    
    def reset_stats(self):
        """Reset statistics (keep models loaded)."""
        old_stats = self.stats.to_dict()
        self.stats = SessionStats()
        self.stats.models_loaded = True
        self.stats.agents_ready = True
        logger.info("[SESSION] Statistics reset (models/agents remain loaded)")
        return old_stats
    
    def shutdown(self):
        """Gracefully shutdown session."""
        logger.info("[SESSION] Shutting down persistent session")
        self.running = False
        self.screenshot_cache.clear()
        
        # Save final stats
        final_stats = self.get_stats()
        logger.info(f"[SESSION] Final stats: {final_stats}")


# Global session instance
_global_session: Optional[PersistentSession] = None
_session_lock = threading.Lock()


def get_session(orchestrator=None, config: Optional[Dict] = None) -> PersistentSession:
    """
    Get or create global persistent session.
    
    Args:
        orchestrator: Orchestrator instance (used on first call).
        config: Configuration (used on first call).
    
    Returns:
        PersistentSession instance.
    """
    global _global_session
    
    if _global_session is None:
        with _session_lock:
            if _global_session is None:
                _global_session = PersistentSession(orchestrator, config)
    
    return _global_session


def reset_session():
    """Reset global session (testing/debugging only)."""
    global _global_session
    with _session_lock:
        if _global_session:
            _global_session.shutdown()
        _global_session = None
