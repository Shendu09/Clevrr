"""
Action Verification & Retry System.

Verifies action success using vision, compares screenshots, or explicit checks.
Automatically retries on failure with exponential backoff.

Workflow:
1. User: "Click the blue button"
2. Take screenshot BEFORE
3. Execute action (click button)
4. Take screenshot AFTER
5. Compare images → Different? → Success!
6. On failure: Retry with alternative approach
"""

import logging
import time
from typing import Callable, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ActionStatus(Enum):
    """Status of action execution."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"
    TIMEOUT = "timeout"


@dataclass
class ActionResult:
    """Result of action execution and verification."""
    status: ActionStatus
    description: str
    success: bool
    attempts: int = 1
    time_taken: float = 0.0
    error_message: Optional[str] = None
    verification_details: Optional[Dict[str, Any]] = None


class ActionVerifier:
    """Verify that actions succeed."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.verification_methods = []
    
    def register_verifier(self, 
                         name: str,
                         verifier_func: Callable[[], bool],
                         priority: int = 100):
        """
        Register action verification method.
        
        Args:
            name: Verifier name
            verifier_func: Function that returns True if action succeeded
            priority: Higher = checked first
        """
        self.verification_methods.append({
            "name": name,
            "func": verifier_func,
            "priority": priority
        })
        self.verification_methods.sort(key=lambda x: x["priority"], reverse=True)
        logger.debug(f"[ActionVerifier] Registered: {name}")
    
    def verify(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Run all verifiers and return result.
        
        Returns:
            (success: bool, details: {method_name: result, ...})
        """
        details = {}
        success = False
        
        for verifier in self.verification_methods:
            try:
                result = verifier["func"]()
                details[verifier["name"]] = result
                if result:
                    success = True
                    break  # Stop on first success
            except Exception as e:
                logger.warning(f"[ActionVerifier] {verifier['name']} error: {e}")
                details[verifier["name"]] = False
        
        return success, details


class ScreenChangeVerifier:
    """Verify action by detecting screen changes."""
    
    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
        self.before_screenshot = None
    
    def capture_before(self) -> bool:
        """Capture screen before action."""
        try:
            from utils.screen_capture import ScreenCapture
            capture = ScreenCapture()
            self.before_screenshot = capture.capture_screen()
            return True
        except Exception as e:
            logger.error(f"[ScreenChangeVerifier] Failed to capture before: {e}")
            return False
    
    def verify_after(self) -> bool:
        """Check if screen changed."""
        try:
            if self.before_screenshot is None:
                logger.warning("[ScreenChangeVerifier] No before screenshot")
                return False
            
            from utils.screen_capture import ScreenCapture
            from utils.image_comparison import ImageComparator
            
            capture = ScreenCapture()
            after = capture.capture_screen()
            
            comparator = ImageComparator(similarity_threshold=self.similarity_threshold)
            result = comparator.compare(self.before_screenshot, after)
            
            is_different = result.is_different
            logger.debug(f"[ScreenChangeVerifier] Change detected: {is_different} "
                        f"(SSIM: {result.ssim_score:.2f})")
            
            return is_different
        except Exception as e:
            logger.error(f"[ScreenChangeVerifier] Failed to verify after: {e}")
            return False


class ActionRetry:
    """Retry action with exponential backoff."""
    
    def __init__(self,
                 max_retries: int = 3,
                 base_delay: float = 0.5,
                 max_delay: float = 5.0):
        """
        Initialize retry strategy.
        
        Args:
            max_retries: Maximum retry attempts
            base_delay: Initial delay between retries (seconds)
            max_delay: Maximum delay between retries
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.attempt = 0
    
    def execute_with_retry(self,
                          action: Callable[[], bool],
                          verifier: Optional[Callable[[], bool]] = None,
                          action_description: str = "action") -> ActionResult:
        """
        Execute action with automatic retry.
        
        Args:
            action: Function to execute (should return True/False or raise exception)
            verifier: Optional verification function (returns True if successful)
            action_description: Description for logging
        
        Returns:
            ActionResult with status and details
        """
        start_time = time.time()
        self.attempt = 0
        last_error = None
        
        while self.attempt < self.max_retries:
            self.attempt += 1
            
            try:
                logger.info(f"[ActionRetry] Attempt {self.attempt}/{self.max_retries}: {action_description}")
                
                # Execute action
                action_result = action()
                
                # Verify if verifier provided
                verified = True
                if verifier:
                    verified = verifier()
                
                if action_result and verified:
                    elapsed = time.time() - start_time
                    logger.info(f"[ActionRetry] SUCCESS (took {elapsed:.2f}s)")
                    return ActionResult(
                        status=ActionStatus.SUCCESS,
                        description=f"{action_description} succeeded",
                        success=True,
                        attempts=self.attempt,
                        time_taken=elapsed
                    )
                else:
                    raise Exception(f"Action or verification failed")
            
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[ActionRetry] Attempt {self.attempt} failed: {e}")
                
                # Calculate backoff delay
                if self.attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (2 ** (self.attempt - 1)),
                        self.max_delay
                    )
                    logger.debug(f"[ActionRetry] Retrying in {delay:.1f}s...")
                    time.sleep(delay)
        
        # All retries exhausted
        elapsed = time.time() - start_time
        logger.error(f"[ActionRetry] FAILED after {self.attempt} attempts")
        
        return ActionResult(
            status=ActionStatus.FAILED,
            description=f"{action_description} failed after {self.attempt} attempts",
            success=False,
            attempts=self.attempt,
            time_taken=elapsed,
            error_message=last_error
        )


