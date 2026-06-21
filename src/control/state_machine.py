#!/usr/bin/env python3
"""State Machine — Main FSM for autonomous ball collection.

Seven main states plus a dedicated RECOVERY state:
    IDLE -> WANDERING -> CHECK_FOR_BALL -> COLLECT_BALL -> CHECK_FOR_BALL
    COLLECT_BALL -> RECOVERY (on failure) -> COLLECT_BALL / BALLS_LEFT
    CHECK_FOR_BALL -> BALLS_LEFT -> BLIND_SPOT -> END
"""

import math
import time

from src.control.pathfinder import AStarPathfinder
from src.control.pid import DualPIDController
from src.control.safety_monitor import SafetyMonitor, SafetyIssue
from src.control.safety_monitor import (REASON_STUCK, REASON_DARK_FRAME,
                                         REASON_ARM_COLLISION,
                                         REASON_ARM_TIMEOUT)

# Main states
IDLE = 'IDLE'
WANDERING = 'WANDERING'
CHECK_FOR_BALL = 'CHECK_FOR_BALL'
COLLECT_BALL = 'COLLECT_BALL'
BALLS_LEFT = 'BALLS_LEFT'
BLIND_SPOT = 'BLIND_SPOT'
END = 'END'
RECOVERY = 'RECOVERY'

# COLLECT_BALL internal sub-states
CS_APPROACH = 'APPROACH'
CS_PICKUP = 'PICKUP'
CS_GOTO_BASKET = 'GOTO_BASKET'
CS_DEPOSIT = 'DEPOSIT'

DEFAULT_TIMEOUTS = {
    IDLE: 5.0,
    WANDERING: 120.0,
    CHECK_FOR_BALL: 2.0,
    COLLECT_BALL: 60.0,
    BALLS_LEFT: 2.0,
    BLIND_SPOT: 30.0,
    END: 30.0,
    RECOVERY: 3.0,
}


