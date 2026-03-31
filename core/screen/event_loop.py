"""Event Loop Screen State Architecture
======================================

Core event loop that processes tasks through screen state detection,
handler routing, action execution, and continuous monitoring.

This is the backbone that makes the system efficient like CLOVIS.
"""

import logging
import asyncio
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class LoopState(Enum):
    """Event loop states."""
    IDLE = "idle"  # Waiting for task
    LISTENING = "listening"  # Waiting for user input
    EXECUTING = "executing"  # Running task
    PLANNING = "planning"  # Running planner
    WATCHING = "watching"  # Watching screen
    ERROR = "error"  # Error state
    SHUTDOWN = "shutdown"  # Shutting down


@dataclass
class LoopMetrics:
    """Metrics for the event loop."""
    tasks_processed: int = 0
    actions_executed: int = 0
    vision_calls: int = 0
    planner_calls: int = 0
    retries_attempted: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    total_time_ms: float = 0.0
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return {
            "tasks_processed": self.tasks_processed,
            "actions_executed": self.actions_executed,
            "vision_calls": self.vision_calls,
            "planner_calls": self.planner_calls,
            "retries_attempted": self.retries_attempted,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "total_time_ms": self.total_time_ms,
            "success_rate": (self.successful_tasks / self.tasks_processed * 100) 
                           if self.tasks_processed > 0 else 0,
        }


@dataclass
class ScreenState:
    """Current screen state."""
    screen_type: str
    screenshot: bytes
    detected_elements: list = field(default_factory=list)
    text_content: list = field(default_factory=list)
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def changed_from(self, other: 'ScreenState') -> bool:
        """Check if screen changed from another state."""
        if other is None:
            return True
        # Screen changed if type differs or significant time passed
        return self.screen_type != other.screen_type


