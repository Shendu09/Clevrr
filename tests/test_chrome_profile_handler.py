"""Tests for Chrome Profile Handler
===================================

Tests for handling Chrome profile selection screen.
"""

import pytest
from unittest.mock import Mock, patch
from core.screen.screen_types import ScreenType
from core.screen.handlers.chrome_profile_handler import ChromeProfileHandler


class TestChromeProfileHandler:
    """Tests for ChromeProfileHandler."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.executor_mock = Mock()
        self.handler = ChromeProfileHandler(executor=self.executor_mock)
    
    def test_handler_initialization(self):
        """Test handler creation."""
        assert self.handler.SCREEN_TYPE == ScreenType.CHROME_PROFILE
        assert self.handler.executor is not None
    
    def test_can_handle(self):
        """Test handler capability check."""
        assert self.handler.can_handle(ScreenType.CHROME_PROFILE)
        assert not self.handler.can_handle(ScreenType.CHROME_BROWSER)
        assert not self.handler.can_handle(ScreenType.DESKTOP)
    
    def test_extract_profile_v(self):
        """Test extracting 'V' profile from task."""
        assert self.handler._extract_profile_from_task("Select V profile") == "v"
        assert self.handler._extract_profile_from_task("open with v") == "v"
        assert self.handler._extract_profile_from_task("choose V") == "v"
    
    def test_extract_profile_bushra(self):
        """Test extracting 'Bushra' profile from task."""
        assert self.handler._extract_profile_from_task("select bushra") == "bushra"
        assert self.handler._extract_profile_from_task("open bushra profile") == "bushra"
    
    def test_extract_default_profile(self):
        """Test default profile selection."""
        result = self.handler._extract_profile_from_task("just open Chrome")
        assert result in ["v", "default"]  # Returns default if not specified
    
    def test_click_valid_profile(self):
        """Test clicking a valid profile."""
        self.executor_mock.click.return_value = None
        
        result = self.handler.click_profile("v")
        
        assert result is True
        self.executor_mock.click.assert_called_once()
    
    def test_click_unknown_profile(self):
        """Test clicking unknown profile."""
        result = self.handler.click_profile("unknown_profile")
        
        assert result is False
        self.executor_mock.click.assert_not_called()
    
    def test_click_bushra_profile(self):
        """Test clicking Bushra profile."""
        self.executor_mock.click.return_value = None
        
        result = self.handler.click_profile("bushra")
        
        assert result is True
        self.executor_mock.click.assert_called_once()
    
    def test_handle_task_success(self):
        """Test handling profile selection successfully."""
        self.executor_mock.click.return_value = None
        
        result = self.handler.handle("Select profile V", b"screenshot")
        
        assert result["success"] is True
        assert result["action_taken"] is not None
        assert result["next_screen"] == ScreenType.CHROME_BROWSER
        assert result["confidence"] > 0.9
    
    def test_handle_task_fails(self):
        """Test handling when click fails."""
        self.executor_mock.click.side_effect = Exception("Click failed")
        
        result = self.handler.handle("Select profile V", b"screenshot")
        
        assert result["success"] is False
        assert result["error"] is not None
    
    def test_should_retry(self):
        """Test retry logic."""
        assert self.handler.should_retry(1, None) is True
        assert self.handler.should_retry(2, None) is False  # Max 2 retries
    
    def test_get_recovery_action(self):
        """Test recovery action."""
        action = self.handler.get_recovery_action()
        assert action is not None
        assert "escape" in action.lower()
    
    def test_without_executor(self):
        """Test handler without executor."""
        handler_no_exec = ChromeProfileHandler(executor=None)
        result = handler_no_exec.click_profile("v")
        
        assert result is False


class TestChromeProfileHandlerWithVision:
    """Tests for handler with vision agent."""
    
    def test_handler_with_vision(self):
        """Test handler initialization with vision agent."""
        executor_mock = Mock()
        vision_mock = Mock()
        
        handler = ChromeProfileHandler(executor=executor_mock, vision_agent=vision_mock)
        
        assert handler.executor is not None
        assert handler.vision_agent is not None


class TestChromeProfileCoordinates:
    """Tests for profile click coordinates."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.executor_mock = Mock()
        self.handler = ChromeProfileHandler(executor=self.executor_mock)
    
    def test_v_profile_coordinates(self):
        """Test V profile coordinates."""
        expected_coords = self.handler.PROFILE_COORDINATES["v"]
        assert expected_coords == (960, 540)
        assert isinstance(expected_coords, tuple)
        assert len(expected_coords) == 2
    
    def test_bushra_profile_coordinates(self):
        """Test Bushra profile coordinates."""
        expected_coords = self.handler.PROFILE_COORDINATES["bushra"]
        assert expected_coords == (450, 540)
    
    def test_all_profiles_have_coordinates(self):
        """Test all profiles have defined coordinates."""
        for profile_name, coords in self.handler.PROFILE_COORDINATES.items():
            assert isinstance(coords, tuple)
            assert len(coords) == 2
            x, y = coords
            assert isinstance(x, int) and isinstance(y, int)
            assert x > 0 and y > 0  # Valid screen coordinates
