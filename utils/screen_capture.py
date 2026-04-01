"""
ScreenCapture — Multi-Monitor Screen Capture Utility

Uses mss for fast, cross-platform screen capture.
Supports coordinate grids for AI-guided clicking.
All processing runs locally with OpenCV.
"""

import base64
import logging
import os
import string
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from mss import mss
from PIL import Image

logger = logging.getLogger(__name__)


class ScreenCapture:
    """Captures and annotates screenshots for the AI agent.

    Provides primary, multi-monitor, and active-window capture.
    Can overlay a coordinate grid so the vision model can
    reference specific screen regions by label (e.g. "A1", "B3").
    """

    def __init__(self, config: dict) -> None:
        """Initialize ScreenCapture with configuration.

        Args:
            config: Dictionary containing screen settings from settings.yaml.
        """
        screen_config = config.get("screen", {})
        self.screenshot_dir: str = screen_config.get(
            "screenshot_dir", "data/screenshots"
        )
        self.grid_size: int = screen_config.get("grid_size", 10)
        self.max_screenshots: int = screen_config.get("max_screenshots", 50)
        self.multi_monitor: bool = screen_config.get("multi_monitor", False)

        # Create screenshot directory
        Path(self.screenshot_dir).mkdir(parents=True, exist_ok=True)
        logger.info("ScreenCapture initialized. Dir: %s", self.screenshot_dir)

    # ------------------------------------------------------------------
    # Capture Methods
    # ------------------------------------------------------------------

    def capture_primary(self) -> str:
        """Capture the primary monitor.

        Returns:
            File path to the saved screenshot.
        """
        try:
            with mss() as sct:
                # Monitor 1 is the primary display (0 is "all monitors")
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)

                filename = self._generate_filename("primary")
                filepath = os.path.join(self.screenshot_dir, filename)

                img = Image.frombytes(
                    "RGB",
                    screenshot.size,
                    screenshot.bgra,
                    "raw",
                    "BGRX",
                )
                img.save(filepath, "PNG")

                self.cleanup_old_screenshots()
                logger.info("Captured primary monitor → %s", filepath)
                return filepath

        except Exception as exc:
            logger.error("Failed to capture primary monitor: %s", exc)
            return ""

    def capture_to_bytes(self) -> bytes:
        """Capture primary monitor and return PNG bytes (never writes to disk).

        Returns:
            PNG image data as bytes.
        """
        try:
            with mss() as sct:
                monitor = sct.monitors[1]
                shot = sct.grab(monitor)
                img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                buf = BytesIO()
                img.save(buf, format="PNG", optimize=True)
                return buf.getvalue()
        except Exception as exc:
            logger.error("Failed to capture to bytes: %s", exc)
            return b""

    def capture_to_base64(self) -> str:
        """Capture and return base64 string ready for Ollama vision calls.

        Returns:
            Base64-encoded PNG image string.
        """
        try:
            return base64.b64encode(self.capture_to_bytes()).decode()
        except Exception as exc:
            logger.error("Failed to capture to base64: %s", exc)
            return ""

    def capture_all_monitors(self) -> List[str]:
        """Capture all connected monitors.

        Returns:
            List of file paths to saved screenshots.
        """
        paths: List[str] = []
        try:
            with mss() as sct:
                # Skip monitor[0] (virtual screen combining all)
                for i, monitor in enumerate(sct.monitors[1:], start=1):
                    screenshot = sct.grab(monitor)
                    filename = self._generate_filename(f"monitor_{i}")
                    filepath = os.path.join(self.screenshot_dir, filename)

                    img = Image.frombytes(
                        "RGB",
                        screenshot.size,
                        screenshot.bgra,
                        "raw",
                        "BGRX",
                    )
                    img.save(filepath, "PNG")
                    paths.append(filepath)

                logger.info("Captured %d monitors.", len(paths))

        except Exception as exc:
            logger.error("Failed to capture all monitors: %s", exc)

        self.cleanup_old_screenshots()
        return paths

    def capture_active_window(self) -> str:
        """Capture the currently focused/active window.

        Falls back to primary monitor capture on failure.

        Returns:
            File path to the saved screenshot.
        """
        try:
            import sys

            if sys.platform == "win32":
                return self._capture_active_window_windows()
            else:
                # Fallback: capture primary monitor
                logger.info(
                    "Active window capture not supported on this OS. "
                    "Falling back to primary monitor."
                )
                return self.capture_primary()

        except Exception as exc:
            logger.warning(
                "Active window capture failed: %s. "
                "Falling back to primary monitor.",
                exc,
            )
            return self.capture_primary()

    def _capture_active_window_windows(self) -> str:
        """Capture active window on Windows using win32 APIs."""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            # Get the foreground window handle
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return self.capture_primary()

            # Get window rectangle
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            left = rect.left
            top = rect.top
            width = rect.right - rect.left
            height = rect.bottom - rect.top

            if width <= 0 or height <= 0:
                return self.capture_primary()

            region = {
                "left": left,
                "top": top,
                "width": width,
                "height": height,
            }

            with mss() as sct:
                screenshot = sct.grab(region)
                filename = self._generate_filename("active_window")
                filepath = os.path.join(self.screenshot_dir, filename)

                img = Image.frombytes(
                    "RGB",
                    screenshot.size,
                    screenshot.bgra,
                    "raw",
                    "BGRX",
                )
                img.save(filepath, "PNG")

                logger.info("Captured active window → %s", filepath)
                return filepath

        except Exception as exc:
            logger.warning("Win32 active window capture failed: %s", exc)
            return self.capture_primary()

    # ------------------------------------------------------------------
    # Coordinate Grid
    # ------------------------------------------------------------------

    def add_coordinate_grid(
        self,
        image_path: str,
        grid_size: Optional[int] = None,
    ) -> Tuple[str, Dict[str, Tuple[int, int]]]:
        """Overlay a labelled coordinate grid on an image.

        The grid divides the screen into cells labelled A1, B2, etc.
        This helps the vision model reference precise locations.

        Args:
            image_path: Path to the source image.
            grid_size: Number of grid divisions per axis (default from config).

        Returns:
            Tuple of (annotated_image_path, coordinate_map).
            coordinate_map maps labels like "A1" → (x_center, y_center).
        """
        if grid_size is None:
            grid_size = self.grid_size

        try:
            img = cv2.imread(image_path)
            if img is None:
                logger.error("Cannot read image: %s", image_path)
                return image_path, {}

            h, w = img.shape[:2]
            cell_w = w / grid_size
            cell_h = h / grid_size

            coordinate_map: Dict[str, Tuple[int, int]] = {}
            row_labels = list(string.ascii_uppercase[:grid_size])
            col_labels = [str(i + 1) for i in range(grid_size)]

            # Draw grid lines
            for i in range(1, grid_size):
                x = int(i * cell_w)
                y = int(i * cell_h)
                cv2.line(img, (x, 0), (x, h), (0, 255, 0), 1)
                cv2.line(img, (0, y), (w, y), (0, 255, 0), 1)

            # Label cells
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = max(0.3, min(w, h) / 2000)
            thickness = max(1, int(min(w, h) / 1000))

            for ri, row_label in enumerate(row_labels):
                for ci, col_label in enumerate(col_labels):
                    label = f"{row_label}{col_label}"
                    cx = int((ci + 0.5) * cell_w)
                    cy = int((ri + 0.5) * cell_h)
                    coordinate_map[label] = (cx, cy)

                    # Draw label with background
                    text_size = cv2.getTextSize(
                        label, font, font_scale, thickness
                    )[0]
                    tx = cx - text_size[0] // 2
                    ty = cy + text_size[1] // 2

                    cv2.rectangle(
                        img,
                        (tx - 2, ty - text_size[1] - 2),
                        (tx + text_size[0] + 2, ty + 2),
                        (0, 0, 0),
                        -1,
                    )
                    cv2.putText(
                        img,
                        label,
                        (tx, ty),
                        font,
                        font_scale,
                        (0, 255, 0),
                        thickness,
                    )

            # Save annotated image
            base, ext = os.path.splitext(image_path)
            annotated_path = f"{base}_grid{ext}"
            cv2.imwrite(annotated_path, img)

            logger.info(
                "Grid overlay saved → %s (%d cells)",
                annotated_path,
                len(coordinate_map),
            )
            return annotated_path, coordinate_map

        except Exception as exc:
            logger.error("Failed to add coordinate grid: %s", exc)
            return image_path, {}

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def get_screen_resolution(self) -> Tuple[int, int]:
        """Return the resolution of the primary monitor.

        Returns:
            Tuple of (width, height).
        """
        try:
            with mss() as sct:
                monitor = sct.monitors[1]
                return monitor["width"], monitor["height"]
        except Exception as exc:
            logger.error("Failed to get screen resolution: %s", exc)
            return 1920, 1080  # Sensible default

    def cleanup_old_screenshots(self, keep_last: Optional[int] = None) -> None:
        """Delete old screenshots, keeping only the most recent N.

        Args:
            keep_last: Number of screenshots to keep (default from config).
        """
        if keep_last is None:
            keep_last = self.max_screenshots

        try:
            screenshot_dir = Path(self.screenshot_dir)
            files = sorted(
                screenshot_dir.glob("*.png"),
                key=lambda f: f.stat().st_mtime,
            )

            if len(files) > keep_last:
                to_delete = files[: len(files) - keep_last]
                for f in to_delete:
                    f.unlink()
                logger.info(
                    "Cleaned up %d old screenshots.", len(to_delete)
                )

        except Exception as exc:
            logger.warning("Screenshot cleanup error: %s", exc)

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _generate_filename(self, prefix: str = "screenshot") -> str:
        """Generate a unique filename with timestamp.

        Args:
            prefix: Filename prefix.

        Returns:
            Filename string (e.g. 'primary_20260318_064500_123.png').
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        return f"{prefix}_{ts}.png"
