"""DifferentialDriveOdometry — simple dead-reckoning pose estimator.

Useful on the real robot when no wheel encoders are available. It integrates
commanded motor values over time to estimate (x, y, yaw).
"""

import math
import time


class DifferentialDriveOdometry:
    """Estimate robot pose from commanded differential-drive motor speeds."""

    def __init__(self, robot, wheel_base=0.19, max_speed=0.25,
                 start_x=0.0, start_y=0.0, start_yaw=0.0):
        """
        Initialize odometry.

        Args:
            robot: Robot instance with left_motor and right_motor attributes
            wheel_base: Distance between tracks (m)
            max_speed: Motor value -> linear speed scale (m/s)
            start_x, start_y, start_yaw: Initial pose
        """
        self.robot = robot
        self.wheel_base = wheel_base
        self.max_speed = max_speed
        self.x = start_x
        self.y = start_y
        self.yaw = start_yaw
        self.last_time = time.time()

    def update(self):
        """Update pose estimate and return (x, y, yaw)."""
        now = time.time()
        dt = now - self.last_time
        self.last_time = now

        left = self.robot.left_motor.value
        right = self.robot.right_motor.value

        linear = (left + right) / 2.0 * self.max_speed
        angular = (right - left) / self.wheel_base * self.max_speed

        self.x += linear * math.cos(self.yaw) * dt
        self.y += linear * math.sin(self.yaw) * dt
        self.yaw += angular * dt

        # Normalize yaw
        while self.yaw > math.pi:
            self.yaw -= 2 * math.pi
        while self.yaw < -math.pi:
            self.yaw += 2 * math.pi

        return self.x, self.y, self.yaw

    def get_pose(self):
        """Return current pose estimate."""
        return self.x, self.y, self.yaw

    def reset(self, x=0.0, y=0.0, yaw=0.0):
        """Reset pose estimate."""
        self.x = x
        self.y = y
        self.yaw = yaw
        self.last_time = time.time()
