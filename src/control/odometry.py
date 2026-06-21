"""DifferentialDriveOdometry — simple dead-reckoning pose estimator.

Useful on the real robot when no wheel encoders are available. It integrates
commanded motor values over time to estimate (x, y, yaw).
"""

import math
import random
import time


class DifferentialDriveOdometry:
    """Estimate robot pose from commanded differential-drive motor speeds."""

    def __init__(self, robot, wheel_base=0.19, max_speed=0.25,
                 start_x=0.0, start_y=0.0, start_yaw=0.0,
                 correction_alpha=0.3, drift_noise_std=0.0):
        """
        Initialize odometry.

        Args:
            robot: Robot instance with left_motor and right_motor attributes
            wheel_base: Distance between tracks (m)
            max_speed: Motor value -> linear speed scale (m/s)
            start_x, start_y, start_yaw: Initial pose
            correction_alpha: Weight for landmark correction (0=ignore, 1=full trust)
            drift_noise_std: Simulated drift noise (m per step), 0=disabled
        """
        self.robot = robot
        self.wheel_base = wheel_base
        self.max_speed = max_speed
        self.x = start_x
        self.y = start_y
        self.yaw = start_yaw
        self.last_time = time.time()
        self.correction_alpha = correction_alpha
        self.drift_noise_std = drift_noise_std
        self._rng = random.Random()

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

        # Optional simulated drift noise (useful for testing robustness)
        if self.drift_noise_std > 0:
            self.x += self._rng.gauss(0, self.drift_noise_std)
            self.y += self._rng.gauss(0, self.drift_noise_std)
            self.yaw += self._rng.gauss(0, self.drift_noise_std * 0.1)

        # Normalize yaw
        while self.yaw > math.pi:
            self.yaw -= 2 * math.pi
        while self.yaw < -math.pi:
            self.yaw += 2 * math.pi

        return self.x, self.y, self.yaw

    def get_pose(self):
        """Return current pose estimate."""
        return self.x, self.y, self.yaw

    def correct_pose(self, landmark_x, landmark_y, observed_bearing, observed_distance):
        """Correct pose estimate using a single known landmark.

        Given a landmark at a known world position and its observed bearing
        (radians, relative to robot heading) and distance (meters), adjust
        the estimated pose to reduce drift error.

        Uses weighted correction: alpha * observed + (1-alpha) * dead_reckoned.

        Args:
            landmark_x: Known landmark x position (m)
            landmark_y: Known landmark y position (m)
            observed_bearing: Bearing to landmark from robot frame (rad)
            observed_distance: Distance to landmark (m)
        """
        alpha = self.correction_alpha
        if alpha <= 0:
            return

        # Predicted landmark position from current dead-reckoned pose
        predicted_x = self.x + observed_distance * math.cos(self.yaw + observed_bearing)
        predicted_y = self.y + observed_distance * math.sin(self.yaw + observed_bearing)

        # Error between predicted and known landmark position
        err_x = landmark_x - predicted_x
        err_y = landmark_y - predicted_y

        # Apply weighted correction to position
        self.x += alpha * err_x
        self.y += alpha * err_y

        # Correct yaw: the bearing to the landmark from the corrected position
        # should match observed_bearing
        expected_bearing = math.atan2(landmark_y - self.y, landmark_x - self.x)
        yaw_correction = expected_bearing - (self.yaw + observed_bearing)
        # Normalize to [-pi, pi]
        while yaw_correction > math.pi:
            yaw_correction -= 2 * math.pi
        while yaw_correction < -math.pi:
            yaw_correction += 2 * math.pi
        self.yaw += alpha * yaw_correction

        # Normalize yaw
        while self.yaw > math.pi:
            self.yaw -= 2 * math.pi
        while self.yaw < -math.pi:
            self.yaw += 2 * math.pi

    def reset(self, x=0.0, y=0.0, yaw=0.0):
        """Reset pose estimate."""
        self.x = x
        self.y = y
        self.yaw = yaw
        self.last_time = time.time()
