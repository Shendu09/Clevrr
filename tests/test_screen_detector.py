"""Tests for Screen Classification System
==========================================

Test suite for screen state detection and handling.
"""

import pytest
from unittest.mock import Mock
from core.screen.screen_types import ScreenType
from core.screen.screen_detector import ScreenDetector, ScreenDetectionResult


class TestScreenType:
    """Tests for ScreenType enum."""
    
    def test_screen_type_values(self):
        """Test that screen types have correct values."""
        assert ScreenType.DESKTOP.value == "desktop"
        assert ScreenType.CHROME_PROFILE.value == "chrome_profile"
        assert ScreenType.GOOGLE_HOMEPAGE.value == "google_homepage"
    
    def test_is_browser(self):
        """Test browser detection."""
        assert ScreenType.CHROME_BROWSER.is_browser()
        assert ScreenType.GOOGLE_HOMEPAGE.is_browser()
        assert ScreenType.YOUTUBE_HOME.is_browser()
        
        assert not ScreenType.DESKTOP.is_browser()
        assert not ScreenType.FILE_EXPLORER.is_browser()
    
    def test_is_desktop(self):
        """Test desktop detection."""
        assert ScreenType.DESKTOP.is_desktop()
        assert ScreenType.FILE_EXPLORER.is_desktop()
        
        assert not ScreenType.CHROME_BROWSER.is_desktop()
        assert not ScreenType.GOOGLE_HOMEPAGE.is_desktop()
    
    def test_is_dialog(self):
        """Test dialog detection."""
        assert ScreenType.POPUP_DIALOG.is_dialog()
        assert ScreenType.CONFIRMATION_DIALOG.is_dialog()
        assert ScreenType.ERROR_PAGE.is_dialog()
        
        assert not ScreenType.CHROME_BROWSER.is_dialog()
        assert not ScreenType.GOOGLE_HOMEPAGE.is_dialog()
    
    def test_string_conversion(self):
        """Test string conversion."""
        assert str(ScreenType.DESKTOP) == "desktop"
        assert str(ScreenType.CHROME_PROFILE) == "chrome_profile"


class TestScreenDetectionResult:
    """Tests for ScreenDetectionResult."""
    
    def test_result_creation(self):
        """Test creating detection result."""
        result = ScreenDetectionResult(
            screen_type=ScreenType.GOOGLE_HOMEPAGE,
            confidence=0.95,
            description="Google search homepage",
            elements=["search box", "google logo"],
            text_content=["Google", "Search"]
        )
        
        assert result.screen_type == ScreenType.GOOGLE_HOMEPAGE
        assert result.confidence == 0.95
        assert len(result.elements) == 2
        assert len(result.text_content) == 2


class TestScreenDetector:
    """Tests for ScreenDetector."""
    
    def test_detector_initialization(self):
        """Test detector creation."""
        detector = ScreenDetector()
        assert detector.vision_agent is None
        
        mock_vision = Mock()
        detector_with_vision = ScreenDetector(vision_agent=mock_vision)
        assert detector_with_vision.vision_agent is not None
    
    def test_detect_without_screenshot(self):
        """Test detection with no screenshot."""
        detector = ScreenDetector()
        result = detector.detect(None)
        
        assert result.screen_type == ScreenType.UNKNOWN
        assert result.confidence == 0.0
    
    def test_classify_chrome_profile(self):
        """Test Chrome profile detection."""
        detector = ScreenDetector()
        
        screen_type = detector._classify_from_text("Who's using Chrome? Select your profile")
        assert screen_type == ScreenType.CHROME_PROFILE
    
    def test_classify_google(self):
        """Test Google homepage detection."""
        detector = ScreenDetector()
        
        screen_type = detector._classify_from_text("Google search engine")
        assert screen_type == ScreenType.GOOGLE_HOMEPAGE
    
    def test_classify_search_results(self):
        """Test search results detection."""
        detector = ScreenDetector()
        
        screen_type = detector._classify_from_text("Google search results for BTS V")
        assert screen_type == ScreenType.GOOGLE_SEARCH_RESULTS
    
    def test_classify_youtube(self):
        """Test YouTube detection."""
        detector = ScreenDetector()
        
        screen_type = detector._classify_from_text("YouTube - Video platform")
        assert screen_type in [ScreenType.YOUTUBE_HOME, ScreenType.YOUTUBE_VIDEO]
    
    def test_classify_login(self):
        """Test login page detection."""
        detector = ScreenDetector()
        
        screen_type = detector._classify_from_text("Sign in with username and password")
        assert screen_type == ScreenType.LOGIN_PAGE
    
    def test_classify_error(self):
        """Test error page detection."""
        detector = ScreenDetector()
        
        screen_type = detector._classify_from_text("404 Not Found - Page not found")
        assert screen_type == ScreenType.ERROR_PAGE
    
    def test_classify_desktop(self):
        """Test desktop detection."""
        detector = ScreenDetector()
        
        screen_type = detector._classify_from_text("Windows desktop with taskbar")
        assert screen_type == ScreenType.DESKTOP
    
    def test_classify_file_explorer(self):
        """Test file explorer detection."""
        detector = ScreenDetector()
        
        screen_type = detector._classify_from_text("Windows File Explorer with folders and files")
        assert screen_type == ScreenType.FILE_EXPLORER
    
    def test_classify_unknown(self):
        """Test unknown screen detection."""
        detector = ScreenDetector()
        
        screen_type = detector._classify_from_text("Random unknown content xyz")
        assert screen_type == ScreenType.UNKNOWN


class TestScreenDetectorWithVision:
    """Tests for detector with vision agent."""
    
    def test_detect_with_vision_agent(self):
        """Test detection using vision agent."""
        mock_vision = Mock()
        mock_vision.analyze_screen.return_value = {
            "screen_description": "Chrome browser showing Google homepage",
            "confidence": 0.92,
            "elements": ["address bar", "search box"],
            "text": ["Google", "Search"]
        }
        
        detector = ScreenDetector(vision_agent=mock_vision)
        result = detector.detect(b"screenshot_bytes")
        
        assert result.screen_type == ScreenType.GOOGLE_HOMEPAGE
        assert result.confidence == 0.92
        mock_vision.analyze_screen.assert_called_once()
    
    def test_detect_with_vision_error_fallback(self):
        """Test fallback when vision fails."""
        mock_vision = Mock()
        mock_vision.analyze_screen.side_effect = Exception("Vision error")
        
        detector = ScreenDetector(vision_agent=mock_vision)
        result = detector.detect(b"screenshot_bytes")
        
        # Should fall back to heuristics
        assert result is not None  # At least returns a result
