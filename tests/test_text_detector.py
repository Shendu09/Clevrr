"""Tests for Text Detection System
==================================

Tests OCR, text region detection, and text finding functionality.
"""

import pytest
from core.screen.text_detector import TextRegion, TextDetector


class TestTextRegion:
    """Tests for TextRegion dataclass."""
    
    def test_text_region_creation(self):
        """Test creating a text region."""
        region = TextRegion(
            text="Hello World",
            confidence=0.95,
            x=100,
            y=150,
            width=200,
            height=50
        )
        
        assert region.text == "Hello World"
        assert region.confidence == 0.95
        assert region.x == 100
        assert region.y == 150
    
    def test_text_region_center(self):
        """Test center coordinate calculation."""
        region = TextRegion(
            text="Test",
            confidence=0.9,
            x=100,
            y=100,
            width=100,
            height=50
        )
        
        center = region.center
        assert center == (150, 125)  # (100 + 50, 100 + 25)
    
    def test_text_region_distance(self):
        """Test distance calculation to point."""
        region = TextRegion(
            text="Test",
            confidence=0.9,
            x=0,
            y=0,
            width=20,
            height=20
        )
        
        # Center is (10, 10)
        distance = region.distance_to(10, 10)
        assert distance == 0.0  # Same as center
        
        distance = region.distance_to(13, 14)
        assert distance > 0  # Some distance


class TestTextDetectorInitialization:
    """Tests for TextDetector initialization."""
    
    def test_initialize_without_vision(self):
        """Test creating detector without vision agent."""
        detector = TextDetector(vision_agent=None, use_pytesseract=False)
        
        assert detector.vision_agent is None
        assert detector.use_pytesseract is False
    
    def test_initialize_with_vision_agent(self):
        """Test creating detector with vision agent."""
        class MockVision:
            pass
        
        vision = MockVision()
        detector = TextDetector(vision_agent=vision, use_pytesseract=False)
        
        assert detector.vision_agent is vision
    
    def test_initialize_with_pytesseract_unavailable(self):
        """Test pytesseract flag when module unavailable."""
        detector = TextDetector(use_pytesseract=True)
        
        # Should attempt to import but may fall back
        assert isinstance(detector.use_pytesseract, bool)


class TestTextDetection:
    """Tests for text detection methods."""
    
    def test_detect_text_no_methods(self):
        """Test detect_text with no detection methods available."""
        detector = TextDetector(vision_agent=None, use_pytesseract=False)
        screenshot = b"test_screenshot"
        
        result = detector.detect_text(screenshot)
        
        assert result == []
    
    def test_detect_text_with_mock_vision(self):
        """Test detect_text with mock vision agent."""
        class MockVision:
            def analyze_screen(self, screenshot):
                return {
                    "text_regions": [
                        {
                            "text": "Click me",
                            "confidence": 0.95,
                            "x": 50,
                            "y": 100,
                            "width": 80,
                            "height": 30
                        }
                    ]
                }
        
        detector = TextDetector(vision_agent=MockVision())
        screenshot = b"test"
        
        regions = detector.detect_text(screenshot)
        
        assert len(regions) == 1
        assert regions[0].text == "Click me"
        assert regions[0].confidence == 0.95
        assert regions[0].x == 50
    
    def test_find_text(self):
        """Test finding specific text."""
        class MockVision:
            def analyze_screen(self, screenshot):
                return {
                    "text_regions": [
                        {"text": "Button 1", "confidence": 0.9, "x": 0, "y": 0, "width": 0, "height": 0},
                        {"text": "Button 2", "confidence": 0.9, "x": 100, "y": 0, "width": 0, "height": 0},
                        {"text": "Submit", "confidence": 0.95, "x": 200, "y": 0, "width": 0, "height": 0},
                    ]
                }
        
        detector = TextDetector(vision_agent=MockVision())
        screenshot = b"test"
        
        result = detector.find_text(screenshot, "Submit")
        
        assert result is not None
        assert result.text == "Submit"
    
    def test_find_text_not_found(self):
        """Test finding text that doesn't exist."""
        class MockVision:
            def analyze_screen(self, screenshot):
                return {"text_regions": []}
        
        detector = TextDetector(vision_agent=MockVision())
        screenshot = b"test"
        
        result = detector.find_text(screenshot, "Nonexistent")
        
        assert result is None
    
    def test_find_text_case_insensitive(self):
        """Test text finding is case-insensitive."""
        class MockVision:
            def analyze_screen(self, screenshot):
                return {
                    "text_regions": [
                        {"text": "HELLO WORLD", "confidence": 0.9, "x": 0, "y": 0, "width": 0, "height": 0}
                    ]
                }
        
        detector = TextDetector(vision_agent=MockVision())
        screenshot = b"test"
        
        result = detector.find_text(screenshot, "hello")
        
        assert result is not None
        assert "HELLO" in result.text.upper()
    
    def test_find_clickable_text(self):
        """Test finding clickable text coordinates."""
        class MockVision:
            def analyze_screen(self, screenshot):
                return {
                    "text_regions": [
                        {"text": "Click Here", "confidence": 0.9, "x": 100, "y": 50, "width": 80, "height": 30}
                    ]
                }
        
        detector = TextDetector(vision_agent=MockVision())
        screenshot = b"test"
        
        coords = detector.find_clickable_text(screenshot, "Click Here")
        
        assert coords is not None
        assert isinstance(coords, tuple)
        assert len(coords) == 2
    
    def test_find_clickable_text_not_found(self):
        """Test finding clickable text that doesn't exist."""
        class MockVision:
            def analyze_screen(self, screenshot):
                return {"text_regions": []}
        
        detector = TextDetector(vision_agent=MockVision())
        screenshot = b"test"
        
        coords = detector.find_clickable_text(screenshot, "Nonexistent")
        
        assert coords is None
    
    def test_extract_all_text(self):
        """Test extracting all text from screenshot."""
        class MockVision:
            def analyze_screen(self, screenshot):
                return {
                    "text_regions": [
                        {"text": "Text 1", "confidence": 0.9, "x": 0, "y": 0, "width": 0, "height": 0},
                        {"text": "Text 2", "confidence": 0.9, "x": 0, "y": 0, "width": 0, "height": 0},
                        {"text": "Text 3", "confidence": 0.9, "x": 0, "y": 0, "width": 0, "height": 0},
                    ]
                }
        
        detector = TextDetector(vision_agent=MockVision())
        screenshot = b"test"
        
        texts = detector.extract_all_text(screenshot)
        
        assert len(texts) == 3
        assert "Text 1" in texts
        assert "Text 2" in texts
        assert "Text 3" in texts


