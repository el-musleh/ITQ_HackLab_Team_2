#!/usr/bin/env python3
"""State Machine — Main FSM for autonomous ball collection.

Seven main states plus a dedicated RECOVERY state:
    IDLE -> WANDERING -> CHECK_FOR_BALL -> COLLECT_BALL -> CHECK_FOR_BALL
    COLLECT_BALL -> RECOVERY (on failure) -> COLLECT_BALL / BALLS_LEFT
    CHECK_FOR_BALL -> BALLS_LEFT -> BLIND_SPOT -> END
"""

import math
import time

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
    WANDERING: 30.0,
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

        self.pid = DualPIDController(
            kp=self.config.get('pid', {}).get('kp', 3.0),
            ki=self.config.get('pid', {}).get('ki', 0.0),
            kd=self.config.get('pid', {}).get('kd', 0.5),
        )

        self.frame_width, self.frame_height = camera.get_frame_size()

        self.timeouts = DEFAULT_TIMEOUTS.copy()
        self.timeouts.update(self.state_machine_config.get('timeouts', {}))

        self.max_retries = 3
        self.basket_calibrated = False

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
        old_state = self.state
        self.state = new_state
        self.state_start_time = time.time()
        self.state_data = {}
        self._log(f'State -> {new_state} (from {old_state})')

    def _handle_safety_issue(self, issue):
        """Handle a proactive safety issue from SafetyMonitor."""
        self._log(f'Safety issue: {issue.reason} — {issue.detail}')

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

        # Register balls seen in current frame
        if frame is not None and pose is not None:
            balls = self.ball_detector.detect(frame)
            pan = self.camera.get_pan() if hasattr(self.camera, 'get_pan') else 0
            for ball in balls:
                self.world_map.register_ball_from_detection(ball, pose, camera_pan_deg=pan)

        # Initialize sweep state
        if 'start_yaw' not in self.state_data:
            self.state_data['start_yaw'] = pose[2] if pose else 0.0
            self.state_data['sweep_phase'] = 0
            self.state_data['sweep_start'] = time.time()
            self.camera.set_pan(-90)
            self._log('WANDERING: starting pan sweep')

        sweep_phase = self.state_data['sweep_phase']
        start_yaw = self.state_data['start_yaw']
        sweep_duration = 4.0
        elapsed = time.time() - self.state_data['sweep_start']

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
                return CHECK_FOR_BALL

        if self._timeout():
            self.camera.center()
            return CHECK_FOR_BALL
        return WANDERING

    def _state_check_for_ball(self, frame, pose):
        self.camera.center()
        if frame is None:
            return BALLS_LEFT
        balls = self.ball_detector.detect(frame)
        if balls:
            balls_sorted = sorted(balls, key=lambda b: b[2])
            self.current_ball = self._ball_to_dict(balls_sorted[0])
            return COLLECT_BALL
        if self.world_map.has_known_balls():
            return BALLS_LEFT
        if self.world_map.has_blind_spots():
            return BLIND_SPOT
        return END

    def _ball_to_dict(self, ball):
        color, (cx, cy), distance, area = ball
        return {'color': color, 'cx': cx, 'cy': cy,
                'distance': distance, 'area': area, 'world_id': None}

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
        balls = self.ball_detector.detect(frame)
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
        self.current_ball = self._ball_to_dict(ball)

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
        left *= self.approach_speed
        right *= self.approach_speed
        self._set_motors(left, right)
        return CS_APPROACH

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
            (0.3, lambda: self.arm.move_to_pose(self.arm.pose_pickup), 1.5),
            (1.8, self.arm.gripper_close, 0.5),
            (2.3, lambda: self.arm.move_to_pose(self.arm.pose_carry), 1.5),
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

    def _sub_goto_basket(self, frame, pose):
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
            (0.0, lambda: self.arm.move_to_pose(self.arm.pose_deposit), 1.5),
            (1.5, self.arm.gripper_open, 0.5),
            (2.0, lambda: self.arm.move_to_pose(self.arm.pose_home), 2.0),
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
        return {'color': None, 'cx': None, 'cy': None,
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
        reached = self._navigate_to_point(target)
        if reached:
            self._set_motors(0, 0)
            if frame is not None:
                balls = self.ball_detector.detect(frame)
                pan = self.camera.get_pan() if hasattr(self.camera, 'get_pan') else 0
                for ball in balls:
                    self.world_map.register_ball_from_detection(ball, pose, camera_pan_deg=pan)
            self.world_map.mark_visited(pose)
            return CHECK_FOR_BALL

        if self._timeout():
            return RECOVERY
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
