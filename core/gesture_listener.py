"""
GestureListener — Hand Gesture Recognition for Scroll Control

Detects hand gestures using webcam and mediapipe:
- 5 fingers raised: scroll up
- 0 fingers (fist): scroll down

Runs in a separate multiprocessing daemon process.
ZERO external APIs - uses local mediapipe model.
"""

import logging
import multiprocessing
import time
from typing import Optional

import pyautogui

logger = logging.getLogger(__name__)


class GestureListener:
    """Hand gesture recognition for desktop control.

    Monitors webcam for hand gestures and triggers scroll actions.
    Runs in a separate process to avoid blocking main application.
    """

    def __init__(self, enabled: bool = True) -> None:
        """Initialize GestureListener.

        Args:
            enabled: Whether gestures are enabled.
        """
        self.enabled = enabled
        self.process: Optional[multiprocessing.Process] = None
        logger.info("GestureListener initialized (enabled=%s).", enabled)

    def start(self) -> None:
        """Start the gesture recognition in a daemon process."""
        if not self.enabled:
            logger.info("Gesture recognition disabled.")
            return

        if self.process is not None and self.process.is_alive():
            logger.warning("Gesture listener is already running.")
            return

        self.process = multiprocessing.Process(
            target=_gesture_watch_process,
            daemon=True,
        )
        self.process.start()
        logger.info("Gesture listener started in daemon process.")

    def stop(self) -> None:
        """Stop the gesture recognition process."""
        if self.process is not None and self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=2)
            logger.info("Gesture listener stopped.")


def _gesture_watch_process() -> None:
    """Main gesture watching loop (runs in separate process).

    Monitors webcam for hand gestures and triggers scroll actions.
    """
    try:
        import cv2
        import mediapipe as mp
    except ImportError:
        logger.error(
            "mediapipe or cv2 not installed. "
            "Install with: pip install mediapipe opencv-python"
        )
        return

    logger.info("Gesture watching process started.")
    print("[GESTURE] Hand gesture recognition active. Raise hand to control scroll.")

    # Initialize mediapipe
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5,
    )

    mp_drawing = mp.solutions.drawing_utils

    # Open webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Failed to open webcam (camera 0).")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

    last_gesture = None
    gesture_cooldown = 0

    try:
        while True:
            success, frame = cap.read()
            if not success:
                break

            # Flip and convert frame
            frame = cv2.flip(frame, 1)
            h, w, c = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Detect hands
            results = hands.process(rgb_frame)

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    # Count raised fingers
                    fingers_raised = _count_raised_fingers(hand_landmarks.landmark)

                    if gesture_cooldown > 0:
                        gesture_cooldown -= 1
                    else:
                        if fingers_raised == 5 and last_gesture != "scroll_up":
                            # All fingers raised - scroll up
                            logger.debug("Gesture: scroll up (5 fingers)")
                            pyautogui.scroll(3)
                            last_gesture = "scroll_up"
                            gesture_cooldown = 10  # Cooldown to prevent repeat triggers

                        elif fingers_raised == 0 and last_gesture != "scroll_down":
                            # Fist (0 fingers) - scroll down
                            logger.debug("Gesture: scroll down (fist)")
                            pyautogui.scroll(-3)
                            last_gesture = "scroll_down"
                            gesture_cooldown = 10

                    # Draw hand landmarks (for debugging)
                    mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            else:
                last_gesture = None

            # Show frame (small preview)
            cv2.imshow("Gesture Listener", frame)
            if cv2.waitKey(5) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        logger.info("Gesture watching process interrupted.")
    except Exception as exc:
        logger.error("Error in gesture watching process: %s", exc)
    finally:
        cap.release()
        cv2.destroyAllWindows()
        hands.close()
        logger.info("Gesture watching process ended.")


def _count_raised_fingers(landmarks: list) -> int:
    """Count the number of raised fingers.

    Args:
        landmarks: List of hand landmark positions from mediapipe.

    Returns:
        Number of raised fingers (0-5).
    """
    if len(landmarks) < 21:
        return 0

    # Finger tip indices (relative to hand landmarks)
    # 8: index, 12: middle, 16: ring, 20: pinky
    # 4: thumb
    # Compare y-coordinates to detect raised fingers

    raised = 0

    # Thumb (special case - check x coordinate)
    if landmarks[4].x < landmarks[3].x:
        raised += 1

    # Other fingers - check if tip (index 8, 12, 16, 20) is above pip joint (6, 10, 14, 18)
    finger_tips = [8, 12, 16, 20]
    finger_pips = [6, 10, 14, 18]

    for tip_idx, pip_idx in zip(finger_tips, finger_pips):
        if landmarks[tip_idx].y < landmarks[pip_idx].y:
            raised += 1

    return raised


def start_gesture_watch(enabled: bool = True) -> GestureListener:
    """Convenience function to start gesture recognition.

    Args:
        enabled: Whether to enable gesture recognition.

    Returns:
        GestureListener instance (already started if enabled).
    """
    listener = GestureListener(enabled=enabled)
    if enabled:
        listener.start()
    return listener
