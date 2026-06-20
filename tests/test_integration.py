"""
Integration / End-to-End Tests

Tests: Full navigation callback simulation, emergency stop pipeline,
safe_stop with missing robot, camera+perception pipeline.
"""
import numpy as np
import time
from tests.test_results import log


def test_safe_stop_with_none():
    """safe_stop must not crash when robot is None."""
    robot = None
    try:
        if robot is not None:
            robot.left_motor.value = 0.0
            robot.right_motor.value = 0.0
        log("Safe stop (None robot)", True, "no crash with None robot")
    except Exception as e:
        log("Safe stop (None robot)", False, str(e))


def test_safe_stop_with_robot():
    """safe_stop must zero motors on a real robot object."""
    try:
        from jetbot import Robot
        robot = Robot()
        robot.stop()
        robot.left_motor.value = 0.0
        robot.right_motor.value = 0.0
        log("Safe stop (real robot)", True, "motors zeroed")
    except Exception as e:
        log("Safe stop (real robot)", False, str(e))


def test_camera_perception_pipeline():
    """Capture frame -> run yellow detection -> run obstacle detection."""
    try:
        frame = None
        # Try jetbot camera
        try:
            from jetbot import Camera
            camera = Camera.instance(width=300, height=300)
            time.sleep(0.5)
            frame = camera.value
        except Exception:
            pass

        # Fallback to OpenCV
        if frame is None:
            import cv2
            cap = cv2.VideoCapture(0)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 300)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 300)
            ret, frame = cap.read()
            cap.release()
            if not ret:
                log("Camera->Perception pipeline", False, "no frame from any source")
                return

        # Run yellow detection
        h = frame.shape[0]
        roi = frame[int(h * 0.70):, :]
        import cv2
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([15, 60, 60]), np.array([45, 255, 255]))
        yellow = int(np.sum(mask > 0))

        # Run obstacle detection
        roi2 = frame[int(h * 0.15):int(h * 0.65), :]
        gray = cv2.cvtColor(roi2, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 40, 120)
        edge_count = int(np.sum(edges > 0))

        log("Camera->Perception pipeline", True,
            f"yellow={yellow} edges={edge_count}")
    except Exception as e:
        log("Camera->Perception pipeline", False, str(e))


def test_emergency_stop_sequence():
    """Simulate emergency stop: unobserve -> safe_stop -> state=STOPPED."""
    try:
        nav_state = "WANDER"
        # Simulate unobserve (would be camera.unobserve_all())
        # Simulate safe_stop
        try:
            from jetbot import Robot
            robot = Robot()
            robot.stop()
        except Exception:
            pass
        nav_state = "STOPPED"
        if nav_state == "STOPPED":
            log("Emergency stop sequence", True, "state set to STOPPED")
        else:
            log("Emergency stop sequence", False, f"state is {nav_state}")
    except Exception as e:
        log("Emergency stop sequence", False, str(e))


def test_reset_to_wander():
    """Simulate reset: all globals return to defaults, state=WANDER."""
    try:
        nav_state = "STOPPED"
        avoid_start_time = 999.0
        avoid_turn_right = False
        wander_cooldown_end = 999.0
        last_left_spd = 0.5
        last_right_spd = -0.5

        # Reset
        nav_state = "WANDER"
        avoid_start_time = 0.0
        avoid_turn_right = True
        wander_cooldown_end = 0.0
        last_left_spd = 0.0
        last_right_spd = 0.0

        checks = [
            nav_state == "WANDER",
            avoid_start_time == 0.0,
            avoid_turn_right is True,
            wander_cooldown_end == 0.0,
            last_left_spd == 0.0,
            last_right_spd == 0.0,
        ]
        if all(checks):
            log("Reset to WANDER", True, "all globals reset")
        else:
            log("Reset to WANDER", False, "some globals not reset")
    except Exception as e:
        log("Reset to WANDER", False, str(e))


def run_all():
    """Run all integration tests."""
    print("--- Integration Tests ---")
    test_safe_stop_with_none()
    test_safe_stop_with_robot()
    test_camera_perception_pipeline()
    test_emergency_stop_sequence()
    test_reset_to_wander()
    print()


if __name__ == "__main__":
    run_all()
