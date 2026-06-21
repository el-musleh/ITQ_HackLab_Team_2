#!/usr/bin/env python3
"""Unit tests for SafetyMonitor, StuckDetector, DarkFrameDetector, ArmCollisionDetector."""

import time
import numpy as np
import pytest

from src.control.safety_monitor import (
    SafetyMonitor,
    StuckDetector,
    DarkFrameDetector,
    ArmCollisionDetector,
    SafetyIssue,
    REASON_STUCK,
    REASON_DARK_FRAME,
    REASON_ARM_COLLISION,
)


# ---------------------------------------------------------------------------
# StuckDetector
# ---------------------------------------------------------------------------
class TestStuckDetector:
    def test_stuck_triggered_when_no_movement(self):
        """Motors running but position unchanged → triggers."""
        det = StuckDetector(window_s=1.0, min_displacement=0.05,
                            motor_threshold=0.05)
        base_time = time.time()
        # Feed 1 second of data with motors running but no movement
        for i in range(10):
            t = base_time + i * 0.1
            # Manually append to control timestamps
            det._poses.append((t, (1.0, 2.0)))
            det._motors.append((t, (0.15, 0.15)))
        issue = det.check()
        assert issue is not None
        assert issue.reason == REASON_STUCK

    def test_not_stuck_when_moving(self):
        """Motors running and position changing → does not trigger."""
        det = StuckDetector(window_s=1.0, min_displacement=0.05,
                            motor_threshold=0.05)
        base_time = time.time()
        for i in range(10):
            t = base_time + i * 0.1
            det._poses.append((t, (1.0 + i * 0.02, 2.0)))
            det._motors.append((t, (0.15, 0.15)))
        issue = det.check()
        assert issue is None

    def test_not_stuck_when_motors_off(self):
        """No motor command → does not trigger even if stationary."""
        det = StuckDetector(window_s=1.0, min_displacement=0.05,
                            motor_threshold=0.05)
        base_time = time.time()
        for i in range(10):
            t = base_time + i * 0.1
            det._poses.append((t, (1.0, 2.0)))
            det._motors.append((t, (0.0, 0.0)))
        issue = det.check()
        assert issue is None

    def test_reset_clears_state(self):
        det = StuckDetector(window_s=1.0, min_displacement=0.05)
        det._poses.append((time.time(), (0, 0)))
        det._motors.append((time.time(), (0.1, 0.1)))
        det.reset()
        assert len(det._poses) == 0
        assert len(det._motors) == 0


# ---------------------------------------------------------------------------
# DarkFrameDetector
# ---------------------------------------------------------------------------
class TestDarkFrameDetector:
    def test_dark_frame_triggered(self):
        """3 consecutive dark frames → triggers."""
        det = DarkFrameDetector(dark_threshold=25, frame_count=3)
        dark = np.zeros((240, 320, 3), dtype=np.uint8)
        for _ in range(3):
            det.update(dark)
        issue = det.check()
        assert issue is not None
        assert issue.reason == REASON_DARK_FRAME

    def test_bright_frame_not_triggered(self):
        det = DarkFrameDetector(dark_threshold=25, frame_count=3)
        bright = np.full((240, 320, 3), 128, dtype=np.uint8)
        for _ in range(5):
            det.update(bright)
        issue = det.check()
        assert issue is None

    def test_streak_resets_on_bright_frame(self):
        det = DarkFrameDetector(dark_threshold=25, frame_count=3)
        dark = np.zeros((240, 320, 3), dtype=np.uint8)
        bright = np.full((240, 320, 3), 128, dtype=np.uint8)
        det.update(dark)
        det.update(dark)
        det.update(bright)  # resets streak
        det.update(dark)
        issue = det.check()
        assert issue is None  # only 1 dark frame after reset

    def test_none_frame_does_not_trigger(self):
        det = DarkFrameDetector(dark_threshold=25, frame_count=3)
        for _ in range(5):
            det.update(None)
        issue = det.check()
        assert issue is None