class SmartActionExecutor:
    """Execute actions with verification and retry."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.verifier = ActionVerifier(config)
        self.screen_verifier = ScreenChangeVerifier()
        self.retry = ActionRetry(
            max_retries=config.get("max_retries", 3),
            base_delay=config.get("retry_delay", 0.5)
        )
    
    def execute(self,
               action: Callable[[], bool],
               description: str = "action",
               verify_screen_change: bool = True,
               custom_verifier: Optional[Callable[[], bool]] = None) -> ActionResult:
        """
        Execute action with smart verification and retry.
        
        Args:
            action: Action to execute
            description: Action description
            verify_screen_change: Use screenshot comparison to verify
            custom_verifier: Custom verification function
        
        Returns:
            ActionResult with execution details
        """
        
        # Setup verifier
        def _verify():
            # First try screen change
            if verify_screen_change:
                if self.screen_verifier.verify_after():
                    return True
            
            # Then try custom verifier
            if custom_verifier:
                return custom_verifier()
            
            return True  # Default to success if no verification
        
        # Capture before screenshot
        if verify_screen_change:
            self.screen_verifier.capture_before()
        
        # Execute with retry
        return self.retry.execute_with_retry(
            action=action,
            verifier=_verify,
            action_description=description
        )
    
    def execute_sequence(self,
                        actions: list[Tuple[Callable, str]]) -> list[ActionResult]:
        """
        Execute sequence of actions.
        
        Args:
            actions: List of (action_func, description) tuples
        
        Returns:
            List of ActionResults
        """
        results = []
        
        for i, (action, description) in enumerate(actions):
            logger.info(f"[SmartActionExecutor] Step {i+1}/{len(actions)}: {description}")
            
            result = self.execute(action, description)
            results.append(result)
            
            # Stop on failure unless configured to continue
            if not result.success and not self.config.get("continue_on_failure", False):
                logger.warning(f"[SmartActionExecutor] Stopping due to failure at step {i+1}")
                break
        
        return results


# Global executor instance
_executor: Optional[SmartActionExecutor] = None


def initialize_executor(config: dict = None) -> SmartActionExecutor:
    """Initialize global action executor."""
    global _executor
    _executor = SmartActionExecutor(config)
    return _executor


def get_executor() -> SmartActionExecutor:
    """Get global action executor."""
    global _executor
    if _executor is None:
        _executor = SmartActionExecutor()
    return _executor


def execute_action(action: Callable,
                  description: str = "action",
                  verify: bool = True) -> ActionResult:
    """Execute action with verification and retry."""
    return get_executor().execute(action, description, verify_screen_change=verify)


def execute_sequence(actions: list) -> list[ActionResult]:
    """Execute sequence of actions."""
    return get_executor().execute_sequence(actions)
