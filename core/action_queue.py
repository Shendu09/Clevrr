"""
Action Queue — Timed Execution of Visual Feedback

Inspired by CLOVIS's action queue system, this enables choreographed
visual feedback like:
  - t=0.0s: Draw box around element
  - t=0.5s: Add text label "Clicking button"
  - t=3.0s: Remove box and text

Used to make automation feel less like magic and more like
controlled, step-by-step instruction.
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class QueuedAction:
    """Represents a timed action to execute."""
    delay_seconds: float
    func: Callable
    args: tuple = ()
    kwargs: dict = None
    action_id: str = ""
    
    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}


class ActionQueue:
    """
    Queue for choreographed timed actions.
    
    Allows scheduling actions to execute at specific times, enabling
    visual feedback like annotating screen elements before/after actions.
    
    Example:
        queue = ActionQueue()
        queue.enqueue(0.0, draw_box, x=100, y=200, width=300, height=150)
        queue.enqueue(0.5, draw_text, x=150, y=250, text="Clicking")
        queue.enqueue(3.0, clear_box)
        await queue.execute_all()
    """
    
    def __init__(self):
        """Initialize the action queue."""
        self.actions: deque[QueuedAction] = deque()
        self.active_ids: Dict[str, QueuedAction] = {}
        self.is_executing = False
        self.execution_start_time: Optional[float] = None
        self.cancelled = False
        
        # Counters
        self.total_queued = 0
        self.total_executed = 0
        self.total_failed = 0

    def enqueue(
        self,
        delay_seconds: float,
        func: Callable,
        *args,
        action_id: str = "",
        **kwargs
    ) -> str:
        """
        Queue an action for delayed execution.

        Args:
            delay_seconds: How many seconds to wait before executing.
            func: The callable to execute.
            *args: Positional arguments for func.
            action_id: Optional ID for tracking/cancelling this action.
            **kwargs: Keyword arguments for func.

        Returns:
            The action ID (generated if not provided).
        """
        if not action_id:
            action_id = f"action_{int(time.time() * 1000000)}"
        
        action = QueuedAction(
            delay_seconds=delay_seconds,
            func=func,
            args=args,
            kwargs=kwargs,
            action_id=action_id,
        )
        
        self.actions.append(action)
        self.active_ids[action_id] = action
        self.total_queued += 1
        
        logger.debug(
            f"[ACTION QUEUE] Queued action '{action_id}' "
            f"at t={delay_seconds:.1f}s"
        )
        
        return action_id

    def cancel_action(self, action_id: str) -> bool:
        """
        Cancel a queued action by its ID.

        Args:
            action_id: ID of the action to cancel.

        Returns:
            True if action was found and cancelled, False otherwise.
        """
        if action_id not in self.active_ids:
            return False
        
        # Remove from queue by ID
        self.actions = deque(
            a for a in self.actions if a.action_id != action_id
        )
        del self.active_ids[action_id]
        
        logger.debug(f"[ACTION QUEUE] Cancelled action '{action_id}'")
        return True

    async def execute_all(self) -> Dict[str, Any]:
        """
        Execute all queued actions in order with proper timing.
        
        This is async to allow non-blocking delays. Each action is executed
        at its scheduled time.

        Returns:
            Dict with execution stats:
                - executed: number of actions executed
                - failed: number of actions that failed
                - duration_seconds: total time taken
        """
        if not self.actions:
            logger.debug("[ACTION QUEUE] No actions to execute")
            return {
                "executed": 0,
                "failed": 0,
                "duration_seconds": 0,
            }
        
        self.is_executing = True
        self.cancelled = False
        self.execution_start_time = time.time()
        self.total_executed = 0
        self.total_failed = 0
        
        start_time = time.time()
        
        try:
            while self.actions and not self.cancelled:
                action = self.actions.popleft()
                current_time = time.time() - start_time
                
                # Wait until it's time for this action
                wait_time = action.delay_seconds - current_time
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                
                # Execute the action
                try:
                    result = action.func(*action.args, **action.kwargs)
                    
                    # Handle async functions
                    if asyncio.iscoroutine(result):
                        await result
                    
                    self.total_executed += 1
                    logger.debug(
                        f"[ACTION QUEUE] Executed '{action.action_id}' "
                        f"at t={action.delay_seconds:.1f}s"
                    )
                    
                except Exception as e:
                    self.total_failed += 1
                    logger.error(
                        f"[ACTION QUEUE] Action '{action.action_id}' "
                        f"failed: {e}"
                    )
        
        finally:
            self.is_executing = False
            duration = time.time() - start_time
            
            # Clear remaining actions
            self.actions.clear()
            self.active_ids.clear()
            
            logger.info(
                f"[ACTION QUEUE] Execution complete. "
                f"Executed: {self.total_executed}, Failed: {self.total_failed}, "
                f"Duration: {duration:.2f}s"
            )
            
            return {
                "executed": self.total_executed,
                "failed": self.total_failed,
                "duration_seconds": duration,
            }

    def cancel_all(self) -> None:
        """Cancel all queued actions and stop execution."""
        self.cancelled = True
        self.actions.clear()
        self.active_ids.clear()
        logger.info("[ACTION QUEUE] All actions cancelled")

    def get_stats(self) -> Dict[str, int]:
        """Return queue statistics."""
        return {
            "total_queued": self.total_queued,
            "total_executed": self.total_executed,
            "total_failed": self.total_failed,
            "currently_queued": len(self.actions),
            "is_executing": self.is_executing,
        }


# Global queue instance (singleton pattern)
_global_queue: Optional[ActionQueue] = None


def get_global_queue() -> ActionQueue:
    """Get or create the global action queue."""
    global _global_queue
    if _global_queue is None:
        _global_queue = ActionQueue()
    return _global_queue


def enqueue_action(
    delay_seconds: float,
    func: Callable,
    *args,
    action_id: str = "",
    **kwargs
) -> str:
    """
    Convenience function to enqueue on the global queue.

    Args:
        delay_seconds: When to execute (in seconds).
        func: The callable to execute.
        *args: Positional arguments.
        action_id: Optional action ID.
        **kwargs: Keyword arguments.

    Returns:
        The action ID.
    """
    return get_global_queue().enqueue(
        delay_seconds, func, *args, action_id=action_id, **kwargs
    )


async def execute_global_queue() -> Dict[str, Any]:
    """Execute all actions on the global queue."""
    return await get_global_queue().execute_all()


def cancel_global_queue() -> None:
    """Cancel all actions on the global queue."""
    get_global_queue().cancel_all()


# Example usage (for testing)
if __name__ == "__main__":
    async def main():
        # Configure logging
        logging.basicConfig(level=logging.DEBUG)
        
        # Define mock functions
        def draw_box():
            print("  [Drawing box]")
        
        def add_text():
            print("  [Adding text label]")
        
        def clear():
            print("  [Clearing annotations]")
        
        # Create and populate queue
        queue = ActionQueue()
        queue.enqueue(0.0, draw_box)
        queue.enqueue(0.5, add_text)
        queue.enqueue(2.0, clear)
        
        # Execute
        print("\nExecuting queue...")
        stats = await queue.execute_all()
        print(f"\nResults: {stats}")
    
    # Run example
    asyncio.run(main())