# ---------------------------------------------------------------------------
# ArmCollisionDetector
# ---------------------------------------------------------------------------
class TestArmCollisionDetector:
    def test_visual_pre_check_clear(self):
        """No obstacle → visual pre-check returns True (safe)."""
        class MockObs:
            def detect_combined(self, frame):
                return {'obstacle_detected': False, 'boundary_detected': False}
        det = ArmCollisionDetector(obstacle_detector=MockObs())
        frame = np.full((240, 320, 3), 128, dtype=np.uint8)
        assert det.visual_pre_check(frame) is True

    def test_visual_pre_check_obstacle(self):
        """Obstacle detected → visual pre-check returns False (unsafe)."""
        class MockObs:
            def detect_combined(self, frame):
                return {'obstacle_detected': True, 'boundary_detected': False}
        det = ArmCollisionDetector(obstacle_detector=MockObs())
        frame = np.full((240, 320, 3), 128, dtype=np.uint8)
        assert det.visual_pre_check(frame) is False

    def test_visual_pre_check_boundary(self):
        """Boundary detected → visual pre-check returns False (unsafe)."""
        class MockObs:
            def detect_combined(self, frame):
                return {'obstacle_detected': False, 'boundary_detected': True}
        det = ArmCollisionDetector(obstacle_detector=MockObs())
        frame = np.full((240, 320, 3), 128, dtype=np.uint8)
        assert det.visual_pre_check(frame) is False

    def test_visual_pre_check_none_frame(self):
        """None frame → returns True (can't check, allow)."""
        det = ArmCollisionDetector(obstacle_detector=type('M', (), {
            'detect_combined': lambda self, f: {'obstacle_detected': True}
        })())
        assert det.visual_pre_check(None) is True

    def test_physics_check_triggers(self):
        """Physics check callback returns True → issue returned."""
        det = ArmCollisionDetector(physics_check_fn=lambda: True)
        issue = det.check(arm_extended=True)
        assert issue is not None
        assert issue.reason == REASON_ARM_COLLISION

    def test_physics_check_no_trigger_when_retracted(self):
        """Arm not extended → physics check not consulted."""
        det = ArmCollisionDetector(physics_check_fn=lambda: True)
        issue = det.check(arm_extended=False)
        assert issue is None

    def test_timeout_check(self):
        det = ArmCollisionDetector(arm_timeout_multiplier=1.5)
        assert det.timeout_check(5.0, 3.0) is True   # 5 > 3*1.5=4.5
        assert det.timeout_check(4.0, 3.0) is False   # 4 < 4.5
        assert det.timeout_check(4.6, 3.0) is True


# ---------------------------------------------------------------------------
# SafetyMonitor (aggregator)
# ---------------------------------------------------------------------------
class TestSafetyMonitor:
    def test_priority_arm_over_stuck(self):
        """Arm collision should be returned before stuck."""
        config = {'safety': {}}
        monitor = SafetyMonitor(
            config=config,
            physics_check_fn=lambda: True,
        )
        # Feed stuck data
        base_time = time.time()
        for i in range(10):
            t = base_time + i * 0.1
            monitor.stuck._poses.append((t, (0, 0)))
            monitor.stuck._motors.append((t, (0.15, 0.15)))
        # Arm collision should take priority
        issue = monitor.check(
            frame=np.full((240, 320, 3), 128, dtype=np.uint8),
            pose=(0, 0, 0),
            motor_values=(0.15, 0.15),
            arm_extended=True,
        )
        assert issue.reason == REASON_ARM_COLLISION

    def test_stuck_over_dark(self):
        """Stuck should be returned before dark frame."""
        monitor = SafetyMonitor(config={'safety': {}})
        base_time = time.time()
        for i in range(10):
            t = base_time + i * 0.1
            monitor.stuck._poses.append((t, (0, 0)))
            monitor.stuck._motors.append((t, (0.15, 0.15)))
        dark = np.zeros((240, 320, 3), dtype=np.uint8)
        for _ in range(3):
            monitor.dark.update(dark)
        issue = monitor.check(
            frame=dark,
            pose=(0, 0, 0),
            motor_values=(0.15, 0.15),
            arm_extended=False,
        )
        assert issue.reason == REASON_STUCK

    def test_dark_frame_when_no_other_issues(self):
        monitor = SafetyMonitor(config={'safety': {}})
        dark = np.zeros((240, 320, 3), dtype=np.uint8)
        for _ in range(3):
            monitor.dark.update(dark)
        issue = monitor.check(
            frame=dark,
            pose=(1.0, 2.0, 0),
            motor_values=(0.0, 0.0),
            arm_extended=False,
        )
        assert issue.reason == REASON_DARK_FRAME

    def test_no_issue_when_all_clear(self):
        monitor = SafetyMonitor(config={'safety': {}})
        bright = np.full((240, 320, 3), 128, dtype=np.uint8)
        issue = monitor.check(
            frame=bright,
            pose=(1.0, 2.0, 0),
            motor_values=(0.15, 0.15),
            arm_extended=False,
        )
        assert issue is None

    def test_reset_clears_all(self):
        monitor = SafetyMonitor(config={'safety': {}})
        monitor.dark._dark_streak = 5
        monitor.stuck._poses.append((time.time(), (0, 0)))
        monitor.reset()
        assert monitor.dark._dark_streak == 0
        assert len(monitor.stuck._poses) == 0