class ScreenStateEventLoop:
    """
    Core event loop that drives task execution through screen states.
    
    Flow:
    1. Capture screenshot
    2. Detect current screen type
    3. Get appropriate handler
    4. Ask handler for next action
    5. Execute action
    6. Log action
    7. Check if done
    8. Loop or finish
    """
    
    def __init__(
        self,
        coordinator,
        executor,
        vision_agent=None,
        action_logger=None,
        max_steps: int = 50
    ):
        """Initialize event loop.
        
        Args:
            coordinator: ScreenStateCoordinator for screen handling
            executor: Executor for performing actions
            vision_agent: Vision agent for screen analysis
            action_logger: Action logger for tracking
            max_steps: Maximum steps per task
        """
        self.coordinator = coordinator
        self.executor = executor
        self.vision_agent = vision_agent
        self.action_logger = action_logger
        self.max_steps = max_steps
        
        self.loop_state = LoopState.IDLE
        self.current_task: Optional[str] = None
        self.current_screen_state: Optional[ScreenState] = None
        self.metrics = LoopMetrics()
        self.task_history: list = []
        
        logger.info("ScreenStateEventLoop initialized")
    
    async def execute_task(self, task_description: str) -> Dict[str, Any]:
        """Execute a task using the event loop.
        
        Args:
            task_description: What to do
            
        Returns:
            Task result
        """
        self.loop_state = LoopState.EXECUTING
        self.current_task = task_description
        step_count = 0
        
        result = {
            "success": False,
            "task": task_description,
            "steps": [],
            "final_screen": None,
            "error": None,
        }
        
        try:
            logger.info(f"Starting task: {task_description}")
            self.metrics.tasks_processed += 1  # Increment once per task
            
            while step_count < self.max_steps:
                step_count += 1
                
                # Step 1: Capture and detect current screen
                self.loop_state = LoopState.WATCHING
                screenshot = await self.executor.take_screenshot()
                self.current_screen_state = await self._detect_screen(screenshot)
                
                logger.debug(
                    f"Step {step_count}: Screen detected as "
                    f"{self.current_screen_state.screen_type}"
                )
                
                # Step 2: Get handler for this screen
                handler = self.coordinator.router.handlers.get(
                    self.current_screen_state.screen_type
                )
                
                if not handler:
                    logger.warning(
                        f"No handler for screen type: "
                        f"{self.current_screen_state.screen_type}"
                    )
                    result["error"] = f"No handler for screen {self.current_screen_state.screen_type}"
                    break
                
                # Step 3: Ask handler for next action
                self.loop_state = LoopState.PLANNING
                action = await handler.get_next_action(
                    task_description,
                    self.current_screen_state
                )
                
                if action is None:
                    # Task complete
                    result["success"] = True
                    logger.info(f"Task completed in {step_count} steps")
                    break
                
                # Step 4: Execute action
                self.loop_state = LoopState.EXECUTING
                logger.info(f"Executing action: {action.get('type', 'unknown')}")
                
                success = await self._execute_action(action)
                self.metrics.actions_executed += 1
                
                if not success and action.get("retry"):
                    self.metrics.retries_attempted += 1
                    logger.warning("Action failed, will retry")
                    continue
                
                # Log action
                if self.action_logger:
                    self.action_logger.log_action(
                        action_type=action.get("type", "unknown"),
                        target=action.get("target"),
                        value=action.get("value"),
                        success=success,
                        screen_state=self.current_screen_state.screen_type
                    )
                
                result["steps"].append({
                    "step": step_count,
                    "action": action,
                    "screen": self.current_screen_state.screen_type,
                    "success": success,
                })
            
            if step_count >= self.max_steps:
                result["error"] = f"Task exceeded max steps ({self.max_steps})"
                logger.warning(f"Task exceeded {self.max_steps} steps")
            
            self.metrics.successful_tasks += int(result.get("success", False))
            self.metrics.failed_tasks += int(not result.get("success", False))
            
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            result["error"] = str(e)
            self.metrics.failed_tasks += 1
        
        finally:
            result["final_screen"] = self.current_screen_state.screen_type if self.current_screen_state else None
            self.loop_state = LoopState.IDLE
            self.current_task = None
            self.task_history.append(result)
        
        return result
    
    async def _detect_screen(self, screenshot: bytes) -> ScreenState:
        """Detect current screen state.
        
        Args:
            screenshot: Current screenshot
            
        Returns:
            ScreenState
        """
        self.metrics.vision_calls += 1
        
        detection = self.coordinator.detector.detect_screen(screenshot)
        
        return ScreenState(
            screen_type=detection.screen_type.value,
            screenshot=screenshot,
            detected_elements=detection.detected_elements,
            text_content=detection.text_content,
            confidence=detection.confidence
        )
    
    async def _execute_action(self, action: Dict[str, Any]) -> bool:
        """Execute a single action.
        
        Args:
            action: Action to execute
            
        Returns:
            True if successful
        """
        try:
            action_type = action.get("type")
            
            if action_type == "click":
                result = await self.executor.click(action["x"], action["y"])
                return result if isinstance(result, bool) else True
            elif action_type == "type":
                result = await self.executor.type_text(action["text"])
                return result if isinstance(result, bool) else True
            elif action_type == "key":
                result = await self.executor.press_key(action["key"])
                return result if isinstance(result, bool) else True
            elif action_type == "navigate":
                result = await self.executor.navigate_to(action["url"])
                return result if isinstance(result, bool) else True
            elif action_type == "wait":
                await asyncio.sleep(action.get("delay_ms", 1000) / 1000.0)
                return True
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current loop status.
        
        Returns:
            Status information
        """
        return {
            "loop_state": self.loop_state.value,
            "current_task": self.current_task,
            "current_screen": self.current_screen_state.screen_type if self.current_screen_state else None,
            "metrics": self.metrics.get_summary(),
            "tasks_in_history": len(self.task_history),
        }
    
    def get_task_history(self, limit: Optional[int] = None) -> list:
        """Get recent task history.
        
        Args:
            limit: Number of recent tasks to return
            
        Returns:
            List of task results
        """
        if limit:
            return self.task_history[-limit:]
        return self.task_history.copy()
