"""Unit tests for DifferentialDriveOdometry including landmark correction."""

import math
import pytest
from src.control.odometry import DifferentialDriveOdometry


class MockMotor:
    def __init__(self, value=0.0):
        self.value = value


class MockRobot:
    def __init__(self, left=0.0, right=0.0):
        self.left_motor = MockMotor(left)
        self.right_motor = MockMotor(right)


class TestOdometryBasic:
    def test_init_defaults(self):
        robot = MockRobot()
        odo = DifferentialDriveOdometry(robot)
        assert odo.x == 0.0
        assert odo.y == 0.0
        assert odo.yaw == 0.0

    def test_init_custom(self):
        robot = MockRobot()
        odo = DifferentialDriveOdometry(robot, wheel_base=0.2,
                                        start_x=1.0, start_y=2.0,
                                        start_yaw=0.5)
        assert odo.x == 1.0
        assert odo.y == 2.0
        assert odo.yaw == 0.5

    def test_get_pose(self):
        robot = MockRobot()
        odo = DifferentialDriveOdometry(robot, start_x=0.5, start_y=0.3,
                                        start_yaw=1.0)
        pose = odo.get_pose()
        assert pose == (0.5, 0.3, 1.0)

    def test_reset(self):
        robot = MockRobot()
        odo = DifferentialDriveOdometry(robot, start_x=1.0, start_y=1.0)
        odo.reset(0.0, 0.0, 0.0)
        assert odo.x == 0.0
        assert odo.y == 0.0
        assert odo.yaw == 0.0


class TestOdometryUpdate:
    def test_stationary_no_movement(self):
        robot = MockRobot(0.0, 0.0)
        odo = DifferentialDriveOdometry(robot)
        # Force a small dt by setting last_time in the past
        import time
        odo.last_time = time.time() - 0.01
        pose = odo.update()
        assert abs(pose[0]) < 0.001
        assert abs(pose[1]) < 0.001

    def test_forward_movement(self):
        robot = MockRobot(1.0, 1.0)
        odo = DifferentialDriveOdometry(robot, max_speed=0.25)
        import time
        odo.last_time = time.time() - 0.1  # 100ms
        pose = odo.update()
        # Should move forward in x direction (yaw=0)
        assert pose[0] > 0
        assert abs(pose[1]) < 0.001

    def test_rotation(self):
        robot = MockRobot(-1.0, 1.0)  # Turn left
        odo = DifferentialDriveOdometry(robot, max_speed=0.25, wheel_base=0.19)
        import time
        odo.last_time = time.time() - 0.1
        pose = odo.update()
        # Yaw should increase (turning left)
        assert pose[2] > 0


class TestCorrectPose:
    def test_correct_pose_reduces_error(self):
        """Verify that correct_pose reduces position error."""
        robot = MockRobot()
        odo = DifferentialDriveOdometry(robot, correction_alpha=0.5)

        # Simulate drift: robot thinks it's at (0.5, 0.5, 0) but
        # is actually at (0.6, 0.5, 0). A landmark at (1.0, 0.5)
        # is observed at bearing=0, distance=0.4 (from true position).
        odo.x = 0.5
        odo.y = 0.5
        odo.yaw = 0.0

        # From true position (0.6, 0.5), landmark at (1.0, 0.5):
        # bearing = 0, distance = 0.4
        odo.correct_pose(landmark_x=1.0, landmark_y=0.5,
                         observed_bearing=0.0, observed_distance=0.4)

        # After correction, x should move toward 0.6
        assert odo.x > 0.5
        assert abs(odo.y - 0.5) < 0.01

    def test_correct_pose_alpha_zero_noop(self):
        robot = MockRobot()
        odo = DifferentialDriveOdometry(robot, correction_alpha=0.0)
        odo.x = 0.5
        odo.y = 0.5
        odo.yaw = 0.0
        odo.correct_pose(1.0, 0.5, 0.0, 0.4)
        assert odo.x == 0.5
        assert odo.y == 0.5

    def test_correct_pose_full_correction(self):
        robot = MockRobot()
        odo = DifferentialDriveOdometry(robot, correction_alpha=1.0)
        odo.x = 0.5
        odo.y = 0.5
        odo.yaw = 0.0
        # With alpha=1.0, correction should fully align
        odo.correct_pose(1.0, 0.5, 0.0, 0.4)
        # After full correction, predicted landmark should match actual
        predicted_x = odo.x + 0.4 * math.cos(odo.yaw + 0.0)
        predicted_y = odo.y + 0.4 * math.sin(odo.yaw + 0.0)
        assert abs(predicted_x - 1.0) < 0.01
        assert abs(predicted_y - 0.5) < 0.01

    def test_correct_pose_with_yaw_error(self):
        robot = MockRobot()
        odo = DifferentialDriveOdometry(robot, correction_alpha=0.5)
        odo.x = 0.5
        odo.y = 0.5
        odo.yaw = 0.1  # Small yaw error
        # Landmark straight ahead at 0.5m
        odo.correct_pose(1.0, 0.5, 0.0, 0.5)
        # Yaw should be corrected toward 0
        assert abs(odo.yaw) < 0.1


class TestDriftNoise:
    def test_drift_noise_adds_variation(self):
        robot = MockRobot(0.0, 0.0)  # Stationary
        odo = DifferentialDriveOdometry(robot, drift_noise_std=0.01)
        import time
        initial_x = odo.x
        odo.last_time = time.time() - 0.01
        odo.update()
        # With drift noise, position should change even when stationary
        assert odo.x != initial_x or odo.y != initial_x

    def test_no_drift_noise_when_disabled(self):
        robot = MockRobot(0.0, 0.0)
        odo = DifferentialDriveOdometry(robot, drift_noise_std=0.0)
        import time
        initial_x = odo.x
        odo.last_time = time.time() - 0.01
        odo.update()
        assert odo.x == initial_x
