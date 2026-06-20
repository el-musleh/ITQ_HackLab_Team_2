"""
Camera Subsystem Tests

Tests: init, capture, resolution, frame format, fallback support.
Run standalone or via test_runner.
"""
import cv2
import time

from tests.test_results import log


def test_camera_init(width=320, height=240):
    """Try to create a camera instance."""
    camera = None
    try:
        from jetbot import Camera
        camera = Camera.instance(width=width, height=height)
        log("Camera init (jetbot)", True, f"resolution {width}x{height}")
        return camera, "jetbot"
    except Exception as e:
        log("Camera init (jetbot)", False, str(e))

    # Fallback: OpenCV direct
    try:
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            log("Camera init (fallback)", True, f"OpenCV fallback {width}x{height}")
            return None, "fallback_ok"
        else:
            log("Camera init (fallback)", False, "No frame from /dev/video0")
            return None, None
    except Exception as e2:
        log("Camera init (fallback)", False, str(e2))
        return None, None


def test_camera_frame(camera, source="jetbot"):
    """Verify we can read at least one valid frame."""
    try:
        if source == "jetbot":
            frame = camera.value
            if frame is None:
                log("Camera frame read", False, "camera.value is None")
                return False
        else:
            cap = cv2.VideoCapture(0)
            ret, frame = cap.read()
            cap.release()
            if not ret:
                log("Camera frame read", False, "cv2.VideoCapture.read() failed")
                return False

        h, w = frame.shape[:2]
        log("Camera frame read", True, f"shape {frame.shape}, dtype {frame.dtype}")

        # Verify BGR format (3 channels)
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            log("Camera frame format", True, "BGR 3-channel")
        else:
            log("Camera frame format", False, f"unexpected shape {frame.shape}")

        return True
    except Exception as e:
        log("Camera frame read", False, str(e))
        return False


def test_camera_resolution(camera, expected_w, expected_h, source="jetbot"):
    """Confirm frame dimensions match configuration."""
    try:
        if source == "jetbot":
            frame = camera.value
        else:
            cap = cv2.VideoCapture(0)
            ret, frame = cap.read()
            cap.release()
            if not ret:
                log("Camera resolution", False, "could not read frame")
                return

        h, w = frame.shape[:2]
        if w == expected_w and h == expected_h:
            log("Camera resolution", True, f"{w}x{h} matches config")
        else:
            log("Camera resolution", False,
                f"got {w}x{h}, expected {expected_w}x{expected_h}")
    except Exception as e:
        log("Camera resolution", False, str(e))


def run_all(width=320, height=240):
    """Run all camera tests and return (camera_obj, source_type or None)."""
    print("--- Camera Tests ---")
    camera, source = test_camera_init(width, height)
    if camera is None and source is None:
        print("CRITICAL: Camera unavailable. Skipping remaining camera tests.")
        return None, None

    test_camera_frame(camera, source)
    test_camera_resolution(camera, width, height, source)
    print()
    return camera, source


if __name__ == "__main__":
    run_all()