class StateMachine:
    """Finite state machine for autonomous ball collection."""

    def __init__(self, ball_detector, basket_detector, obstacle_detector,
                 chassis, arm, camera, world_map, config=None,
                 pose_provider=None, start_corner=(0.0, 0.0), logger=None):
        """
        Initialize the state machine.

        Args:
            ball_detector: BallDetector instance
            basket_detector: BasketDetector instance
            obstacle_detector: ObstacleDetector instance
            chassis: ChassisController instance
            arm: ArmController instance
            camera: CameraController instance
            world_map: WorldMap instance
            config: Optional configuration dict
            pose_provider: Callable returning (x, y, yaw) in meters/radians
            start_corner: (x, y) of the starting corner (m)
            logger: Optional Python logger; prints if None
        """
        self.ball_detector = ball_detector
        self.basket_detector = basket_detector
        self.obstacle_detector = obstacle_detector
        self.chassis = chassis
        self.arm = arm
        self.camera = camera
        self.world_map = world_map
        self.pose_provider = pose_provider
        self.start_corner = start_corner
        self.logger = logger

        self.config = config or {}
        self.state_machine_config = self.config.get('state_machine', {})
        self.motor_config = self.config.get('motors', {})

        self.max_speed = self.motor_config.get('max_speed', 0.25)
        self.approach_speed = self.motor_config.get('approach_speed', 0.15)
        self.search_speed = self.motor_config.get('search_speed', 0.10)
        self.turn_speed = self.search_speed
        self.min_approach_speed = self.motor_config.get('min_approach_speed', 0.05)
        self.far_distance_threshold = self.motor_config.get('far_distance_threshold', 50.0)
        self.close_distance_threshold = self.motor_config.get('close_distance_threshold', 15.0)

        self.pid = DualPIDController(
            kp=self.config.get('pid', {}).get('kp', 3.0),
            ki=self.config.get('pid', {}).get('ki', 0.0),
            kd=self.config.get('pid', {}).get('kd', 0.5),
        )

        self.frame_width, self.frame_height = camera.get_frame_size()

        self.timeouts = DEFAULT_TIMEOUTS.copy()
        self.timeouts.update(self.state_machine_config.get('timeouts', {}))

        self.max_retries = 5
        self.basket_calibrated = False

        # Pathfinder for map-based navigation to basket
        pf_cfg = self.config.get('pathfinder', {})
        self.pathfinder = AStarPathfinder(
            arena_bounds=world_map.arena_bounds,
            obstacle_positions=world_map.obstacle_positions,
            cell_size=pf_cfg.get('cell_size', 0.05),
            safety_margin=pf_cfg.get('safety_margin', 0.18),
        )
        self.visual_homing_threshold = 0.5  # Switch to visual within 50cm of basket

        # Safety monitor (proactive stuck / dark-frame / arm-collision)
        physics_check_fn = None
        if hasattr(arm, 'check_arm_collision'):
            physics_check_fn = arm.check_arm_collision
        self.safety_monitor = SafetyMonitor(
            config=config,
            obstacle_detector=obstacle_detector,
            physics_check_fn=physics_check_fn,
        )

        self.reset()

    def reset(self):
        """Reset state machine to initial IDLE state."""
        self.state = IDLE
        self.state_start_time = time.time()
        self.state_data = {}

        self.current_ball = None
        self.finished = False
        self.fatal_error = None

        self.safety_active = False
        self.safety_clear_time = None
        self.safety_action = None
        self.safety_timer = 0.0
        self.safety_pause_start = None

        self.recovery_origin = None
        self.recovery_retry_count = 0
        self.recovery_reason = None

        self.collect_sub_state = None
        self.collect_sub_start = None

        # Track arm extension state for safety monitor
        self.arm_extended = False

        # Track dark-frame recovery re-check
        self._dark_recheck = False

        self.balls_collected = 0
        self.init_retries = {}
        self.camera_ready = False
        self.arm_ready = False

    def tick(self):
        """Run one control cycle. Return True while running, False when finished."""
        if self.finished or self.fatal_error:
            return False

        frame = self._read_frame()
        pose = self._get_pose()

        # Proactive safety monitor (stuck, dark frame, arm collision)
        # Skip when already in RECOVERY — the handler manages its own motors
        # and resets the monitor on entry.
        if self.state != RECOVERY:
            motor_values = self.chassis.get_motor_values() if hasattr(self.chassis, 'get_motor_values') else (0.0, 0.0)
            self.arm_extended = self._is_arm_extended()
            issue = self.safety_monitor.check(frame, pose, motor_values, self.arm_extended)
            if issue is not None:
                self._handle_safety_issue(issue)
                return True

        if self._update_safety(frame):
            return True

        if pose is not None:
            self.world_map.mark_visited(pose)

        next_state = self._state_handlers[self.state](self, frame, pose)
        self._transition_to(next_state)
        return not self.finished

    def _read_frame(self):
        try:
            return self.camera.read()
        except Exception as e:
            self._log(f'Camera read error: {e}')
            return None

    def _get_pose(self):
        if self.pose_provider is None:
            return None
        try:
            return self.pose_provider()
        except Exception as e:
            self._log(f'Pose provider error: {e}')
            return None

    def _log(self, message):
        if self.logger:
            self.logger.info(message)
        else:
            print(message)

    def _set_motors(self, left, right):
        self.chassis.set_motors(left, right)

    def _is_arm_extended(self):
        """Check whether the arm is currently in an extended pose."""
        if hasattr(self.arm, 'is_extended'):
            try:
                return self.arm.is_extended()
            except Exception:
                return False
        return False

    def _transition_to(self, new_state):
        if new_state == self.state:
            return
        if new_state == RECOVERY:
            self.recovery_origin = self.state
            self._saved_state_data = self.state_data
        old_state = self.state
        self.state = new_state
        self.state_start_time = time.time()
        if new_state == RECOVERY:
            self.state_data = {}
        elif old_state == RECOVERY and hasattr(self, '_saved_state_data') and self._saved_state_data:
            self.state_data = self._saved_state_data
            self._saved_state_data = None
        else:
            self.state_data = {}
        self._log(f'State -> {new_state} (from {old_state})')

    def _handle_safety_issue(self, issue):
        """Handle a proactive safety issue from SafetyMonitor."""
        self._log(f'Safety issue: {issue.reason} — {issue.detail}')
        self.safety_monitor.reset()

        if issue.reason == REASON_ARM_COLLISION:
            # Retract arm first, then go to recovery
            try:
                self.arm.home()
            except Exception as e:
                self._log(f'Arm retract failed: {e}')
            self.arm_extended = False
            self.recovery_reason = REASON_ARM_COLLISION
            self._transition_to(RECOVERY)
            return

        if issue.reason == REASON_STUCK:
            self.recovery_reason = REASON_STUCK
            self._transition_to(RECOVERY)
            return

        if issue.reason == REASON_DARK_FRAME:
            self.recovery_reason = REASON_DARK_FRAME
            self._transition_to(RECOVERY)
            return

        # Fallback: generic recovery
        self.recovery_reason = issue.reason
        self._transition_to(RECOVERY)

    def _elapsed(self):
        return time.time() - self.state_start_time

    def _timeout(self):
        return self._elapsed() > self.timeouts.get(self.state, 10.0)

    @staticmethod
    def _normalize_angle(angle):
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle

    def _update_safety(self, frame):
        if frame is None:
            return False
        obs = self.obstacle_detector.detect_combined(frame)
        now = time.time()

        if obs['boundary_detected'] or obs['obstacle_detected']:
            self.safety_active = True
            self.safety_clear_time = None
            if self.safety_action is None:
                self.safety_action = obs.get('turn_direction', 'reverse')
                self.safety_timer = now + 0.5
                self.safety_pause_start = now
                self._log(f'Safety: {obs["priority"]} -> {self.safety_action}')
                # If navigating to basket via A*, mark blocked area and replan
                if self.state == COLLECT_BALL and self.collect_sub_state == CS_GOTO_BASKET:
                    pose = self._get_pose()
                    if pose is not None:
                        self.pathfinder.mark_blocked(pose[0], pose[1], radius=0.15)
                        self.state_data.pop('basket_path', None)
                        self._log('GOTO_BASKET: obstacle hit — replanning A* path')
            self._execute_safety_action(self.safety_action)
            return True

        if self.safety_active:
            if self.safety_clear_time is None:
                self.safety_clear_time = now
            if now - self.safety_clear_time > 0.5 and now > self.safety_timer:
                self._log('Safety clear')
                self.safety_active = False
                self.safety_clear_time = None
                self.safety_action = None
                self.chassis.stop()
                if hasattr(self, 'safety_pause_start') and self.safety_pause_start:
                    self.state_start_time += now - self.safety_pause_start
                    self.safety_pause_start = None
            else:
                self._execute_safety_action(self.safety_action)
            return True

        return False

    def _execute_safety_action(self, action):
        speed = self.approach_speed
        if action == 'reverse':
            self._set_motors(-speed, -speed)
        elif action == 'left':
            self._set_motors(-speed, speed)
        elif action == 'right':
            self._set_motors(speed, -speed)
        else:
            self._set_motors(-speed, -speed)

    # ------------------------------------------------------------------
    # State handlers
    # ------------------------------------------------------------------
    def _state_idle(self, frame, pose):
        if self._elapsed() > self.timeouts[IDLE]:
            ok = True
            for name, init_fn in [('camera', self.camera.initialize),
                                   ('arm', self.arm.home)]:
                attr = f'{name}_ready'
                if not getattr(self, attr, False):
                    retries = self.init_retries.get(name, 0)
                    if retries >= 3:
                        self.fatal_error = f'{name} initialization failed after 3 retries'
                        self._log(f'FATAL: {self.fatal_error}')
                        return END
                    try:
                        result = init_fn()
                        if result:
                            setattr(self, attr, True)
                            self._log(f'{name} initialized')
                        else:
                            self.init_retries[name] = retries + 1
                            self._log(f'{name} init failed, retry {retries + 1}')
                            ok = False
                    except Exception as e:
                        self.init_retries[name] = retries + 1
                        self._log(f'{name} init error: {e}, retry {retries + 1}')
                        ok = False
            if not ok:
                self.state_start_time = time.time()
                return IDLE
            return WANDERING
        return IDLE

    def _state_wandering(self, frame, pose):
        # Calibrate basket when first reliably seen
        if frame is not None and not self.basket_calibrated:
            basket = self.basket_detector.detect(frame)
            if basket.get('basket_found'):
                frames = self.state_data.get('basket_frames', [])
                frames.append(frame)
                self.state_data['basket_frames'] = frames
                if len(frames) >= 10:
                    self._log('Calibrating basket...')
                    try:
                        self.basket_detector.calibrate(frames)
                        self.basket_calibrated = True
                        self._log('Basket calibrated')
                    except Exception as e:
                        self._log(f'Basket calibration failed: {e}')
                    # Estimate basket world position from first detection + pose
                    if pose is not None and basket.get('distance'):
                        bx, by = self._estimate_basket_world_pos(basket, pose)
                        if bx is not None:
                            self.world_map.set_basket_position(bx, by)
                            self._log(f'Basket world pos estimated: ({bx:.2f}, {by:.2f})')

        # Register balls seen in current frame (use validated detections)
        if frame is not None and pose is not None:
            raw_balls = self.ball_detector.detect(frame)
            balls = self.ball_detector.validate_detection(raw_balls)
            yellow_mask = self._get_yellow_mask(frame)
            pan = self.camera.get_pan() if hasattr(self.camera, 'get_pan') else 0
            for ball in balls:
                if self._ball_overlaps_yellow(ball, yellow_mask):
                    continue
                self.world_map.register_ball_from_detection(ball, pose, camera_pan_deg=pan)

        # Initialize sweep state
        if 'start_yaw' not in self.state_data:
            self.state_data['start_yaw'] = pose[2] if pose else 0.0
            self.state_data['sweep_phase'] = 0
            self.state_data['sweep_start'] = time.time()
            self.state_data['corners_visited'] = []
            self.camera.set_pan(-90)
            self._log('WANDERING: starting pan sweep')

        sweep_phase = self.state_data['sweep_phase']
        start_yaw = self.state_data['start_yaw']
        sweep_duration = 4.0
        elapsed = time.time() - self.state_data['sweep_start']

        # Phases 0-2: initial in-place pan sweep + rotate + sweep
        if sweep_phase == 0:
            pan = -90 + 180 * min(1.0, elapsed / sweep_duration)
            self.camera.set_pan(pan)
            if elapsed >= sweep_duration:
                self.state_data['sweep_phase'] = 1
                self.state_data['rotate_target'] = self._normalize_angle(start_yaw + math.pi)
                self.state_data['rotate_start'] = time.time()
                if pose is None:
                    self.camera.center()
                    return CHECK_FOR_BALL
        elif sweep_phase == 1:
            if pose is None:
                self.camera.center()
                return CHECK_FOR_BALL
            target_yaw = self.state_data['rotate_target']
            yaw_error = self._normalize_angle(target_yaw - pose[2])
            if abs(yaw_error) > 0.2:
                self._set_motors(-self.turn_speed, self.turn_speed)
            else:
                self._set_motors(0, 0)
                self.state_data['sweep_phase'] = 2
                self.state_data['sweep_start'] = time.time()
                self.camera.set_pan(-90)
        elif sweep_phase == 2:
            pan = -90 + 180 * min(1.0, elapsed / sweep_duration)
            self.camera.set_pan(pan)
            if elapsed >= sweep_duration:
                self.camera.center()
                # Mark current area visited and transition to corner navigation
                if pose is not None:
                    self.world_map.mark_visited(pose)
                self.state_data['sweep_phase'] = 3
                self._log('WANDERING: initial sweep done, navigating to corners')
        elif sweep_phase == 3:
            # Corner-to-corner navigation: go to each unvisited arena corner
            # and do a pan sweep at each one
            if pose is None:
                return CHECK_FOR_BALL

            # Check if we have a current corner target
            corner_target = self.state_data.get('corner_target')

            if corner_target is None:
                # Find next unvisited corner
                next_corner = self.world_map.get_nearest_unvisited_corner(pose)
                if next_corner is None:
                    # All corners visited — go check for balls / blind spots
                    self._log('WANDERING: all corners visited')
                    return CHECK_FOR_BALL
                self.state_data['corner_target'] = next_corner
                self.state_data['corner_sweep_done'] = False
                self._log(f'WANDERING: navigating to corner {next_corner}')

            corner_target = self.state_data['corner_target']

            if not self.state_data.get('corner_sweep_done', False):
                # Navigate to the corner
                reached = self._navigate_to_point(corner_target)
                if reached:
                    self._set_motors(0, 0)
                    self.world_map.mark_corner_visited(corner_target)
                    self.world_map.mark_visited(pose)
                    # Start a pan sweep at this corner
                    self.state_data['corner_sweep_done'] = True
                    self.state_data['corner_sweep_start'] = time.time()
                    self.state_data['corner_sweep_phase'] = 0
                    self.camera.set_pan(-90)
                    self._log(f'WANDERING: reached corner {corner_target}, sweeping')
            else:
                # Do pan sweep at this corner
                cs_elapsed = time.time() - self.state_data['corner_sweep_start']
                cs_phase = self.state_data['corner_sweep_phase']

                if cs_phase == 0:
                    pan = -90 + 180 * min(1.0, cs_elapsed / sweep_duration)
                    self.camera.set_pan(pan)
                    if cs_elapsed >= sweep_duration:
                        self.state_data['corner_sweep_phase'] = 1
                        self.state_data['corner_rotate_target'] = self._normalize_angle(
                            (pose[2] if pose else 0) + math.pi)
                        self.state_data['corner_rotate_start'] = time.time()
                elif cs_phase == 1:
                    if pose is None:
                        self.camera.center()
                        # Move to next corner
                        self.state_data['corner_target'] = None
                        return WANDERING
                    target_yaw = self.state_data['corner_rotate_target']
                    yaw_error = self._normalize_angle(target_yaw - pose[2])
                    if abs(yaw_error) > 0.2:
                        self._set_motors(-self.turn_speed, self.turn_speed)
                    else:
                        self._set_motors(0, 0)
                        self.state_data['corner_sweep_phase'] = 2
                        self.state_data['corner_sweep_start'] = time.time()
                        self.camera.set_pan(-90)
                elif cs_phase == 2:
                    pan = -90 + 180 * min(1.0, cs_elapsed / sweep_duration)
                    self.camera.set_pan(pan)
                    if cs_elapsed >= sweep_duration:
                        self.camera.center()
                        # Done with this corner — move to next
                        self._log(f'WANDERING: corner {corner_target} swept')
                        self.state_data['corner_target'] = None

        if self._timeout():
            self.camera.center()
            return CHECK_FOR_BALL
        return WANDERING

    def _get_yellow_mask(self, frame):
        """Get yellow obstacle mask, or None if unavailable."""
        if not hasattr(self.obstacle_detector, 'get_yellow_mask'):
            return None
        return self.obstacle_detector.get_yellow_mask(frame)

    def _ball_overlaps_yellow(self, ball, yellow_mask):
        """Check if a ball detection centroid falls on yellow tape pixels."""
        if yellow_mask is None:
            return False
        _, (cx, cy), _, _ = ball
        h, w = yellow_mask.shape[:2]
        if 0 <= cx < w and 0 <= cy < h:
            return yellow_mask[cy, cx] > 0
        return False

    def _validated_balls(self, frame):
        """Return validated ball detections, filtered by obstacle cross-check."""
        raw = self.ball_detector.detect(frame)
        validated = self.ball_detector.validate_detection(raw)
        if not validated:
            return []
        yellow_mask = self._get_yellow_mask(frame)
        return [b for b in validated if not self._ball_overlaps_yellow(b, yellow_mask)]

    def _state_check_for_ball(self, frame, pose):
        self.camera.center()
        if frame is None:
            return BALLS_LEFT
        balls = self._validated_balls(frame)
        if balls:
            balls_sorted = sorted(balls, key=lambda b: b[2])
            for ball in balls_sorted:
                world_id = None
                if pose is not None:
                    pan = self.camera.get_pan() if hasattr(self.camera, 'get_pan') else 0
                    world_id = self.world_map.register_ball_from_detection(
                        ball, pose, camera_pan_deg=pan)
                if world_id is not None:
                    self.current_ball = self._ball_to_dict(ball, world_id=world_id)
                    return COLLECT_BALL
                # Ball estimated outside arena — check if boundary confirms it
                boundary_detected, _, _ = self.obstacle_detector.detect_boundary(frame)
                if boundary_detected:
                    self._log('Ball outside arena (boundary confirmed) — skipping')
                else:
                    self._log('Ball position outside bounds but boundary not visible — skipping')
                # Try next ball
            # No valid balls found in this frame
        if self.world_map.has_known_balls():
            return BALLS_LEFT
        if self.world_map.has_blind_spots():
            return BLIND_SPOT
        return END

    def _ball_to_dict(self, ball, world_id=None):
        color, (cx, cy), distance, area = ball
        return {'color': color, 'cx': cx, 'cy': cy,
                'distance': distance, 'area': area, 'world_id': world_id}

    def _state_collect_ball(self, frame, pose):
        if self.collect_sub_state is None:
            self.collect_sub_state = CS_APPROACH
            self.collect_sub_start = time.time()
            self.pid.reset()

        if self._timeout():
            self._log('COLLECT_BALL timeout')
            self.collect_sub_state = None
            return RECOVERY

        next_sub = self._collect_sub_handlers[self.collect_sub_state](self, frame, pose)

        if next_sub is None:
            self.collect_sub_state = None
            self.balls_collected += 1
            self._log('Ball deposited successfully')
            return CHECK_FOR_BALL

        if next_sub != self.collect_sub_state:
            self.collect_sub_state = next_sub
            self.collect_sub_start = time.time()
            self.pid.reset()
            self.state_data.clear()

        return COLLECT_BALL

    def _sub_approach(self, frame, pose):
        if frame is None:
            return RECOVERY
        balls = self._validated_balls(frame)
        if not balls:
            lost_time = self.state_data.get('lost_time')
            if lost_time is None:
                self.state_data['lost_time'] = time.time()
            elif time.time() - lost_time > 1.0:
                self.state_data.pop('lost_time', None)
                return RECOVERY
            self.chassis.stop()
            return CS_APPROACH
        self.state_data.pop('lost_time', None)

        ball = self._find_matching_ball(balls)
        if ball is None:
            ball = balls[0]
        world_id = self.current_ball.get('world_id') if self.current_ball else None
        if pose is not None:
            pan = self.camera.get_pan() if hasattr(self.camera, 'get_pan') else 0
            new_id = self.world_map.register_ball_from_detection(
                ball, pose, camera_pan_deg=pan)
            if new_id is not None:
                world_id = new_id
        self.current_ball = self._ball_to_dict(ball, world_id=world_id)

        color, (cx, cy), distance, area = ball
        center_x = self.frame_width / 2
        centered = abs(cx - center_x) < 30
        close = distance < 15.0 or area > 800

        if centered and close:
            self.chassis.stop()
            return CS_PICKUP

        left, right = self.pid.update(cx, cy, self.frame_width, self.frame_height)
        left = max(-1.0, min(1.0, left))
        right = max(-1.0, min(1.0, right))
        speed_scale = self._distance_to_speed(distance)
        left *= speed_scale
        right *= speed_scale
        self._set_motors(left, right)
        return CS_APPROACH

    def _distance_to_speed(self, distance):
        """Linearly ramp approach speed based on ball distance.

        Far  (>= far_distance_threshold)  → approach_speed
        Close (<= close_distance_threshold) → min_approach_speed
        In between → linear interpolation.
        """
        if distance >= self.far_distance_threshold:
            return self.approach_speed
        if distance <= self.close_distance_threshold:
            return self.min_approach_speed
        ratio = (distance - self.close_distance_threshold) / (
            self.far_distance_threshold - self.close_distance_threshold)
        return self.min_approach_speed + ratio * (self.approach_speed - self.min_approach_speed)

    def _find_matching_ball(self, balls):
        if self.current_ball is None:
            return None
        target_color = self.current_ball.get('color')
        for ball in balls:
            if ball[0] == target_color:
                return ball
        return None

    def _sub_pickup(self, frame, pose):
        elapsed = time.time() - self.collect_sub_start

        # Layer 1: visual pre-check before extending arm
        if not self.state_data.get('pickup_visual_ok'):
            if frame is not None and frame.size > 0:
                if not self.safety_monitor.arm.visual_pre_check(frame):
                    self._log('Pickup aborted: obstacle detected before arm extension')
                    self.recovery_reason = REASON_ARM_COLLISION
                    return RECOVERY
            self.state_data['pickup_visual_ok'] = True

        # Layer 3: timeout check (expected total ~3.8s, multiplied)
        expected_pickup_duration = 3.8
        if self.safety_monitor.arm.timeout_check(elapsed, expected_pickup_duration):
            self._log(f'Pickup timeout: elapsed={elapsed:.1f}s > '
                      f'{expected_pickup_duration * self.safety_monitor.arm.arm_timeout_multiplier:.1f}s')
            try:
                self.arm.home()
            except Exception as e:
                self._log(f'Arm retract on timeout failed: {e}')
            self.arm_extended = False
            self.recovery_reason = REASON_ARM_TIMEOUT
            return RECOVERY

        steps = [
            (0.0, self.arm.gripper_open, 0.3),
            (0.3, lambda: self.arm.move_to_pose_ramped(self.arm.pose_pickup, max_speed=self.arm.slow_speed), 1.5),
            (1.8, self.arm.gripper_close, 0.5),
            (2.3, lambda: self.arm.move_to_pose_ramped(self.arm.pose_carry, max_speed=self.arm.default_speed), 1.5),
        ]
        last_step = self.state_data.get('last_pickup_step', -1)
        for i, (start, action, duration) in enumerate(steps):
            if start <= elapsed < start + duration:
                if last_step != i:
                    action()
                    self.state_data['last_pickup_step'] = i
                    self.arm_extended = (i == 1 or i == 3)
                return CS_PICKUP
        self.arm_extended = False
        return CS_GOTO_BASKET

    def _estimate_basket_world_pos(self, basket_detection, pose):
        """Estimate basket world coordinates from detection + robot pose.

        Args:
            basket_detection: Dict from BasketDetector.detect()
            pose: (x, y, yaw) robot pose

        Returns:
            (x, y) world coordinates or (None, None) if estimation fails.
        """
        if pose is None:
            return None, None
        rx, ry, ryaw = pose
        centroid = basket_detection.get('centroid')
        distance_cm = basket_detection.get('distance')
        if centroid is None or distance_cm is None:
            return None, None
        cx, _ = centroid
        # Bearing from frame center (approximate FOV 90 degrees)
        half_fov = math.radians(45)
        bearing = (cx - self.frame_width / 2) / (self.frame_width / 2) * half_fov
        distance_m = distance_cm / 100.0
        bx = rx + distance_m * math.cos(ryaw + bearing)
        by = ry + distance_m * math.sin(ryaw + bearing)
        return bx, by

    def _sub_goto_basket(self, frame, pose):
        """Hybrid navigation to basket: A* pathfinding + visual homing.

        Phase A: Follow A* waypoints from current pose to basket world position.
        Phase B: Switch to visual homing (BasketDetector) when within
                 ``visual_homing_threshold`` of the basket.
        Replans A* path if obstacle is encountered during Phase A.
        """
        basket_pos = self.world_map.get_basket_position()

        # --- No basket position: fall back to purely visual homing ---
        if basket_pos is None or pose is None:
            return self._goto_basket_visual(frame, pose)

        rx, ry, _ = pose
        dist_to_basket = math.hypot(basket_pos[0] - rx, basket_pos[1] - ry)

        # --- Phase B: Visual homing (close to basket) ---
        if dist_to_basket < self.visual_homing_threshold:
            result = self._goto_basket_visual(frame, pose)
            if result == CS_DEPOSIT:
                return result
            # If visual fails, fall back to path following
            if result == RECOVERY:
                # Replan and try path following
                self.state_data.pop('basket_path', None)
            else:
                return result

        # --- Phase A: A* path following ---
        # Compute path on first entry or after replan
        if 'basket_path' not in self.state_data or not self.state_data['basket_path']:
            path = self.pathfinder.find_path((rx, ry), basket_pos)
            if path is None:
                self._log('A* path to basket failed — trying visual homing')
                return self._goto_basket_visual(frame, pose)
            self.state_data['basket_path'] = list(path)
            self.state_data['basket_path_idx'] = 0
            self._log(f'A* path to basket: {len(path)} waypoints, '
                      f'{self.pathfinder.get_path_length(path):.2f}m')

        path = self.state_data['basket_path']
        idx = self.state_data.get('basket_path_idx', 0)

        if idx >= len(path):
            # Path exhausted — should be at basket, switch to visual
            self.state_data.pop('basket_path', None)
            return self._goto_basket_visual(frame, pose)

        # Navigate to current waypoint
        target = path[idx]
        reached = self._navigate_to_point(target)
        if reached:
            self.state_data['basket_path_idx'] = idx + 1
            if idx + 1 >= len(path):
                # Final waypoint reached — switch to visual
                self.state_data.pop('basket_path', None)
                return self._goto_basket_visual(frame, pose)
            return CS_GOTO_BASKET

        # Check timeout
        if self._timeout():
            self._log('GOTO_BASKET path following timeout')
            return RECOVERY

        return CS_GOTO_BASKET

    def _goto_basket_visual(self, frame, pose):
        """Visual homing using BasketDetector — final approach and alignment."""
        if frame is None:
            self.chassis.stop()
            return RECOVERY
        basket = self.basket_detector.detect(frame)
        if not basket.get('basket_found'):
            lost_time = self.state_data.get('basket_lost_time')
            if lost_time is None:
                self.state_data['basket_lost_time'] = time.time()
            elif time.time() - lost_time > 2.0:
                self.state_data.pop('basket_lost_time', None)
                return RECOVERY
            self.chassis.turn_left(self.turn_speed)
            return CS_GOTO_BASKET
        self.state_data.pop('basket_lost_time', None)

        centroid = basket.get('centroid')
        distance = basket.get('distance', 999)
        if centroid is None:
            self.chassis.turn_left(self.turn_speed)
            return CS_GOTO_BASKET

        cx, cy = centroid
        if distance < 20.0 and abs(cx - self.frame_width / 2) < 40:
            self.chassis.stop()
            return CS_DEPOSIT

        left, right = self.pid.update(cx, cy, self.frame_width, self.frame_height)
        left = max(-1.0, min(1.0, left))
        right = max(-1.0, min(1.0, right))
        left *= self.approach_speed * 0.8
        right *= self.approach_speed * 0.8
        self._set_motors(left, right)
        return CS_GOTO_BASKET

    def _sub_deposit(self, frame, pose):
        elapsed = time.time() - self.collect_sub_start

        # Layer 1: visual pre-check before extending arm over basket
        if not self.state_data.get('deposit_visual_ok'):
            if frame is not None and frame.size > 0:
                if not self.safety_monitor.arm.visual_pre_check(frame):
                    self._log('Deposit aborted: obstacle detected before arm extension')
                    self.recovery_reason = REASON_ARM_COLLISION
                    return RECOVERY
            self.state_data['deposit_visual_ok'] = True

        # Layer 3: timeout check (expected total ~4.0s, multiplied)
        expected_deposit_duration = 4.0
        if self.safety_monitor.arm.timeout_check(elapsed, expected_deposit_duration):
            self._log(f'Deposit timeout: elapsed={elapsed:.1f}s > '
                      f'{expected_deposit_duration * self.safety_monitor.arm.arm_timeout_multiplier:.1f}s')
            try:
                self.arm.home()
            except Exception as e:
                self._log(f'Arm retract on timeout failed: {e}')
            self.arm_extended = False
            self.recovery_reason = REASON_ARM_TIMEOUT
            return RECOVERY

        steps = [
            (0.0, lambda: self.arm.move_to_pose_ramped(self.arm.pose_deposit, max_speed=self.arm.default_speed), 1.5),
            (1.5, self.arm.gripper_open, 0.5),
            (2.0, lambda: self.arm.move_to_pose_ramped(self.arm.pose_home, max_speed=self.arm.default_speed), 2.0),
        ]
        last_step = self.state_data.get('last_deposit_step', -1)
        for i, (start, action, duration) in enumerate(steps):
            if start <= elapsed < start + duration:
                if last_step != i:
                    action()
                    self.state_data['last_deposit_step'] = i
                    self.arm_extended = (i == 0)
                return CS_DEPOSIT
        self.arm_extended = False
        if self.current_ball and self.current_ball.get('world_id'):
            self.world_map.mark_collected(self.current_ball['world_id'])
        self.current_ball = None
        return None

    def _state_balls_left(self, frame, pose):
        if self.world_map.has_known_balls():
            ball = self.world_map.get_nearest_ball(pose)
            if ball:
                self.current_ball = self._ball_to_dict_from_map(ball)
                return CHECK_FOR_BALL
        return BLIND_SPOT

    def _ball_to_dict_from_map(self, ball):
        return {'color': ball.get('color'), 'cx': None, 'cy': None,
                'distance': None, 'area': None, 'world_id': ball['id']}

    def _state_blind_spot(self, frame, pose):
        if pose is None:
            # No pose: rotate in place for a short sweep
            if 'sweep_done' not in self.state_data:
                self._set_motors(-self.turn_speed, self.turn_speed)
                if self._elapsed() > 3.0:
                    self.state_data['sweep_done'] = True
                    self.camera.center()
            else:
                return CHECK_FOR_BALL
            return BLIND_SPOT

        if 'target' not in self.state_data:
            target = self.world_map.get_nearest_blind_spot(pose)
            if target is None:
                return END
            self.state_data['target'] = target
            self._log(f'Blind spot target: {target}')

        target = self.state_data['target']

        # Phase 1: navigate to target
        if not self.state_data.get('reached', False):
            reached = self._navigate_to_point(target)
            if not reached:
                if self._timeout():
                    return RECOVERY
                return BLIND_SPOT
            # Reached target — start pan sweep
            self._set_motors(0, 0)
            self.world_map.mark_visited(pose)
            self.state_data['reached'] = True
            self.state_data['sweep_phase'] = 0
            self.state_data['sweep_start'] = time.time()
            self.camera.set_pan(-90)
            self._log(f'BLIND_SPOT: reached {target}, starting pan sweep')

        # Phase 2: pan sweep at the target location
        sweep_duration = 4.0
        sweep_phase = self.state_data['sweep_phase']
        elapsed = time.time() - self.state_data['sweep_start']

        if sweep_phase == 0:
            pan = -90 + 180 * min(1.0, elapsed / sweep_duration)
            self.camera.set_pan(pan)
            if elapsed >= sweep_duration:
                self.state_data['sweep_phase'] = 1
                self.state_data['rotate_target'] = self._normalize_angle(pose[2] + math.pi)
                self.camera.center()
        elif sweep_phase == 1:
            target_yaw = self.state_data['rotate_target']
            yaw_error = self._normalize_angle(target_yaw - pose[2])
            if abs(yaw_error) > 0.2:
                self._set_motors(-self.turn_speed, self.turn_speed)
            else:
                self._set_motors(0, 0)
                self.state_data['sweep_phase'] = 2
                self.state_data['sweep_start'] = time.time()
                self.camera.set_pan(-90)
        elif sweep_phase == 2:
            pan = -90 + 180 * min(1.0, elapsed / sweep_duration)
            self.camera.set_pan(pan)
            if elapsed >= sweep_duration:
                self.camera.center()
                # Register any balls found during the sweep
                if frame is not None:
                    balls = self._validated_balls(frame)
                    pan_val = self.camera.get_pan() if hasattr(self.camera, 'get_pan') else 0
                    for ball in balls:
                        self.world_map.register_ball_from_detection(ball, pose, camera_pan_deg=pan_val)
                self._log(f'BLIND_SPOT: sweep done at {target}')
                return CHECK_FOR_BALL

        return BLIND_SPOT

    def _navigate_to_point(self, target):
        pose = self._get_pose()
        if pose is None:
            return False
        rx, ry, ryaw = pose
        dx = target[0] - rx
        dy = target[1] - ry
        dist = math.hypot(dx, dy)
        if dist < 0.15:
            return True
        target_yaw = math.atan2(dy, dx)
        yaw_error = self._normalize_angle(target_yaw - ryaw)
        if abs(yaw_error) > 0.3:
            turn = self.turn_speed * (1.0 if yaw_error > 0 else -1.0)
            self._set_motors(-turn, turn)
        else:
            self._set_motors(self.approach_speed, self.approach_speed)
        return False

    def _state_end(self, frame, pose):
        if pose is None:
            self._set_motors(0, 0)
            self.finished = True
            self._log('End: no pose, stopping')
            return END
        reached = self._navigate_to_point(self.start_corner)
        if reached:
            self._set_motors(0, 0)
            self.finished = True
            self._log('End: returned to start corner')
        return END

    def _state_recovery(self, frame, pose):
        if self.recovery_origin is None:
            self.recovery_origin = CHECK_FOR_BALL

        if 'recovery_start' not in self.state_data:
            self.state_data['recovery_start'] = time.time()
            self._log(f'RECOVERY from {self.recovery_origin} '
                      f'reason={self.recovery_reason} '
                      f'retry {self.recovery_retry_count}')
            # Reset safety monitor detectors on recovery entry
            self.safety_monitor.reset()

        elapsed = time.time() - self.state_data['recovery_start']
        reason = self.recovery_reason

        # Reason-based recovery sequences
        if reason == REASON_STUCK:
            # Longer reverse for stuck situations
            if elapsed < 0.8:
                self._set_motors(-self.approach_speed, -self.approach_speed)
            elif elapsed < 1.5:
                self._set_motors(-self.turn_speed, self.turn_speed)
            else:
                self.chassis.stop()
                return self._finish_recovery()

        elif reason == REASON_DARK_FRAME:
            # Reverse to clear view, then re-check frame
            if elapsed < 0.5:
                self._set_motors(-self.approach_speed, -self.approach_speed)
            elif elapsed < 1.0:
                self.chassis.stop()
                # Re-check if frame is still dark
                if frame is not None and frame.size > 0:
                    gray_mean = frame.mean()
                    if gray_mean < self.safety_monitor.dark.dark_threshold:
                        self._log(f'Still dark after reverse (mean={gray_mean:.1f}), retrying')
                        # Continue reversing
                        self.state_data['recovery_start'] = time.time()
                        self._set_motors(-self.approach_speed, -self.approach_speed)
                        return RECOVERY
                self._log('Frame cleared after reverse')
            else:
                return self._finish_recovery()

        elif reason == REASON_ARM_COLLISION or reason == REASON_ARM_TIMEOUT:
            # Arm should already be retracted by _handle_safety_issue or sub-state
            # Brief reverse + turn
            if elapsed < 0.5:
                self._set_motors(-self.approach_speed, -self.approach_speed)
            elif elapsed < 1.5:
                self._set_motors(-self.turn_speed, self.turn_speed)
            else:
                self.chassis.stop()
                return self._finish_recovery()

        else:
            # Default recovery (timeout, lost target, etc.)
            if elapsed < 0.5:
                self._set_motors(-self.approach_speed, -self.approach_speed)
            elif elapsed < 1.5:
                self._set_motors(-self.turn_speed, self.turn_speed)
            else:
                self.chassis.stop()
                return self._finish_recovery()

        return RECOVERY

    def _finish_recovery(self):
        """Common exit logic for recovery state."""
        self.recovery_retry_count += 1
        if self.recovery_retry_count > self.max_retries:
            self._log('Recovery retries exhausted')
            # If we're carrying a ball (GOTO_BASKET failed), keep it and
            # replan the path rather than discarding it.
            if (self.recovery_origin == COLLECT_BALL
                    and self.collect_sub_state == CS_GOTO_BASKET
                    and self.current_ball is not None):
                self._log('Keeping ball — replanning path to basket')
                self.state_data.pop('basket_path', None)
                self.recovery_origin = None
                self.recovery_retry_count = 0
                self.recovery_reason = None
                return CS_GOTO_BASKET
            # Normal exhaustion: mark ball unreachable and move on
            if self.current_ball and self.current_ball.get('world_id'):
                self.world_map.mark_unreachable(self.current_ball['world_id'])
            self.current_ball = None
            self.recovery_origin = None
            self.recovery_retry_count = 0
            self.recovery_reason = None
            return BALLS_LEFT
        else:
            origin = self.recovery_origin
            self.recovery_origin = None
            self.recovery_retry_count = 0
            self.recovery_reason = None
            return origin

    _state_handlers = {
        IDLE: _state_idle,
        WANDERING: _state_wandering,
        CHECK_FOR_BALL: _state_check_for_ball,
        COLLECT_BALL: _state_collect_ball,
        BALLS_LEFT: _state_balls_left,
        BLIND_SPOT: _state_blind_spot,
        END: _state_end,
        RECOVERY: _state_recovery,
    }

    _collect_sub_handlers = {
        CS_APPROACH: _sub_approach,
        CS_PICKUP: _sub_pickup,
        CS_GOTO_BASKET: _sub_goto_basket,
        CS_DEPOSIT: _sub_deposit,
    }

    def get_status(self):
        """Return a status summary dict."""
        total, collected, remaining, unreachable = self.world_map.get_ball_count()
        return {
            'state': self.state,
            'balls_collected': self.balls_collected,
            'balls_in_map': total,
            'balls_remaining': remaining,
            'current_ball': self.current_ball,
            'finished': self.finished,
            'fatal_error': self.fatal_error,
        }
