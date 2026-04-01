"""
Continuous Screen Watching System.

Monitors screen changes and triggers reactions:
- Error popup appears → Auto-close
- Download finishes → Open file
- Login page appears → Enter credentials
- Task completes → Notify user

Uses image comparison and OCR to detect changes.
"""

import threading
import time
import logging
from typing import Callable, Optional, Dict, List, Any
from enum import Enum
from dataclasses import dataclass
import json

import numpy as np
import cv2

logger = logging.getLogger(__name__)


class ScreenEvent(Enum):
    """Types of screen changes detected."""
    CHANGE_DETECTED = "change"
    ERROR_POPUP = "error"
    SUCCESS_NOTIFICATION = "success"
    LOADING_INDICATOR = "loading"
    TEXT_RECOGNIZED = "text"
    ELEMENT_HIGHLIGHTED = "element"
    CUSTOM_PATTERN = "pattern"


@dataclass
class ScreenObservation:
    """Observation of screen state change."""
    event_type: ScreenEvent
    description: str
    changed_regions: List[tuple] = None  # [(x, y, w, h), ...]
    confidence: float = 0.0
    timestamp: float = None
    screenshot_path: Optional[str] = None


class ScreenWatcher:
    """Monitor screen for changes and react."""
    
    # Adaptive interval tuning
    QUIET_THRESHOLD = 10   # Seconds of no change before slowing down
    MAX_INTERVAL = 3.0     # Maximum seconds between checks in quiet mode
    
    def __init__(self, check_interval: float = 1.0, similarity_threshold: float = 0.85):
        """
        Initialize screen watcher.
        
        Args:
            check_interval: Seconds between checks
            similarity_threshold: Threshold for "changed" (0.0-1.0)
        """
        self.check_interval = check_interval
        self.similarity_threshold = similarity_threshold
        self.running = False
        self.watch_thread = None
        
        # Callbacks for different events
        self.callbacks: Dict[ScreenEvent, List[Callable]] = {
            event: [] for event in ScreenEvent
        }
        
        # Pattern matchers for automations
        self.patterns: Dict[str, Dict[str, Any]] = {}
        
        # State tracking
        self.last_screenshot = None
        self.last_change_time = None
        self.consecutive_unchanges = 0
        self.quiet_seconds = 0.0
    
    def start(self):
        """Start watching screen."""
        if self.running:
            return
        
        self.running = True
        self.watch_thread = threading.Thread(
            target=self._watch_loop,
            daemon=True,
            name="ScreenWatcher"
        )
        self.watch_thread.start()
        logger.info("[ScreenWatcher] Started")
    
    def stop(self):
        """Stop watching screen."""
        self.running = False
        if self.watch_thread:
            self.watch_thread.join(timeout=5)
        logger.info("[ScreenWatcher] Stopped")
    
    def _watch_loop(self):
        """Main watching loop with adaptive interval and downscaled comparison."""
        quiet_seconds = 0.0
        
        while self.running:
            try:
                # Capture at 25% resolution for fast diff
                current = self._capture_downscaled()
                
                if current is None or current.size == 0:
                    time.sleep(self.check_interval)
                    continue
                
                # First capture - establish baseline
                if self.last_screenshot is None:
                    self.last_screenshot = current
                    time.sleep(self.check_interval)
                    continue
                
                # Fast comparison on downscaled images
                changed = self._has_changed(current)
                
                if changed:
                    quiet_seconds = 0.0
                    self._fire_event(ScreenEvent.CHANGE_DETECTED, ScreenObservation(
                        event_type=ScreenEvent.CHANGE_DETECTED,
                        description="Screen changed",
                        confidence=1.0
                    ))
                    self._detect_patterns(current)
                    logger.debug("[ScreenWatcher] Screen change detected")
                else:
                    quiet_seconds += self.check_interval
                
                # Adaptive sleep: slow down during quiet periods
                interval = min(
                    self.check_interval * (1 + quiet_seconds / self.QUIET_THRESHOLD),
                    self.MAX_INTERVAL,
                )
                time.sleep(interval)
                
            except Exception as e:
                logger.error("[ScreenWatcher] Watch loop error: %s", e)
                time.sleep(self.check_interval)
    
    def _capture_downscaled(self) -> Optional[np.ndarray]:
        """Capture at 25% size for fast diff comparison.
        
        Returns:
            Numpy array of downscaled screenshot (or None on error).
        """
        try:
            from mss import mss
            
            with mss() as sct:
                shot = sct.grab(sct.monitors[1])
                img = np.array(shot)
                h, w = img.shape[:2]
                # Resize to 25% for faster comparison
                downscaled = cv2.resize(img, (w // 4, h // 4), interpolation=cv2.INTER_AREA)
                return downscaled
        except Exception as e:
            logger.error("[ScreenWatcher] Failed to capture downscaled image: %s", e)
            return None
    
    def _has_changed(self, current: np.ndarray) -> bool:
        """Check if screen has changed using downscaled image comparison.
        
        Args:
            current: Current downscaled screenshot.
            
        Returns:
            True if screen has changed beyond threshold.
        """
        if self.last_screenshot is None or self.last_screenshot.size == 0:
            self.last_screenshot = current
            return False
        
        try:
            # Compute mean absolute difference
            diff = cv2.absdiff(self.last_screenshot, current)
            mean_diff = diff.mean()
            
            # If mean difference exceeds threshold, consider it changed
            changed = mean_diff > (1.0 - self.similarity_threshold) * 255
            
            if changed:
                self.last_screenshot = current.copy()
            
            return changed
        except Exception as e:
            logger.error("[ScreenWatcher] Comparison error: %s", e)
            return False
    
    def _detect_patterns(self, current: np.ndarray):
        """Detect known patterns from screenshot analysis.
        
        Args:
            current: Current downscaled screenshot array.
        """
        # This is where we'd use OCR, UI detection, etc.
        # For now, basic implementation for detecting common patterns
        
        try:
            # Placeholder for pattern detection (OCR, UI detection, etc.)
            # Future: Use pytesseract for OCR, or pywinauto for UI elements
            
            # Example: Could detect error dialogs, loading indicators, etc.
            # For now, just log that a pattern detection was attempted
            logger.debug("[ScreenWatcher] Pattern detection completed")
            
        except Exception as e:
            logger.error("[ScreenWatcher] Pattern detection error: %s", e)
            if self._has_error_indicators(comparison):
                self._fire_event(ScreenEvent.ERROR_POPUP, ScreenObservation(
                    event_type=ScreenEvent.ERROR_POPUP,
                    description="Error dialog detected",
                    confidence=0.8
                ))
            
            # Example: Detect success notification
            if self._has_success_indicators(comparison):
                self._fire_event(ScreenEvent.SUCCESS_NOTIFICATION, ScreenObservation(
                    event_type=ScreenEvent.SUCCESS_NOTIFICATION,
                    description="Success notification shown",
                    confidence=0.8
                ))
        
        except Exception as e:
            logger.debug(f"[ScreenWatcher] Pattern detection error: {e}")
    
    def _has_error_indicators(self, comparison) -> bool:
        """Check if error dialog likely present."""
        # Could check for red colors, "error" text, X buttons
        # For now, return False
        return False
    
    def _has_success_indicators(self, comparison) -> bool:
        """Check if success notification likely present."""
        # Could check for green colors, checkmarks, success text
        return False
    
    def register_callback(self, event: ScreenEvent, callback: Callable):
        """Register callback for screen event."""
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)
        logger.debug(f"[ScreenWatcher] Registered callback for {event.value}")
    
    def unregister_callback(self, event: ScreenEvent, callback: Callable):
        """Unregister callback."""
        if event in self.callbacks:
            self.callbacks[event] = [c for c in self.callbacks[event] if c != callback]
    
    def _fire_event(self, event: ScreenEvent, observation: ScreenObservation):
        """Fire event to all registered callbacks."""
        observation.timestamp = time.time()
        
        if event in self.callbacks:
            for callback in self.callbacks[event]:
                try:
                    callback(observation)
                except Exception as e:
                    logger.error(f"[ScreenWatcher] Callback error: {e}")
    
    def register_pattern(self, 
                        pattern_name: str,
                        condition: Callable[[ScreenObservation], bool],
                        action: Callable[[ScreenObservation], None],
                        enabled: bool = True):
        """
        Register custom pattern.
        
        Args:
            pattern_name: Unique pattern ID
            condition: Function to check if pattern matches
            action: Function to run if pattern matches
            enabled: Whether pattern is active
        """
        self.patterns[pattern_name] = {
            "condition": condition,
            "action": action,
            "enabled": enabled,
            "match_count": 0
        }
        logger.debug(f"[ScreenWatcher] Registered pattern: {pattern_name}")
    
    def get_watch_stats(self) -> Dict[str, Any]:
        """Get watching statistics."""
        return {
            "running": self.running,
            "last_change": self.last_change_time,
            "consecutive_unchanges": self.consecutive_unchanges,
            "callbacks_registered": sum(len(cbs) for cbs in self.callbacks.values()),
            "patterns_registered": len(self.patterns)
        }


class AutomationReactor:
    """Automatic reactions to screen changes."""
    
    def __init__(self, watcher: ScreenWatcher):
        self.watcher = watcher
        self._setup_default_patterns()
    
    def _setup_default_patterns(self):
        """Setup common auto-reactions."""
        
        # Auto-close error dialogs (when user enables this)
        def error_handler(obs: ScreenObservation):
            logger.info("[AutoReact] Closing error dialog...")
            # Would use pyautogui/pywinauto to close
        
        self.watcher.register_callback(ScreenEvent.ERROR_POPUP, error_handler)
        
        # Notify user on success
        def success_handler(obs: ScreenObservation):
            logger.info("[AutoReact] Task completed!")
        
        self.watcher.register_callback(ScreenEvent.SUCCESS_NOTIFICATION, success_handler)
    
    def enable_auto_error_close(self, enabled: bool = True):
        """Auto-close error dialogs."""
        # This would be configured per-pattern
        pass
    
    def enable_auto_retry(self, max_retries: int = 3):
        """Automatically retry on failure."""
        pass
    
    def enable_auto_download_open(self, enabled: bool = True):
        """Auto-open downloaded files."""
        pass


# Global watcher instance
_watcher: Optional[ScreenWatcher] = None


def initialize_screen_watcher(check_interval: float = 1.0) -> ScreenWatcher:
    """Initialize global screen watcher."""
    global _watcher
    _watcher = ScreenWatcher(check_interval=check_interval)
    return _watcher


def get_screen_watcher() -> ScreenWatcher:
    """Get global screen watcher."""
    global _watcher
    if _watcher is None:
        _watcher = ScreenWatcher()
    return _watcher


def start_watching():
    """Start screen watching."""
    get_screen_watcher().start()


def stop_watching():
    """Stop screen watching."""
    get_screen_watcher().stop()


def register_watch_callback(event: ScreenEvent, callback: Callable):
    """Register callback for screen event."""
    get_screen_watcher().register_callback(event, callback)


def register_watch_pattern(
    pattern_name: str,
    condition: Callable,
    action: Callable
):
    """Register custom watch pattern."""
    get_screen_watcher().register_pattern(pattern_name, condition, action)
