"""
Image Comparison System — Detect changes between screenshots.

Features:
- Pixel-level comparison
- Structural similarity (SSIM)
- Feature detection
- Bounding box extraction of changes
- Confidence scoring

Used for:
- Action verification (did the UI change?)
- Task completion detection
- Auto-retry on failure
"""

import numpy as np
import cv2
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    """Result of comparing two images."""
    is_different: bool  # True if images are significantly different
    similarity: float  # 0.0-1.0 (1.0 = identical)
    ssim_score: float  # Structural similarity index
    pixel_change_percent: float  # % of pixels that changed
    difference_mask: Optional[np.ndarray] = None  # Mask of changed areas
    changed_regions: List[Tuple[int, int, int, int]] = None  # List of (x, y, w, h)
    confidence: float = 0.0  # Confidence in the comparison


class ImageComparator:
    """Compare images to detect changes."""
    
    def __init__(self, 
                 similarity_threshold: float = 0.85,
                 pixel_threshold: float = 0.05,
                 min_region_size: int = 100):
        """
        Initialize image comparator.
        
        Args:
            similarity_threshold: SSIM threshold for "different" (0.0-1.0)
            pixel_threshold: Pixel change threshold for "different" (0.0-1.0)
            min_region_size: Minimum size of detected region to report
        """
        self.similarity_threshold = similarity_threshold
        self.pixel_threshold = pixel_threshold
        self.min_region_size = min_region_size
    
    def compare(self, 
                image1_path_or_array,
                image2_path_or_array) -> ComparisonResult:
        """
        Compare two images.
        
        Args:
            image1_path_or_array: Path to image 1 or numpy array
            image2_path_or_array: Path to image 2 or numpy array
        
        Returns:
            ComparisonResult with detailed comparison metrics
        """
        # Load images
        img1 = self._load_image(image1_path_or_array)
        img2 = self._load_image(image2_path_or_array)
        
        if img1 is None or img2 is None:
            return ComparisonResult(
                is_different=False,
                similarity=0.0,
                ssim_score=0.0,
                pixel_change_percent=0.0,
                confidence=0.0
            )
        
        # Ensure same size
        if img1.shape != img2.shape:
            height = max(img1.shape[0], img2.shape[0])
            width = max(img1.shape[1], img2.shape[1])
            img1 = cv2.resize(img1, (width, height))
            img2 = cv2.resize(img2, (width, height))
        
        # Convert to grayscale for comparison
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY) if len(img1.shape) == 3 else img1
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY) if len(img2.shape) == 3 else img2
        
        # Calculate metrics
        ssim_score = self._calculate_ssim(gray1, gray2)
        pixel_change = self._calculate_pixel_change(gray1, gray2)
        difference_mask = self._create_difference_mask(gray1, gray2)
        changed_regions = self._extract_changed_regions(difference_mask)
        
        # Determine if different
        is_different = (
            ssim_score < self.similarity_threshold or
            pixel_change > self.pixel_threshold
        )
        
        # Calculate confidence
        confidence = max(ssim_score, 1.0 - pixel_change)
        
        logger.debug(f"[ImageComparison] SSIM: {ssim_score:.3f}, "
                    f"Pixel Change: {pixel_change:.1%}, Different: {is_different}")
        
        return ComparisonResult(
            is_different=is_different,
            similarity=ssim_score,
            ssim_score=ssim_score,
            pixel_change_percent=pixel_change,
            difference_mask=difference_mask,
            changed_regions=changed_regions,
            confidence=confidence
        )
    
    def _load_image(self, image_path_or_array) -> Optional[np.ndarray]:
        """Load image from path or return numpy array."""
        try:
            if isinstance(image_path_or_array, (str, Path)):
                img = cv2.imread(str(image_path_or_array))
                if img is None:
                    logger.error(f"Failed to load image: {image_path_or_array}")
                return img
            elif isinstance(image_path_or_array, np.ndarray):
                return image_path_or_array
            else:
                logger.error(f"Invalid image input type: {type(image_path_or_array)}")
                return None
        except Exception as e:
            logger.error(f"Error loading image: {e}")
            return None
    
    def _calculate_ssim(self, gray1: np.ndarray, gray2: np.ndarray) -> float:
        """Calculate Structural Similarity Index."""
        try:
            from skimage.metrics import structural_similarity as ssim
            score = ssim(gray1, gray2)
            # Normalize to 0-1 range
            return (score + 1) / 2
        except ImportError:
            # Fallback: use mean squared error
            mse = np.mean((gray1.astype(float) - gray2.astype(float)) ** 2)
            # Convert MSE to similarity (0-1)
            if mse > 10000:
                return 0.0
            return 1.0 - (mse / 10000)
        except Exception as e:
            logger.warning(f"SSIM calculation failed: {e}")
            return 0.5
    
    def _calculate_pixel_change(self, gray1: np.ndarray, gray2: np.ndarray) -> float:
        """Calculate percentage of pixels that changed."""
        try:
            # Use Otsu's threshold to detect significant changes
            diff = cv2.absdiff(gray1, gray2)
            _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
            
            changed_pixels = np.count_nonzero(thresh)
            total_pixels = thresh.shape[0] * thresh.shape[1]
            
            return changed_pixels / total_pixels if total_pixels > 0 else 0.0
        except Exception as e:
            logger.warning(f"Pixel change calculation failed: {e}")
            return 0.0
    
    def _create_difference_mask(self, gray1: np.ndarray, gray2: np.ndarray) -> np.ndarray:
        """Create binary mask of changed areas."""
        try:
            diff = cv2.absdiff(gray1, gray2)
            _, mask = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
            
            # Dilate to connect nearby changes
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.dilate(mask, kernel, iterations=2)
            
            return mask
        except Exception as e:
            logger.warning(f"Difference mask creation failed: {e}")
            return np.zeros_like(gray1, dtype=np.uint8)
    
    def _extract_changed_regions(self, mask: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Extract bounding boxes of changed regions."""
        try:
            contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            regions = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                # Only include regions above minimum size
                if w * h >= self.min_region_size:
                    regions.append((x, y, w, h))
            
            return regions
        except Exception as e:
            logger.warning(f"Region extraction failed: {e}")
            return []
    
    def highlight_differences(self,
                            image_path_or_array,
                            comparison: ComparisonResult) -> Optional[np.ndarray]:
        """
        Create visualization of differences.
        
        Args:
            image_path_or_array: Original image
            comparison: ComparisonResult from compare()
        
        Returns:
            Image with bounding boxes around changed regions
        """
        try:
            img = self._load_image(image_path_or_array)
            if img is None or comparison.changed_regions is None:
                return None
            
            # Draw rectangles around changed regions
            for x, y, w, h in comparison.changed_regions:
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.putText(img, "Changed", (x, y - 5),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            
            return img
        except Exception as e:
            logger.error(f"Failed to highlight differences: {e}")
            return None


class ScreenshotComparator:
    """Compare live screenshots to detect changes."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.comparator = ImageComparator(
            similarity_threshold=self.config.get('similarity_threshold', 0.85),
            pixel_threshold=self.config.get('pixel_threshold', 0.05)
        )
        self.last_screenshot = None
    
    def capture_and_compare(self) -> ComparisonResult:
        """
        Capture current screenshot and compare to previous.
        
        Returns:
            ComparisonResult, or None if no previous screenshot
        """
        from utils.screen_capture import ScreenCapture
        
        try:
            capture = ScreenCapture()
            current = capture.capture_screen()
            
            if self.last_screenshot is None:
                self.last_screenshot = current
                return ComparisonResult(
                    is_different=False,
                    similarity=1.0,
                    ssim_score=1.0,
                    pixel_change_percent=0.0,
                    confidence=1.0
                )
            
            # Compare with last
            result = self.comparator.compare(self.last_screenshot, current)
            self.last_screenshot = current
            
            return result
        except Exception as e:
            logger.error(f"Screenshot comparison failed: {e}")
            return None
    
    def reset(self):
        """Reset comparison state."""
        self.last_screenshot = None


# Global comparator instance
_comparator: Optional[ImageComparator] = None


def initialize_comparator(config: dict = None) -> ImageComparator:
    """Initialize global image comparator."""
    global _comparator
    _comparator = ImageComparator()
    return _comparator


def compare_images(img1, img2) -> ComparisonResult:
    """Compare two images."""
    global _comparator
    if _comparator is None:
        _comparator = ImageComparator()
    return _comparator.compare(img1, img2)


def are_different(img1, img2, threshold: float = 0.85) -> bool:
    """Check if images are significantly different."""
    result = compare_images(img1, img2)
    return result.is_different
