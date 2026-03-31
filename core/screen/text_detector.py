"""OCR and Text Detection System
===============================

Detects and extracts text from screenshots using multiple strategies.
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TextRegion:
    """Represents a detected text region on screen."""
    text: str
    confidence: float  # 0.0 to 1.0
    x: int
    y: int
    width: int
    height: int
    
    @property
    def center(self) -> tuple:
        """Get center coordinates of text region."""
        return (self.x + self.width // 2, self.y + self.height // 2)
    
    def distance_to(self, x: int, y: int) -> float:
        """Calculate distance to point."""
        cx, cy = self.center
        return ((cx - x) ** 2 + (cy - y) ** 2) ** 0.5


class TextDetector:
    """Detects and extracts text from screenshots."""
    
    def __init__(self, vision_agent=None, use_pytesseract: bool = False):
        """Initialize text detector.
        
        Args:
            vision_agent: Vision agent for text detection
            use_pytesseract: Whether to use pytesseract OCR
        """
        self.vision_agent = vision_agent
        self.use_pytesseract = use_pytesseract
        
        if use_pytesseract:
            try:
                import pytesseract
                self.pytesseract = pytesseract
                logger.info("Pytesseract available for OCR")
            except ImportError:
                logger.warning("Pytesseract not available")
                self.use_pytesseract = False
        
        logger.info("TextDetector initialized")
    
    def detect_text(self, screenshot: bytes) -> List[TextRegion]:
        """Detect all text in screenshot.
        
        Args:
            screenshot: Screenshot bytes
            
        Returns:
            List of detected text regions
        """
        if self.vision_agent:
            return self._detect_with_vision(screenshot)
        elif self.use_pytesseract:
            return self._detect_with_pytesseract(screenshot)
        else:
            logger.warning("No text detection method available")
            return []
    
    def find_text(self, screenshot: bytes, search_text: str) -> Optional[TextRegion]:
        """Find specific text in screenshot.
        
        Args:
            screenshot: Screenshot bytes
            search_text: Text to find
            
        Returns:
            First matching TextRegion or None
        """
        regions = self.detect_text(screenshot)
        search_lower = search_text.lower()
        
        for region in regions:
            if search_lower in region.text.lower():
                return region
        
        return None
    
    def find_clickable_text(
        self,
        screenshot: bytes,
        search_text: str
    ) -> Optional[tuple]:
        """Find text and return click coordinates.
        
        Args:
            screenshot: Screenshot bytes
            search_text: Text to find
            
        Returns:
            (x, y) coordinates to click, or None
        """
        region = self.find_text(screenshot, search_text)
        if region:
            return region.center
        return None
    
    def extract_all_text(self, screenshot: bytes) -> List[str]:
        """Extract all text from screenshot.
        
        Args:
            screenshot: Screenshot bytes
            
        Returns:
            List of detected text strings
        """
        regions = self.detect_text(screenshot)
        return [region.text for region in regions]
    
    def _detect_with_vision(self, screenshot: bytes) -> List[TextRegion]:
        """Detect text using vision agent."""
        try:
            analysis = self.vision_agent.analyze_screen(screenshot)
            text_data = analysis.get("text_regions", [])
            
            regions = []
            for item in text_data:
                if isinstance(item, dict):
                    regions.append(TextRegion(
                        text=item.get("text", ""),
                        confidence=item.get("confidence", 0.8),
                        x=item.get("x", 0),
                        y=item.get("y", 0),
                        width=item.get("width", 0),
                        height=item.get("height", 0),
                    ))
                else:
                    # If just a string
                    regions.append(TextRegion(
                        text=str(item),
                        confidence=0.8,
                        x=0,
                        y=0,
                        width=0,
                        height=0,
                    ))
            
            return regions
        except Exception as e:
            logger.error(f"Vision-based text detection failed: {e}")
            return []
    
    def _detect_with_pytesseract(self, screenshot: bytes) -> List[TextRegion]:
        """Detect text using pytesseract OCR."""
        try:
            from PIL import Image
            import io
            
            # Convert bytes to PIL Image
            img = Image.open(io.BytesIO(screenshot))
            
            # Get text with coordinates
            data = self.pytesseract.image_to_data(img, output_type='dict')
            
            regions = []
            for i in range(len(data['text'])):
                if data['text'][i].strip():  # Skip empty
                    regions.append(TextRegion(
                        text=data['text'][i],
                        confidence=float(data['conf'][i]) / 100.0,
                        x=int(data['left'][i]),
                        y=int(data['top'][i]),
                        width=int(data['width'][i]),
                        height=int(data['height'][i]),
                    ))
            
            logger.debug(f"OCR detected {len(regions)} text regions")
            return regions
        except Exception as e:
            logger.error(f"Pytesseract text detection failed: {e}")
            return []
