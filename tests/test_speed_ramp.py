"""Unit tests for distance-based speed ramping (chassis) and trapezoidal
servo velocity profiling (arm)."""

import sys
import pytest
from unittest.mock import patch, MagicMock

# Stub out TTLServo before importing arm to avoid serial port init
_mock_ttl = MagicMock()
sys.modules.setdefault('src.SCSCtrl.TTLServo', _mock_ttl)
# Also patch the package-level import if needed
import src.SCSCtrl as _scs
_scs.TTLServo = _mock_ttl

from src.hardware.arm import ArmController


# ---------------------------------------------------------------------------
# Chassis: _distance_to_speed()
# ---------------------------------------------------------------------------

class TestDistanceToSpeed:
    """Test the linear distance-to-speed mapping on StateMachine.

    We instantiate a lightweight stub that has only the attributes used by
    _distance_to_speed() to avoid needing a full hardware setup.
    """

    def _make_stub(self, approach_speed=0.15, min_speed=0.05,
                   far=50.0, close=15.0):
        from src.control.state_machine import StateMachine
        # Create an uninitialised instance and inject just the attrs we need
        sm = StateMachine.__new__(StateMachine)
        sm.approach_speed = approach_speed
        sm.min_approach_speed = min_speed
        sm.far_distance_threshold = far
        sm.close_distance_threshold = close
        return sm

    def test_far_distance_returns_approach(self):
        sm = self._make_stub()
        assert sm._distance_to_speed(60.0) == pytest.approx(0.15)

    def test_far_distance_exact_threshold(self):
        sm = self._make_stub()
        assert sm._distance_to_speed(50.0) == pytest.approx(0.15)

    def test_close_distance_returns_min(self):
        sm = self._make_stub()
        assert sm._distance_to_speed(10.0) == pytest.approx(0.05)

    def test_close_distance_exact_threshold(self):
        sm = self._make_stub()
        assert sm._distance_to_speed(15.0) == pytest.approx(0.05)

    def test_midpoint_linear_interpolation(self):
        sm = self._make_stub()
        # midpoint between 15 and 50 → (15+50)/2 = 32.5
        speed = sm._distance_to_speed(32.5)
        expected = 0.05 + 0.5 * (0.15 - 0.05)
        assert speed == pytest.approx(expected)

    def test_monotonically_increasing(self):
        sm = self._make_stub()
        prev = sm._distance_to_speed(15.0)
        for d in range(16, 51):
            curr = sm._distance_to_speed(float(d))
            assert curr >= prev - 1e-9
            prev = curr

    def test_clamps_above_far(self):
        sm = self._make_stub()
        assert sm._distance_to_speed(999.0) == pytest.approx(0.15)

    def test_clamps_below_close(self):
        sm = self._make_stub()
        assert sm._distance_to_speed(0.0) == pytest.approx(0.05)

    def test_custom_thresholds(self):
        sm = self._make_stub(approach_speed=0.20, min_speed=0.02, far=100.0, close=30.0)
        assert sm._distance_to_speed(150.0) == pytest.approx(0.20)
        assert sm._distance_to_speed(20.0) == pytest.approx(0.02)
        # midpoint at 65
        mid = sm._distance_to_speed(65.0)
        expected = 0.02 + 0.5 * (0.20 - 0.02)
        assert mid == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Arm: move_to_pose_ramped() trapezoidal velocity profile
# ---------------------------------------------------------------------------

class TestMoveToPoseRamped:
    """Test that move_to_pose_ramped produces a trapezoidal speed profile."""

    def _make_arm(self):
        """Create an ArmController without hardware serial."""
        with patch('src.hardware.arm.TTLServo'):
            arm = ArmController()
        return arm

    def test_returns_true_on_success(self):
        arm = self._make_arm()
        with patch('src.hardware.arm.TTLServo.servoAngleCtrl') as mock_ctrl, \
             patch('time.sleep'):
            result = arm.move_to_pose_ramped([0, -40, -60, 0], num_steps=10)
        assert result is True

    def test_updates_current_pose(self):
        arm = self._make_arm()
        target = [10, 20, 30, 45]
        with patch('src.hardware.arm.TTLServo.servoAngleCtrl'), \
             patch('time.sleep'):
            arm.move_to_pose_ramped(target, num_steps=5)
        assert arm.current_pose == target

    def test_speed_profile_trapezoidal(self):
        """Verify speed increases, plateaus, then decreases."""
        arm = self._make_arm()
        speeds = []

        def capture_speed(servo_id, angle, debug, speed):
            speeds.append(speed)

        with patch('src.hardware.arm.TTLServo.servoAngleCtrl',
                   side_effect=capture_speed), \
             patch('time.sleep'):
            arm.move_to_pose_ramped([0, -40, -60, 0], num_steps=10,
                                    max_speed=150)

        # 4 servos × 10 steps = 40 calls; take every 4th (one per step)
        step_speeds = [speeds[i] for i in range(3, len(speeds), 4)]
        assert len(step_speeds) == 10

        # Phase 1 (steps 1-3): acceleration — speeds should increase
        assert step_speeds[0] < step_speeds[1] < step_speeds[2]

        # Phase 2 (steps 4-7): cruise — speeds should be at max
        for s in step_speeds[3:7]:
            assert s == 150

        # Phase 3 (steps 8-10): deceleration — speeds should decrease
        assert step_speeds[7] > step_speeds[8] > step_speeds[9]

    def test_first_step_not_min_speed(self):
        """Even the first step should be above slow_speed due to ramp."""
        arm = self._make_arm()
        speeds = []

        def capture_speed(servo_id, angle, debug, speed):
            speeds.append(speed)

        with patch('src.hardware.arm.TTLServo.servoAngleCtrl',
                   side_effect=capture_speed), \
             patch('time.sleep'):
            arm.move_to_pose_ramped([0, -40, -60, 0], num_steps=10,
                                    max_speed=150)

        # First step speed (step 1, progress=0.1, ramp=0.333)
        first_speed = speeds[3]  # 4th call = first step's gripper servo
        assert first_speed > arm.slow_speed

    def test_last_step_at_min_speed(self):
        """The last step should be at slow_speed (progress=1.0, ramp=0)."""
        arm = self._make_arm()
        speeds = []

        def capture_speed(servo_id, angle, debug, speed):
            speeds.append(speed)

        with patch('src.hardware.arm.TTLServo.servoAngleCtrl',
                   side_effect=capture_speed), \
             patch('time.sleep'):
            arm.move_to_pose_ramped([0, -40, -60, 0], num_steps=10,
                                    max_speed=150)

        # Last step: progress=1.0, ramp=(1.0-1.0)/0.3=0 → step_speed = slow_speed
        last_speed = speeds[-1]
        assert last_speed == arm.slow_speed

    def test_interpolated_angles_reach_target(self):
        """Final step angles should equal target pose."""
        arm = self._make_arm()
        target = [5, -30, -50, 45]
        angles = []

        def capture(servo_id, angle, debug, speed):
            if servo_id == arm.base_id:
                angles.append(angle)

        with patch('src.hardware.arm.TTLServo.servoAngleCtrl',
                   side_effect=capture), \
             patch('time.sleep'):
            arm.move_to_pose_ramped(target, num_steps=10)

        # Last interpolated angle should be the target
        assert angles[-1] == target[0]

    def test_failure_returns_false(self):
        arm = self._make_arm()
        with patch('src.hardware.arm.TTLServo.servoAngleCtrl',
                   side_effect=Exception("Servo error")), \
             patch('time.sleep'):
            result = arm.move_to_pose_ramped([0, -40, -60, 0])
        assert result is False
