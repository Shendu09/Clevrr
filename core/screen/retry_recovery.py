"""Retry and Recovery System
============================

Handles task retries, recovery actions, and escalation strategies.
"""

import logging
import asyncio
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy options."""
    IMMEDIATE = "immediate"  # Retry immediately
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # 1s, 2s, 4s, ...
    LINEAR_BACKOFF = "linear_backoff"  # 1s, 2s, 3s, ...
    FIXED_DELAY = "fixed_delay"  # Always same delay


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay_ms: int = 100
    max_delay_ms: int = 5000
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    backoff_multiplier: float = 2.0
    
    def get_delay_ms(self, attempt: int) -> int:
        """Calculate delay for given attempt number.
        
        Args:
            attempt: Attempt number (0-based)
            
        Returns:
            Delay in milliseconds
        """
        if self.strategy == RetryStrategy.IMMEDIATE:
            return 0
        elif self.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.initial_delay_ms * (attempt + 1)
        elif self.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = int(self.initial_delay_ms * (self.backoff_multiplier ** attempt))
        else:  # FIXED_DELAY
            delay = self.initial_delay_ms
        
        return min(delay, self.max_delay_ms)


class RecoveryAction(Enum):
    """Possible recovery actions."""
    RETRY = "retry"  # Try the task again
    RESET_STATE = "reset_state"  # Reset to known good state
    RESTART_APP = "restart_app"  # Restart the application
    SCREENSHOT = "screenshot"  # Take screenshot to assess
    REFRESH_PAGE = "refresh_page"  # Refresh browser page
    PRESS_ESCAPE = "press_escape"  # Press escape key
    CLICK_BACK = "click_back"  # Go back
    WAIT = "wait"  # Wait and retry
    ESCALATE = "escalate"  # Escalate to human or different handler


@dataclass
class RecoveryAttempt:
    """Record of a recovery attempt."""
    action: RecoveryAction
    timestamp: datetime
    success: bool = False
    error: Optional[str] = None
    details: Dict[str, Any] = None


class TaskRetry:
    """Handles task retries with configurable backoff."""
    
    def __init__(self, policy: Optional[RetryPolicy] = None):
        """Initialize retry handler.
        
        Args:
            policy: Retry policy configuration
        """
        self.policy = policy or RetryPolicy()
        self.attempts = 0
        self.last_error: Optional[str] = None
        logger.info(f"TaskRetry initialized with policy: {self.policy.strategy.value}")
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> tuple:
        """Execute function with automatic retry.
        
        Args:
            func: Async function to execute
            *args: Arguments to pass to function
            **kwargs: Keyword arguments to pass to function
            
        Returns:
            Tuple of (success, result, error_message)
        """
        self.attempts = 0
        last_error = None
        
        while self.attempts < self.policy.max_attempts:
            try:
                result = await func(*args, **kwargs)
                logger.info(f"Task succeeded on attempt {self.attempts + 1}")
                return (True, result, None)
            except Exception as e:
                self.attempts += 1
                last_error = str(e)
                
                if self.attempts >= self.policy.max_attempts:
                    logger.error(f"Task failed after {self.attempts} attempts: {e}")
                    return (False, None, last_error)
                
                delay_ms = self.policy.get_delay_ms(self.attempts - 1)
                logger.warning(
                    f"Attempt {self.attempts} failed ({e}), "
                    f"retrying in {delay_ms}ms..."
                )
                await asyncio.sleep(delay_ms / 1000.0)
        
        return (False, None, last_error)
    
    def get_attempts(self) -> int:
        """Get number of attempts made."""
        return self.attempts


class RecoveryManager:
    """Manages recovery from failures."""
    
    def __init__(self, executor=None):
        """Initialize recovery manager.
        
        Args:
            executor: Executor for performing recovery actions
        """
        self.executor = executor
        self.recovery_history: List[RecoveryAttempt] = []
        self.max_recoveries = 50
        logger.info("RecoveryManager initialized")
    
    async def attempt_recovery(
        self,
        action: RecoveryAction,
        **details
    ) -> bool:
        """Attempt a recovery action.
        
        Args:
            action: Recovery action to attempt
            **details: Additional details about action
            
        Returns:
            True if recovery succeeded
        """
        logger.info(f"Attempting recovery: {action.value}")
        
        try:
            if action == RecoveryAction.RETRY:
                # Retry is handled by retry logic
                return True
            elif action == RecoveryAction.SCREENSHOT:
                # Take screenshot
                if self.executor:
                    await self.executor.take_screenshot()
                return True
            elif action == RecoveryAction.REFRESH_PAGE:
                # Refresh page
                if self.executor:
                    await self.executor.press_key("f5")
                return True
            elif action == RecoveryAction.PRESS_ESCAPE:
                # Press escape
                if self.executor:
                    await self.executor.press_key("escape")
                return True
            elif action == RecoveryAction.CLICK_BACK:
                # Go back
                if self.executor:
                    await self.executor.press_key("escape")  # Browser back
                return True
            elif action == RecoveryAction.WAIT:
                # Wait
                delay = details.get("delay_ms", 1000)
                await asyncio.sleep(delay / 1000.0)
                return True
            elif action == RecoveryAction.RESET_STATE:
                # Reset to known state
                if self.executor:
                    # Implementation would be app-specific
                    pass
                return True
            elif action == RecoveryAction.RESTART_APP:
                # Restart app
                if self.executor:
                    # Implementation would be app-specific
                    pass
                return True
            elif action == RecoveryAction.ESCALATE:
                # Escalate
                logger.warning("Escalating task - human intervention may be needed")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Recovery action failed: {e}")
            self._record_attempt(action, success=False, error=str(e), **details)
            return False
    
    def _record_attempt(
        self,
        action: RecoveryAction,
        success: bool = False,
        error: Optional[str] = None,
        **details
    ):
        """Record recovery attempt."""
        attempt = RecoveryAttempt(
            action=action,
            timestamp=datetime.now(),
            success=success,
            error=error,
            details=details
        )
        
        self.recovery_history.append(attempt)
        
        # Keep history bounded
        if len(self.recovery_history) > self.max_recoveries:
            self.recovery_history.pop(0)
    
    def get_recovery_history(self) -> List[RecoveryAttempt]:
        """Get recovery history."""
        return self.recovery_history.copy()
    
    def get_successful_recoveries(self) -> int:
        """Get count of successful recoveries."""
        return sum(1 for a in self.recovery_history if a.success)
    
    def get_failed_recoveries(self) -> int:
        """Get count of failed recoveries."""
        return sum(1 for a in self.recovery_history if not a.success)


class ReliableTaskExecutor:
    """Executes tasks with retries and recovery."""
    
    def __init__(
        self,
        executor=None,
        retry_policy: Optional[RetryPolicy] = None
    ):
        """Initialize executor.
        
        Args:
            executor: Underlying executor for actions
            retry_policy: Retry policy for tasks
        """
        self.executor = executor
        self.retry = TaskRetry(retry_policy)
        self.recovery = RecoveryManager(executor)
        logger.info("ReliableTaskExecutor initialized")
    
    async def execute_task(
        self,
        task_func: Callable,
        recovery_actions: Optional[List[RecoveryAction]] = None,
        *args,
        **kwargs
    ) -> tuple:
        """Execute task with retries and recovery.
        
        Args:
            task_func: Function to execute
            recovery_actions: Actions to attempt if task fails
            *args: Arguments to pass to function
            **kwargs: Keyword arguments to pass to function
            
        Returns:
            Tuple of (success, result, error_message)
        """
        logger.info(f"Executing task with reliability: {task_func.__name__}")
        
        # Try with retries first
        success, result, error = await self.retry.execute_with_retry(
            task_func, *args, **kwargs
        )
        
        if success:
            return (True, result, None)
        
        # If task failed, try recovery
        if recovery_actions:
            for action in recovery_actions:
                logger.info(f"Attempting recovery action: {action.value}")
                recovery_ok = await self.recovery.attempt_recovery(action)
                
                if recovery_ok and action != RecoveryAction.ESCALATE:
                    # Try task again
                    success, result, error = await self.retry.execute_with_retry(
                        task_func, *args, **kwargs
                    )
                    if success:
                        return (True, result, None)
        
        return (False, None, error)
    
    def get_status(self) -> Dict[str, Any]:
        """Get executor status."""
        return {
            "attempts_made": self.retry.get_attempts(),
            "successful_recoveries": self.recovery.get_successful_recoveries(),
            "failed_recoveries": self.recovery.get_failed_recoveries(),
            "total_recovery_attempts": len(self.recovery.get_recovery_history()),
        }
