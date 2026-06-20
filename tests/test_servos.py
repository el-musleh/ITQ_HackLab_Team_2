"""
Servo / Arm Subsystem Tests

Tests: TTLServo import, arm joints movement, camera pan/tilt.
WARNING: Arm will move during tests. Keep clear of fragile objects.
"""
import time
from tests.test_results import log


def test_servo_library():
    """Verify TTLServo library imports and port opens."""
    try:
        from SCSCtrl import TTLServo
        log("Servo library", True, "SCSCtrl.TTLServo imported")
        return TTLServo
    except Exception as e:
        log("Servo library", False, str(e))
        return None


def test_camera_pan_tilt(TTLServo, pan=0, tilt=15):
    """Move camera pan and tilt servos to known positions."""
    try:
        TTLServo.servoAngleCtrl(1, pan, 1, 100)   # pan
        time.sleep(0.15)
        TTLServo.servoAngleCtrl(5, tilt, 1, 100)  # tilt
        time.sleep(0.50)
        log("Camera pan/tilt", True, f"pan={pan} tilt={tilt}")
    except Exception as e:
        log("Camera pan/tilt", False, str(e))


def test_arm_base(TTLServo, angle=0):
    """Move arm base servo."""
    try:
        TTLServo.servoAngleCtrl(2, angle, 1, 100)
        time.sleep(0.30)
        log("Arm base servo", True, f"moved to {angle}")
    except Exception as e:
        log("Arm base servo", False, str(e))


def test_arm_shoulder(TTLServo, angle=0):
    """Move arm shoulder servo."""
    try:
        TTLServo.servoAngleCtrl(3, angle, 1, 100)
        time.sleep(0.30)
        log("Arm shoulder servo", True, f"moved to {angle}")
    except Exception as e:
        log("Arm shoulder servo", False, str(e))


def test_arm_elbow(TTLServo, angle=0):
    """Move arm elbow servo."""
    try:
        TTLServo.servoAngleCtrl(4, angle, 1, 100)
        time.sleep(0.30)
        log("Arm elbow servo", True, f"moved to {angle}")
    except Exception as e:
        log("Arm elbow servo", False, str(e))


def test_gripper(TTLServo, open_angle=0, close_angle=-30):
    """Open and close gripper."""
    try:
        TTLServo.servoAngleCtrl(6, open_angle, 1, 100)
        time.sleep(0.30)
        TTLServo.servoAngleCtrl(6, close_angle, 1, 100)
        time.sleep(0.30)
        log("Gripper servo", True, f"open={open_angle} close={close_angle}")
    except Exception as e:
        log("Gripper servo", False, str(e))


def test_servo_home(TTLServo):
    """Return all servos to a safe home position."""
    try:
        TTLServo.servoAngleCtrl(1, 0, 1, 100)   # pan
        time.sleep(0.1)
        TTLServo.servoAngleCtrl(5, 0, 1, 100)   # tilt
        time.sleep(0.1)
        TTLServo.servoAngleCtrl(2, 0, 1, 100)   # base
        time.sleep(0.1)
        TTLServo.servoAngleCtrl(3, 0, 1, 100)   # shoulder
        time.sleep(0.1)
        TTLServo.servoAngleCtrl(4, 0, 1, 100)   # elbow
        time.sleep(0.1)
        TTLServo.servoAngleCtrl(6, 0, 1, 100)   # gripper open
        time.sleep(0.3)
        log("Servo home", True, "all servos returned to 0")
    except Exception as e:
        log("Servo home", False, str(e))


def run_all():
    """Run all servo/arm tests."""
    print("--- Servo Tests ---")
    print("WARNING: Arm will move. Keep clear.")
    print()

    TTLServo = test_servo_library()
    if TTLServo is None:
        print("CRITICAL: Servo library unavailable. Skipping servo tests.")
        return None

    test_camera_pan_tilt(TTLServo, pan=0, tilt=15)
    test_arm_base(TTLServo, angle=10)
    test_arm_shoulder(TTLServo, angle=10)
    test_arm_elbow(TTLServo, angle=10)
    test_gripper(TTLServo, open_angle=0, close_angle=-20)
    test_servo_home(TTLServo)
    print()
    return TTLServo


if __name__ == "__main__":
    run_all()
