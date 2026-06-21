#!/usr/bin/env python3
"""Safety Monitor — Proactive detection of stuck, dark-frame, and arm-collision situations.

Three independent detectors are aggregated by :class:`SafetyMonitor`.  Each
detector exposes a ``check(...)`` method returning a :class:`SafetyIssue` or
``None``.  The state machine calls ``SafetyMonitor.check`` on every tick before
running state handlers.
"""

import collections
import time

import numpy as np


# Recovery reason constants (also used by the state machine RECOVERY handler)
REASON_STUCK = 'stuck'
REASON_DARK_FRAME = 'dark_frame'
REASON_ARM_COLLISION = 'arm_collision'
REASON_ARM_TIMEOUT = 'arm_timeout'


class SafetyIssue:
    """Describes a safety issue detected during a tick."""

    __slots__ = ('reason', 'action', 'detail')

    def __init__(self, reason, action='reverse', detail=''):
        self.reason = reason
        self.action = action
        self.detail = detail

    def __repr__(self):
        return f'SafetyIssue(reason={self.reason!r}, action={self.action!r})'


# ---------------------------------------------------------------------------
# Stuck detector
# ---------------------------------------------------------------------------
class StuckDetector:
    """Detects motor stall by comparing motor commands with pose displacement."""

    def __init__(self, window_s=2.0, min_displacement=0.02,
                 motor_threshold=0.05):
        self.window_s = window_s
        self.min_displacement = min_displacement
        self.motor_threshold = motor_threshold
        self._poses = collections.deque()  # (timestamp, (x, y, yaw))
        self._motors = collections.deque()  # (timestamp, (left, right))

    def update(self, pose, motor_values):
        """Feed latest pose and motor values into the rolling window."""
        now = time.time()
        if pose is not None:
            yaw = pose[2] if len(pose) > 2 else 0.0
            self._poses.append((now, (pose[0], pose[1], yaw)))
        self._motors.append((now, motor_values))
        self._prune(now)

    def _prune(self, now):
        cutoff = now - self.window_s
        while self._poses and self._poses[0][0] < cutoff:
            self._popleft_pose()
        while self._motors and self._motors[0][0] < cutoff:
            self._motors.popleft()

    def _popleft_pose(self):
        self._poses.popleft()

    def check(self):
        """Return a :class:`SafetyIssue` if stuck, else ``None``."""
        if len(self._poses) < 2 or len(self._motors) < 2:
            return None

        # Are motors being driven?
        max_motor = max(abs(m[1][0]) + abs(m[1][1]) for m in self._motors)
        if max_motor < self.motor_threshold:
            return None

        # If motors have opposite signs, robot is turning — not stuck
        avg_left = sum(m[1][0] for m in self._motors) / len(self._motors)
        avg_right = sum(m[1][1] for m in self._motors) / len(self._motors)
        if avg_left * avg_right < 0:
            return None

        # Has the robot moved enough?
        first = self._poses[0][1]
        last = self._poses[-1][1]
        disp = np.hypot(last[0] - first[0], last[1] - first[1])
        if disp < self.min_displacement:
            return SafetyIssue(
                REASON_STUCK, action='reverse',
                detail=f'disp={disp:.3f}m motors={max_motor:.2f}',
            )
        return None

    def reset(self):
        self._poses.clear()
        self._motors.clear()


# ---------------------------------------------------------------------------
# Dark frame detector
# ---------------------------------------------------------------------------
class DarkFrameDetector:
    """Detects vision blackout when the camera is too close to an obstacle."""

    def __init__(self, dark_threshold=25, frame_count=3):
        self.dark_threshold = dark_threshold
        self.frame_count = frame_count
        self._dark_streak = 0

    def update(self, frame):
        """Feed the latest camera frame.  Returns ``True`` if frame is dark."""
        if frame is None:
            return False
        try:
            gray = np.mean(frame)
        except Exception:
            return False
        if gray < self.dark_threshold:
            self._dark_streak += 1
        else:
            self._dark_streak = 0
        return self._dark_streak >= self.frame_count

    def check(self):
        """Return a :class:`SafetyIssue` if dark streak is long enough."""
        if self._dark_streak >= self.frame_count:
            return SafetyIssue(
                REASON_DARK_FRAME, action='reverse',
                detail=f'dark_streak={self._dark_streak}',
            )
        return None

    def reset(self):
        self._dark_streak = 0


