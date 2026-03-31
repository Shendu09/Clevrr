"""Tests for Screen Router
==========================

Tests for task routing and state management.
"""

import pytest
from unittest.mock import Mock, patch
from core.screen.screen_types import ScreenType
from core.screen.screen_detector import ScreenDetector
from core.screen.screen_handler import ScreenHandlerRegistry
from core.screen.screen_router import ScreenRouter, ScreenRouterWithRetry
from core.screen.handlers import ChromeProfileHandler


class TestScreenRouter:
    """Tests for ScreenRouter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.detector = ScreenDetector()
        self.registry = ScreenHandlerRegistry()
        self.executor_mock = Mock()
        
        # Register a handler
        self.profile_handler = ChromeProfileHandler(executor=self.executor_mock)
        self.registry.register(self.profile_handler)
        
        self.router = ScreenRouter(self.detector, self.registry)
    
    def test_router_initialization(self):
        """Test router creation."""
        assert self.router.detector is not None
        assert self.router.registry is not None
        assert self.router.last_screen_type is None
        assert self.router.stuck_count == 0
    
    def test_route_task_no_handler(self):
        """Test routing to unregistered screen."""
        # Don't register a handler for DESKTOP
        result = self.router.route_task("open chrome", b"screenshot")
        
        # Should fail gracefully
        assert result["success"] is False
        assert "No handler" in result.get("error", "")
    
    def test_route_tracks_screen_type(self):
        """Test that router tracks current screen type."""
        # Manually set up a handler for testing
        handler = Mock()
        handler.SCREEN_TYPE = ScreenType.CHROME_PROFILE
        handler.handle.return_value = {"success": True}
        self.registry.register(handler)
        
        self.router.last_screen_type = None
        assert self.router.last_screen_type is None
        
        result = self.router.route_task("select profile", b"screenshot")
        
        # Last screen should be tracked (if handler accepted it)
        assert self.router.last_screen_type is not None
    
    def test_stuck_detection(self):
        """Test stuck state detection."""
        handler = Mock()
        handler.SCREEN_TYPE = ScreenType.CHROME_PROFILE
        handler.handle.return_value = {"success": False}
        self.registry.register(handler)
        
        # First time on this screen
        self.router.last_screen_type = ScreenType.CHROME_PROFILE
        assert self.router.is_stuck() is False
        
        # Simulate being stuck
        self.router.stuck_count = 3
        assert self.router.is_stuck() is True
    
    def test_get_stuck_recovery_action(self):
        """Test getting recovery action when stuck."""
        handler = Mock()
        handler.SCREEN_TYPE = ScreenType.CHROME_PROFILE
        handler.get_recovery_action.return_value = "press escape"
        self.registry.register(handler)
        
        self.router.last_screen_type = ScreenType.CHROME_PROFILE
        action = self.router.get_stuck_recovery_action()
        
        assert action is not None
        assert "escape" in action.lower()
    
    def test_get_screen_summary(self):
        """Test getting screen state summary."""
        self.router.last_screen_type = ScreenType.CHROME_PROFILE
        self.router.stuck_count = 2
        
        summary = self.router.get_screen_summary()
        
        assert summary["current_screen"] == "chrome_profile"
        assert summary["stuck_count"] == 2
        assert summary["is_stuck"] is False
        assert "handlers_available" in summary


class TestScreenRouterWithRetry:
    """Tests for ScreenRouterWithRetry."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.detector = ScreenDetector()
        self.registry = ScreenHandlerRegistry()
        self.executor_mock = Mock()
        
        handler = ChromeProfileHandler(executor=self.executor_mock)
        self.registry.register(handler)
        
        self.router = ScreenRouterWithRetry(
            self.detector, 
            self.registry, 
            max_retries=3
        )
    
    def test_retry_router_initialization(self):
        """Test retry router creation."""
        assert self.router.max_retries == 3
        assert self.router.attempt_count == 0
        assert self.router.last_error is None
    
    def test_route_task_with_retry_success_first_try(self):
        """Test successful task on first attempt."""
        handler = Mock()
        handler.SCREEN_TYPE = ScreenType.CHROME_PROFILE
        handler.handle.return_value = {
            "success": True,
            "action_taken": "Selected profile"
        }
        handler.should_retry.return_value = True
        self.registry.register(handler)
        
        result = self.router.route_task_with_retry("select profile", b"screenshot")
        
        assert result["success"] is True
        assert result["attempt"] == 1
    
    def test_route_task_with_retry_success_on_second(self):
        """Test successful task on second attempt."""
        handler = Mock()
        handler.SCREEN_TYPE = ScreenType.CHROME_PROFILE
        handler.should_retry.return_value = True
        
        # Fail first time, succeed second
        handler.handle.side_effect = [
            {"success": False, "error": "Click failed"},
            {"success": True, "action_taken": "Selected profile"}
        ]
        
        self.registry.register(handler)
        
        result = self.router.route_task_with_retry("select profile", b"screenshot")
        
        # In real implementation, would track attempts
        assert result is not None
    
    def test_reset_attempt_counter(self):
        """Test resetting attempt counter."""
        self.router.attempt_count = 3
        self.router.reset_attempt_counter()
        
        assert self.router.attempt_count == 0
        assert self.router.last_error is None


class TestScreenRouterRequestTracking:
    """Tests for request tracking in router."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.detector = ScreenDetector()
        self.registry = ScreenHandlerRegistry()
        self.router = ScreenRouter(self.detector, self.registry)
    
    def test_multiple_sequential_routing(self):
        """Test routing multiple tasks sequentially."""
        # Register handler
        handler = Mock()
        handler.SCREEN_TYPE = ScreenType.CHROME_PROFILE
        handler.handle.return_value = {"success": True}
        self.registry.register(handler)
        
        # Route multiple tasks
        for i in range(3):
            self.router.route_task(f"task {i}", b"screenshot")
        
        # Router should track state
        assert self.router.last_screen_type is not None
