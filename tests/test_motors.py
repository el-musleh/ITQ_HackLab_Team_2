"""
Motor / Drive Subsystem Tests

Tests: Robot init, motor directions, stop, speed limits.
WARNING: Robot will move briefly during tests. Place on blocks or keep clear area.
"""
import time
from tests.test_results import log


def test_robot_init():
    """Initialize Robot object and verify motor attributes exist."""
    try:
        from jetbot import Robot
        robot = Robot()
        robot.stop()
        # Verify both motors are accessible
        _ = robot.left_motor.value
        _ = robot.right_motor.value
        log("Robot init", True, "Robot() created, motors accessible")
        return robot
    except Exception as e:
        log("Robot init", False, str(e))
        return None


def test_motor_stop(robot):
    """Verify motors can be zeroed."""
    try:
        robot.stop()
        l = robot.left_motor.value
        r = robot.right_motor.value
        if l == 0.0 and r == 0.0:
            log("Motor stop", True, f"L={l} R={r}")
        else:
            log("Motor stop", False, f"L={l} R={r} (expected 0,0)")
    except Exception as e:
        log("Motor stop", False, str(e))


def test_motor_forward(robot, duration=0.5, speed=0.15):
    """Brief forward motion test — robot will move."""
    try:
        robot.left_motor.value  = speed
        robot.right_motor.value = speed
        time.sleep(duration)
        robot.stop()
        log("Motor forward", True, f"drove forward {duration}s @ speed={speed}")
    except Exception as e:
        robot.stop()
        log("Motor forward", False, str(e))


def test_motor_reverse(robot, duration=0.5, speed=0.15):
    """Brief reverse motion test — robot will move."""
    try:
        robot.left_motor.value  = -speed
        robot.right_motor.value = -speed
        time.sleep(duration)
        robot.stop()
        log("Motor reverse", True, f"drove reverse {duration}s @ speed={speed}")
    except Exception as e:
        robot.stop()
        log("Motor reverse", False, str(e))


def test_motor_turn_left(robot, duration=0.5, speed=0.2):
    """Brief left turn test — robot will spin."""
    try:
        robot.left_motor.value  = -speed
        robot.right_motor.value =  speed
        time.sleep(duration)
        robot.stop()
        log("Motor turn left", True, f"spun left {duration}s @ speed={speed}")
    except Exception as e:
        robot.stop()
        log("Motor turn left", False, str(e))


def test_motor_turn_right(robot, duration=0.5, speed=0.2):
    """Brief right turn test — robot will spin."""
    try:
        robot.left_motor.value  =  speed
        robot.right_motor.value = -speed
        time.sleep(duration)
        robot.stop()
        log("Motor turn right", True, f"spun right {duration}s @ speed={speed}")
    except Exception as e:
        robot.stop()
        log("Motor turn right", False, str(e))


def test_speed_clamp(robot, max_speed=0.25):
    """Verify motors accept and hold values within safe range."""
    try:
        robot.left_motor.value  = max_speed
        robot.right_motor.value = max_speed
        time.sleep(0.2)
        l = robot.left_motor.value
        r = robot.right_motor.value
        robot.stop()
        if abs(l - max_speed) < 0.01 and abs(r - max_speed) < 0.01:
            log("Speed clamp", True, f"max speed {max_speed} accepted")
        else:
            log("Speed clamp", False, f"L={l} R={r} (expected ~{max_speed})")
    except Exception as e:
        robot.stop()
        log("Speed clamp", False, str(e))


def run_all(duration=0.5, speed=0.15, max_speed=0.25):
    """
    Run all motor tests.
    
    Parameters
    ----------
    duration : float
        Seconds to drive in each direction test (default 0.5).
    speed : float
        Motor speed for direction tests (default 0.15).
    max_speed : float
        Speed for clamp test (default 0.25).
    """
    print("--- Motor Tests ---")
    print("WARNING: Robot will move. Keep clear or place on blocks.")
    print()

    robot = test_robot_init()
    if robot is None:
        print("CRITICAL: Robot init failed. Skipping motor tests.")
        return None

    time.sleep(0.5)
    test_motor_stop(robot)
    test_motor_forward(robot, duration, speed)
    time.sleep(0.3)
    test_motor_reverse(robot, duration, speed)
    time.sleep(0.3)
    test_motor_turn_left(robot, duration, speed)
    time.sleep(0.3)
    test_motor_turn_right(robot, duration, speed)
    time.sleep(0.3)
    test_speed_clamp(robot, max_speed)
    robot.stop()
    print()
    return robot


if __name__ == "__main__":
    run_all()
