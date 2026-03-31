"""Screen State Integration Coordinator
======================================

Orchestrates all screen state systems (detection, handlers, routing, recovery).
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ScreenStateConfig:
    """Configuration for screen state system."""
    enable_vision_detection: bool = True
    enable_ocr: bool = True
    enable_action_logging: bool = True
    enable_screenshots_caching: bool = True
    max_cached_screenshots: int = 20
    retry_max_attempts: int = 3
    retry_initial_delay_ms: int = 100
    recovery_enabled: bool = True


class ScreenStateCoordinator:
    """Coordinates all screen state systems."""
    
    def __init__(
        self,
        executor=None,
        vision_agent=None,
        config: Optional[ScreenStateConfig] = None
    ):
        """Initialize coordinator.
        
        Args:
            executor: Executor for performing actions
            vision_agent: Vision agent for screen analysis
            config: System configuration
        """
        self.executor = executor
        self.vision_agent = vision_agent
        self.config = config or ScreenStateConfig()
        
        self._initialize_subsystems()
        logger.info("ScreenStateCoordinator initialized")
    
    def _initialize_subsystems(self):
        """Initialize all subsystems."""
        # Import subsystems
        from core.screen.screen_detector import ScreenDetector
        from core.screen.screen_router import ScreenRouter, ScreenRouterWithRetry
        from core.screen.text_detector import TextDetector
        from core.screen.action_logger import ActionLogger
        from core.screen.screenshot_manager import ScreenshotCache
        from core.screen.keyboard_shortcuts import KeyboardShortcutsManager
        from core.screen.retry_recovery import RecoveryManager, RetryPolicy, TaskRetry
        
        # Initialize detector
        self.detector = ScreenDetector(
            vision_agent=self.vision_agent if self.config.enable_vision_detection else None
        )
        logger.debug("ScreenDetector initialized")
        
        # Initialize router with retry
        if self.config.enable_vision_detection:
            retry_policy = RetryPolicy(max_attempts=self.config.retry_max_attempts)
            self.router = ScreenRouterWithRetry(
                detector=self.detector,
                executor=self.executor,
                retry_policy=retry_policy
            )
        else:
            self.router = ScreenRouter(detector=self.detector, executor=self.executor)
        logger.debug("ScreenRouter initialized")
        
        # Initialize text detector
        self.text_detector = TextDetector(
            vision_agent=self.vision_agent if self.config.enable_ocr else None
        )
        logger.debug("TextDetector initialized")
        
        # Initialize action logger
        self.action_logger = ActionLogger()
        logger.debug("ActionLogger initialized")
        
        # Initialize screenshot cache
        self.screenshot_cache = ScreenshotCache(
            max_cache=self.config.max_cached_screenshots
        )
        logger.debug("ScreenshotCache initialized")
        
        # Initialize keyboard shortcuts
        self.keyboard = KeyboardShortcutsManager(executor=self.executor)
        logger.debug("KeyboardShortcutsManager initialized")
        
        # Initialize recovery
        self.recovery = RecoveryManager(executor=self.executor)
        logger.debug("RecoveryManager initialized")
    
    async def process_task(
        self,
        task_description: str,
        screenshot: bytes
    ) -> Dict[str, Any]:
        """Process a task using screen state system.
        
        Args:
            task_description: Description of task to perform
            screenshot: Current screenshot
            
        Returns:
            Dictionary with results
        """
        logger.info(f"Processing task: {task_description}")
        
        results = {
            "success": False,
            "task": task_description,
            "screen_type": None,
            "actions_taken": [],
            "error": None,
        }
        
        try:
            # Detect current screen
            detection = self.detector.detect_screen(screenshot)
            results["screen_type"] = detection.screen_type.value
            logger.info(f"Detected screen: {detection.screen_type.value}")
            
            # Cache screenshot
            if self.config.enable_screenshots_caching:
                self.screenshot_cache.add(screenshot)
            
            # Route to appropriate handler
            handler_result = await self.router.route_task(
                task_description,
                detection.screen_type,
                screenshot
            )
            
            if handler_result["success"]:
                results["success"] = True
                results["actions_taken"] = handler_result.get("actions", [])
            else:
                results["error"] = handler_result.get("error", "Unknown error")
                
                # Attempt recovery if enabled
                if self.config.recovery_enabled:
                    logger.info("Task failed, attempting recovery...")
                    # Recovery would be attempted here
            
        except Exception as e:
            logger.error(f"Task processing failed: {e}")
            results["error"] = str(e)
        
        return results
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        return {
            "detector_ready": self.detector is not None,
            "router_ready": self.router is not None,
            "text_detector_ready": self.text_detector is not None,
            "action_logger_history": len(self.action_logger.history),
            "cached_screenshots": self.screenshot_cache.size(),
            "recovery_available": self.config.recovery_enabled,
            "successful_recoveries": self.recovery.get_successful_recoveries(),
            "failed_recoveries": self.recovery.get_failed_recoveries(),
        }
    
    def register_handler(self, screen_type, handler):
        """Register a screen handler."""
        self.router.handlers.register(screen_type, handler)
        logger.debug(f"Registered handler for {screen_type}")
    
    def get_action_summary(self) -> Dict[str, Any]:
        """Get action summary."""
        return self.action_logger.get_summary()
    
    def clear_cache(self):
        """Clear all caches."""
        self.screenshot_cache.clear()
        self.action_logger.clear_history()
        logger.info("Caches cleared")
    
    def get_all_shortcuts(self) -> List[Dict]:
        """Get all available keyboard shortcuts."""
        return self.keyboard.list_shortcuts()
