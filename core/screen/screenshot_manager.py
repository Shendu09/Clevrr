"""Screenshot Comparison System
===============================

Compares screenshots to detect changes and state transitions.
"""

import logging
import hashlib
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
import io

logger = logging.getLogger(__name__)


@dataclass
class ScreenshotMetadata:
    """Metadata about a screenshot."""
    hash: str  # SHA256 hash
    size: int  # File size in bytes
    width: int
    height: int
    
    def __eq__(self, other) -> bool:
        """Compare screenshots by hash."""
        if not isinstance(other, ScreenshotMetadata):
            return False
        return self.hash == other.hash


class ScreenshotComparator:
    """Compares screenshots to detect changes."""
    
    def __init__(self):
        """Initialize comparator."""
        self.last_screenshot: Optional[bytes] = None
        self.last_metadata: Optional[ScreenshotMetadata] = None
        logger.info("ScreenshotComparator initialized")
    
    @staticmethod
    def compute_hash(screenshot: bytes) -> str:
        """Compute SHA256 hash of screenshot.
        
        Args:
            screenshot: Screenshot bytes
            
        Returns:
            Hex digest of SHA256 hash
        """
        return hashlib.sha256(screenshot).hexdigest()
    
    @staticmethod
    def get_metadata(screenshot: bytes) -> ScreenshotMetadata:
        """Get metadata about screenshot.
        
        Args:
            screenshot: Screenshot bytes
            
        Returns:
            ScreenshotMetadata
        """
        try:
            from PIL import Image
            
            # Parse image
            img = Image.open(io.BytesIO(screenshot))
            width, height = img.size
        except Exception as e:
            logger.warning(f"Could not parse image metadata: {e}")
            width = height = 0
        
        return ScreenshotMetadata(
            hash=ScreenshotComparator.compute_hash(screenshot),
            size=len(screenshot),
            width=width,
            height=height,
        )
    
    def is_changed(self, screenshot: bytes) -> bool:
        """Check if screenshot has changed from last one.
        
        Args:
            screenshot: New screenshot bytes
            
        Returns:
            True if screenshot has changed
        """
        if self.last_screenshot is None:
            return True
        
        return self.compute_hash(screenshot) != self.compute_hash(
            self.last_screenshot
        )
    
    def update(self, screenshot: bytes) -> ScreenshotMetadata:
        """Update reference screenshot.
        
        Args:
            screenshot: New screenshot bytes
            
        Returns:
            Metadata of new screenshot
        """
        self.last_screenshot = screenshot
        self.last_metadata = self.get_metadata(screenshot)
        logger.debug(f"Updated screenshot reference (hash: {self.last_metadata.hash[:8]}...)")
        return self.last_metadata
    
    @staticmethod
    def pixel_difference(
        screenshot1: bytes,
        screenshot2: bytes
    ) -> Optional[float]:
        """Calculate pixel-level difference between screenshots.
        
        Args:
            screenshot1: First screenshot bytes
            screenshot2: Second screenshot bytes
            
        Returns:
            Percentage difference (0.0 to 1.0) or None on error
        """
        try:
            from PIL import Image, ImageChops
            
            img1 = Image.open(io.BytesIO(screenshot1))
            img2 = Image.open(io.BytesIO(screenshot2))
            
            # Ensure same size
            if img1.size != img2.size:
                img2 = img2.resize(img1.size)
            
            # Calculate difference
            diff = ImageChops.difference(img1, img2)
            stat = diff.convert("L").getextrema()
            
            # Return percentage (0-1)
            return (stat[1] / 255.0) if stat[1] > 0 else 0.0
        except Exception as e:
            logger.warning(f"Could not compute pixel difference: {e}")
            return None
    
    @staticmethod
    def get_diff_regions(
        screenshot1: bytes,
        screenshot2: bytes,
        threshold: int = 50
    ) -> list:
        """Get regions where screenshots differ.
        
        Args:
            screenshot1: First screenshot bytes
            screenshot2: Second screenshot bytes
            threshold: How different pixels must be (0-255)
            
        Returns:
            List of regions with differences
        """
        try:
            from PIL import Image, ImageChops
            
            img1 = Image.open(io.BytesIO(screenshot1))
            img2 = Image.open(io.BytesIO(screenshot2))
            
            if img1.size != img2.size:
                img2 = img2.resize(img1.size)
            
            # Get difference
            diff = ImageChops.difference(img1, img2)
            diff_array = diff.convert("L")
            
            # Get bounding box of difference
            bbox = diff_array.getbbox()
            if bbox:
                return [(bbox[0], bbox[1], bbox[2], bbox[3])]
            
            return []
        except Exception as e:
            logger.warning(f"Could not get diff regions: {e}")
            return []


class ScreenshotCache:
    """Caches screenshots for comparison and analysis."""
    
    def __init__(self, max_cache: int = 10):
        """Initialize cache.
        
        Args:
            max_cache: Maximum screenshots to keep
        """
        self.max_cache = max_cache
        self.cache: Dict[str, bytes] = {}  # hash -> screenshot
        self.order: list = []  # Insertion order
        logger.info(f"ScreenshotCache initialized (max: {max_cache})")
    
    def add(self, screenshot: bytes) -> str:
        """Add screenshot to cache.
        
        Args:
            screenshot: Screenshot bytes
            
        Returns:
            Hash of screenshot
        """
        hash_val = ScreenshotComparator.compute_hash(screenshot)
        
        if hash_val not in self.cache:
            self.cache[hash_val] = screenshot
            self.order.append(hash_val)
            
            # Evict old entries
            while len(self.order) > self.max_cache:
                old_hash = self.order.pop(0)
                del self.cache[old_hash]
            
            logger.debug(f"Cached screenshot (hash: {hash_val[:8]}...)")
        
        return hash_val
    
    def get(self, hash_val: str) -> Optional[bytes]:
        """Get screenshot from cache.
        
        Args:
            hash_val: Hash of screenshot
            
        Returns:
            Screenshot bytes or None
        """
        return self.cache.get(hash_val)
    
    def get_by_index(self, index: int) -> Optional[bytes]:
        """Get screenshot by index.
        
        Args:
            index: Index (0 = oldest)
            
        Returns:
            Screenshot bytes or None
        """
        if 0 <= index < len(self.order):
            hash_val = self.order[index]
            return self.cache.get(hash_val)
        return None
    
    def get_last(self) -> Optional[bytes]:
        """Get most recent screenshot.
        
        Returns:
            Screenshot bytes or None
        """
        return self.get_by_index(-1) if self.order else None
    
    def size(self) -> int:
        """Get cache size."""
        return len(self.cache)
    
    def clear(self):
        """Clear cache."""
        self.cache.clear()
        self.order.clear()
        logger.info("Screenshot cache cleared")