# ---------------------------------------------------------------------------
# Arm collision detector
# ---------------------------------------------------------------------------
class ArmCollisionDetector:
    """Multi-layer arm collision / obstruction detection.

    Layer 1 — visual pre-check via an obstacle detector (both sim + hardware).
    Layer 2 — physics contact check (simulation only, via callback).
    Layer 3 — sub-state timeout (both sim + hardware).
    """

    def __init__(self, obstacle_detector=None, arm_timeout_multiplier=1.5,
                 visual_check_enabled=True,
                 physics_check_fn=None):
        self.obstacle_detector = obstacle_detector
        self.arm_timeout_multiplier = arm_timeout_multiplier
        self.visual_check_enabled = visual_check_enabled
        self.physics_check_fn = physics_check_fn

    def visual_pre_check(self, frame):
        """Layer 1: check for obstacles before extending the arm.

        Returns ``True`` if it is *safe* to extend (no obstacle detected).
        """
        if not self.visual_check_enabled or self.obstacle_detector is None:
            return True
        if frame is None or frame.size == 0:
            return True  # can't check, allow (recovery handles None frame)
        result = self.obstacle_detector.detect_combined(frame)
        return not (result.get('obstacle_detected') or
                    result.get('boundary_detected'))

    def physics_check(self):
        """Layer 2: check PyBullet arm-link contacts (sim only).

        Returns ``True`` if an arm collision is detected.
        """
        if self.physics_check_fn is None:
            return False
        return self.physics_check_fn()

    def timeout_check(self, elapsed, expected_duration):
        """Layer 3: check whether an arm sub-state has taken too long.

        Returns ``True`` if the sub-state has exceeded the timeout.
        """
        return elapsed > expected_duration * self.arm_timeout_multiplier

    def check(self, frame=None, arm_extended=False):
        """Combined check.  Returns a :class:`SafetyIssue` or ``None``."""
        # Layer 2 — physics contact (only meaningful while arm is moving)
        if arm_extended and self.physics_check():
            return SafetyIssue(
                REASON_ARM_COLLISION, action='retract',
                detail='physics contact on arm link',
            )
        return None


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------
class SafetyMonitor:
    """Aggregates StuckDetector, DarkFrameDetector, and ArmCollisionDetector."""

    def __init__(self, config=None, obstacle_detector=None,
                 physics_check_fn=None):
        safety_cfg = (config or {}).get('safety', {})

        self.stuck = StuckDetector(
            window_s=safety_cfg.get('stuck_window_s', 2.0),
            min_displacement=safety_cfg.get('stuck_min_displacement', 0.02),
            motor_threshold=safety_cfg.get('stuck_motor_threshold', 0.05),
        )
        self.dark = DarkFrameDetector(
            dark_threshold=safety_cfg.get('dark_threshold', 25),
            frame_count=safety_cfg.get('dark_frame_count', 3),
        )
        self.arm = ArmCollisionDetector(
            obstacle_detector=obstacle_detector,
            arm_timeout_multiplier=safety_cfg.get('arm_timeout_multiplier', 1.5),
            visual_check_enabled=safety_cfg.get('arm_visual_check', True),
            physics_check_fn=physics_check_fn,
        )

    def check(self, frame, pose, motor_values, arm_extended=False):
        """Run all detectors and return the first :class:`SafetyIssue` or ``None``.

        Priority: arm collision > stuck > dark frame.
        """
        # Feed data into detectors
        self.stuck.update(pose, motor_values)
        self.dark.update(frame)

        # Check arm collision (Layer 2 physics)
        issue = self.arm.check(frame=frame, arm_extended=arm_extended)
        if issue is not None:
            return issue

        # Check stuck
        issue = self.stuck.check()
        if issue is not None:
            return issue

        # Check dark frame
        issue = self.dark.check()
        if issue is not None:
            return issue

        return None

    def reset(self):
        self.stuck.reset()
        self.dark.reset()
