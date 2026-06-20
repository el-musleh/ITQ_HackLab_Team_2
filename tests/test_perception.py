"""
Perception / Vision Subsystem Tests

Tests: Yellow tape detection, obstacle edge detection, frame processing.
Requires a working camera — run test_camera first.
"""
import cv2
import numpy as np
import time
from tests.test_results import log


TAPE_HSV_LOWER = np.array([15,  60,  60])
TAPE_HSV_UPPER = np.array([45, 255, 255])
CANNY_LOW  = 40
CANNY_HIGH = 120


def _get_frame(camera, source="jetbot"):
    """Helper to fetch one frame from either source."""
    if source == "jetbot":
        return camera.value.copy() if camera.value is not None else None
    else:
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        ret, frame = cap.read()
        cap.release()
        return frame if ret else None


def test_frame_available(camera, source="jetbot"):
    """Confirm we can grab a frame for perception tests."""
    frame = _get_frame(camera, source)
    if frame is not None:
        log("Frame available", True, f"shape {frame.shape}")
        return True
    else:
        log("Frame available", False, "camera returned None")
        return False


def test_yellow_detection(camera, source="jetbot"):
    """Test yellow tape detection on current frame."""
    frame = _get_frame(camera, source)
    if frame is None:
        log("Yellow detection", False, "no frame")
        return

    try:
        h = frame.shape[0]
        roi_start = int(h * 0.70)
        roi = frame[roi_start:, :]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, TAPE_HSV_LOWER, TAPE_HSV_UPPER)
        yellow_pixels = int(np.sum(mask > 0))

        # Report whether yellow is seen (non-zero is informative)
        status = "yellow detected" if yellow_pixels > 0 else "no yellow in frame"
        log("Yellow detection", True, f"{yellow_pixels} pixels — {status}")
    except Exception as e:
        log("Yellow detection", False, str(e))


def test_obstacle_detection(camera, source="jetbot"):
    """Test edge-based obstacle detection on current frame."""
    frame = _get_frame(camera, source)
    if frame is None:
        log("Obstacle detection", False, "no frame")
        return

    try:
        h, w = frame.shape[:2]
        roi_top = int(h * 0.15)
        roi_bot = int(h * 0.65)
        roi = frame[roi_top:roi_bot, :]

        # Mask yellow pixels
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        yellow_mask = cv2.inRange(hsv, TAPE_HSV_LOWER, TAPE_HSV_UPPER)

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray[yellow_mask > 0] = 0

        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, CANNY_LOW, CANNY_HIGH)
        edge_pixels = int(np.sum(edges > 0))

        log("Obstacle detection", True, f"{edge_pixels} edge pixels in front ROI")
    except Exception as e:
        log("Obstacle detection", False, str(e))


def test_frame_rate(camera, source="jetbot", samples=10):
    """Measure approximate frame capture rate."""
    try:
        t0 = time.time()
        for _ in range(samples):
            _ = _get_frame(camera, source)
        dt = time.time() - t0
        fps = samples / dt if dt > 0 else 0
        log("Frame rate", True, f"~{fps:.1f} fps over {samples} frames")
    except Exception as e:
        log("Frame rate", False, str(e))


def run_all(camera=None, source="jetbot"):
    """Run all perception tests. Pass camera object from test_camera."""
    print("--- Perception Tests ---")
    if camera is None and source == "jetbot":
        print("No camera object provided. Trying OpenCV fallback...")
        source = "fallback"

    if not test_frame_available(camera, source):
        print("CRITICAL: Cannot capture frames. Skipping perception tests.")
        return

    test_yellow_detection(camera, source)
    test_obstacle_detection(camera, source)
    test_frame_rate(camera, source)
    print()


if __name__ == "__main__":
    run_all()
