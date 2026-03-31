"""Screen State Detector
======================

Analyzes screenshots to detect which screen/state is currently displayed.
Uses vision agent + text detection + pattern matching.
"""

import logging
from typing import Optional, Tuple
from dataclasses import dataclass

from .screen_types import ScreenType

logger = logging.getLogger(__name__)


@dataclass
class ScreenDetectionResult:
    """Result of screen detection."""
    screen_type: ScreenType
    confidence: float  # 0.0 to 1.0
    description: str
    elements: list  # Detected UI elements on screen
    text_content: list  # Text found on screen


class ScreenDetector:
    """Detects current screen state from screenshot."""
    
    def __init__(self, vision_agent=None):
        """Initialize screen detector.
        
        Args:
            vision_agent: Vision agent for analysis (optional, uses fallback if None)
        """
        self.vision_agent = vision_agent
        logger.info("ScreenDetector initialized")
    
    def detect(self, screenshot: Optional[bytes]) -> ScreenDetectionResult:
        """Detect screen type from screenshot.
        
        Args:
            screenshot: Screenshot bytes (PIL Image or numpy array)
            
        Returns:
            ScreenDetectionResult with detected type and confidence
        """
        if screenshot is None:
            logger.warning("No screenshot provided, returning UNKNOWN")
            return ScreenDetectionResult(
                screen_type=ScreenType.UNKNOWN,
                confidence=0.0,
                description="No screenshot provided",
                elements=[],
                text_content=[]
            )
        
        # Use vision agent if available
        if self.vision_agent:
            return self._detect_with_vision(screenshot)
        else:
            return self._detect_with_heuristics(screenshot)
    
    def _detect_with_vision(self, screenshot: bytes) -> ScreenDetectionResult:
        """Detect screen using vision agent analysis."""
        try:
            analysis = self.vision_agent.analyze_screen(screenshot)
            
            screen_desc = analysis.get("screen_description", "").lower()
            screen_type = self._classify_from_text(screen_desc)
            
            return ScreenDetectionResult(
                screen_type=screen_type,
                confidence=analysis.get("confidence", 0.8),
                description=analysis.get("screen_description", "Unknown"),
                elements=analysis.get("elements", []),
                text_content=analysis.get("text", [])
            )
        except Exception as e:
            logger.error(f"Vision detection failed: {e}, falling back to heuristics")
            return self._detect_with_heuristics(screenshot)
    
    def _detect_with_heuristics(self, screenshot: bytes) -> ScreenDetectionResult:
        """Fallback: detect screen using image heuristics."""
        # This is a placeholder for heuristic-based detection
        # In real implementation, would analyze image properties
        return ScreenDetectionResult(
            screen_type=ScreenType.UNKNOWN,
            confidence=0.5,
            description="Heuristic detection (limited)",
            elements=[],
            text_content=[]
        )
    
    def _classify_from_text(self, text: str) -> ScreenType:
        """Classify screen type from text description."""
        text_lower = text.lower()
        
        # Chrome profile detection
        if any(x in text_lower for x in ["profile", "who's using", "select profile", "chrome user"]):
            return ScreenType.CHROME_PROFILE
        
        # Chrome browser detection
        if any(x in text_lower for x in ["browser", "chrome", "tab", "address bar"]):
            return ScreenType.CHROME_BROWSER
        
        # Google detection
        if "google" in text_lower:
            if any(x in text_lower for x in ["search results", "results"]):
                return ScreenType.GOOGLE_SEARCH_RESULTS
            else:
                return ScreenType.GOOGLE_HOMEPAGE
        
        # YouTube detection
        if "youtube" in text_lower:
            if any(x in text_lower for x in ["video playing", "playing"]):
                return ScreenType.YOUTUBE_VIDEO
            else:
                return ScreenType.YOUTUBE_HOME
        
        # Login detection
        if any(x in text_lower for x in ["login", "password", "username", "sign in"]):
            return ScreenType.LOGIN_PAGE
        
        # Error detection
        if any(x in text_lower for x in ["error", "failed", "not found", "404", "500"]):
            return ScreenType.ERROR_PAGE
        
        # Desktop detection
        if any(x in text_lower for x in ["desktop", "taskbar"]):
            return ScreenType.DESKTOP
        
        # File explorer
        if any(x in text_lower for x in ["explorer", "files", "folder"]):
            return ScreenType.FILE_EXPLORER
        
        return ScreenType.UNKNOWN
    
    def detect_text_in_screenshot(self, screenshot: bytes) -> list:
        """Extract text from screenshot."""
        try:
            if self.vision_agent:
                analysis = self.vision_agent.analyze_screen(screenshot)
                return analysis.get("text", [])
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
        
        return []
    
    def detect_elements_in_screenshot(self, screenshot: bytes) -> list:
        """Detect UI elements in screenshot."""
        try:
            if self.vision_agent:
                analysis = self.vision_agent.analyze_screen(screenshot)
                return analysis.get("elements", [])
        except Exception as e:
            logger.error(f"Element detection failed: {e}")
        
        return []