class TestTextDetectionVisionIntegration:
    """Tests for vision agent integration."""
    
    def test_vision_fallback_on_error(self):
        """Test fallback when vision agent fails."""
        class BrokenVision:
            def analyze_screen(self, screenshot):
                raise Exception("Vision error")
        
        detector = TextDetector(vision_agent=BrokenVision())
        screenshot = b"test"
        
        result = detector.detect_text(screenshot)
        
        assert result == []
    
    def test_vision_with_string_results(self):
        """Test vision agent returning string results."""
        class SimpleVision:
            def analyze_screen(self, screenshot):
                return {
                    "text_regions": ["Button", "Text", "Label"]
                }
        
        detector = TextDetector(vision_agent=SimpleVision())
        screenshot = b"test"
        
        regions = detector.detect_text(screenshot)
        
        assert len(regions) == 3
        assert regions[0].text == "Button"


class TestTextDetectionEdgeCases:
    """Tests for edge cases and error conditions."""
    
    def test_empty_screenshot(self):
        """Test handling empty screenshot."""
        class MockVision:
            def analyze_screen(self, screenshot):
                return {"text_regions": []}
        
        detector = TextDetector(vision_agent=MockVision())
        screenshot = b""
        
        result = detector.detect_text(screenshot)
        
        assert result == []
    
    def test_region_with_empty_text(self):
        """Test region with empty text string."""
        class MockVision:
            def analyze_screen(self, screenshot):
                return {
                    "text_regions": [
                        {"text": "", "confidence": 0.5, "x": 0, "y": 0, "width": 0, "height": 0}
                    ]
                }
        
        detector = TextDetector(vision_agent=MockVision())
        screenshot = b"test"
        
        regions = detector.detect_text(screenshot)
        
        assert len(regions) == 1
        assert regions[0].text == ""
    
    def test_zero_dimensions(self):
        """Test region with zero width/height."""
        region = TextRegion(
            text="Test",
            confidence=0.9,
            x=100,
            y=100,
            width=0,
            height=0
        )
        
        # Should still work
        assert region.text == "Test"
        assert region.center == (100, 100)
    
    def test_very_low_confidence(self):
        """Test region with very low confidence."""
        region = TextRegion(
            text="Uncertain",
            confidence=0.1,
            x=0,
            y=0,
            width=0,
            height=0
        )
        
        assert region.confidence == 0.1
    
    def test_large_coordinates(self):
        """Test with very large coordinates."""
        region = TextRegion(
            text="Far",
            confidence=0.9,
            x=10000,
            y=10000,
            width=1000,
            height=1000
        )
        
        assert region.x == 10000
        assert region.center == (10500, 10500)
