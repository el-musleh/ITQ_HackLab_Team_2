"""
Simulated Hardware Interfaces
Drop-in replacements for hardware.chassis, hardware.arm, hardware.camera.

These classes have IDENTICAL APIs to the real hardware classes, allowing
seamless switching between simulation and real robot with a single import
change.
"""

import logging
import time

import numpy as np
import pybullet as p

from src.simulation.sim_core import render_camera

logger = logging.getLogger(__name__)


# Fallback joint indices (used only when the URDF joint discovery fails or
# when no joint_map is provided). Matches the original jetank.urdf layout.
_DEFAULT_JOINT_MAP = {
    'base': 5,
    'shoulder': 6,
    'elbow': 7,
    'wrist': 8,
    'claw': 10,
}


class ChassisController:
    """Simulated chassis - mimics hardware.chassis.ChassisController."""

    def __init__(self, robot_id, max_speed=0.25, sim=None,
                 locomotion_mode='velocity', wheel_joint_indices=None,
                 wheel_radius=0.03, speed_scale=2.0, wheel_direction_sign=-1.0):
        """
        Initialize simulated chassis.

        Args:
            robot_id: PyBullet robot body ID.
            max_speed: Maximum motor speed (0.0 to 1.0).
            sim: Optional SimulationCore instance (required for 'wheels' mode
                joint discovery and physics stepping).
            locomotion_mode: 'velocity' (default; sets base velocity directly)
                or 'wheels' (drive wheel joints via velocity control). 'wheels'
                requires ``wheel_joint_indices`` or a ``sim`` with discovered
                wheel joints.
            wheel_joint_indices: List of wheel joint indices. If None and
                ``sim`` is provided, discovered from the URDF.
            wheel_radius: Wheel radius in meters (used for 'wheels' mode).
            speed_scale: Linear velocity scale factor used in 'velocity' mode
                to match real-robot speed.
            wheel_direction_sign: Sign applied to wheel angular velocity in
                'wheels' mode so that ``forward()`` moves the robot in its
                forward direction. Default -1.0 matches the jetank.urdf wheel
                axis orientation.
        """
        self.robot_id = robot_id
        self.max_speed = max_speed
        self.left_speed = 0.0
        self.right_speed = 0.0

        # Track current motor values (for get_motor_values())
        self.left_value = 0.0
        self.right_value = 0.0

        # Differential drive parameters (4-wheel skid-steer)
        self.wheel_base = 0.19  # Distance between tracks (19cm width)
        self.max_force = 10.0  # Maximum motor force

        self.locomotion_mode = locomotion_mode
        self.speed_scale = speed_scale
        self.wheel_radius = wheel_radius
        self.wheel_direction_sign = wheel_direction_sign
        self.sim = sim

        if wheel_joint_indices is not None:
            self.wheel_joint_indices = list(wheel_joint_indices)
        elif sim is not None:
            self.wheel_joint_indices = sim.get_wheel_joint_indices()
        else:
            self.wheel_joint_indices = []

        # Group wheel joints by side. URDF names: wheel_fl, wheel_fr,
        # wheel_rl, wheel_rr. Discover left/right by re-reading joint names.
        self._wheel_left = []
        self._wheel_right = []
        self._group_wheels_by_side()

        if self.locomotion_mode == 'wheels' and not self._wheel_left and not self._wheel_right:
            logger.warning("locomotion_mode='wheels' but no wheel joints found; "
                           "falling back to 'velocity' mode")
            self.locomotion_mode = 'velocity'

    def _group_wheels_by_side(self):
        if self.sim is None or not self.wheel_joint_indices:
            # Without sim we can't read joint names; assume ordering
            # [fl, fr, rl, rr] -> left=[0,2], right=[1,3]
            if len(self.wheel_joint_indices) >= 4:
                self._wheel_left = [self.wheel_joint_indices[0], self.wheel_joint_indices[2]]
                self._wheel_right = [self.wheel_joint_indices[1], self.wheel_joint_indices[3]]
            return
        for idx in self.wheel_joint_indices:
            info = p.getJointInfo(self.sim.robot_id, idx)
            name = info[1].decode('utf-8')
            # Joint names look like 'wheel_fl_joint', 'wheel_rr_joint', etc.
            # The side token is the segment between 'wheel_' and '_joint'.
            token = name
            if token.startswith('wheel_'):
                token = token[len('wheel_'):]
            if token.endswith('_joint'):
                token = token[:-len('_joint')]
            if token.endswith('l'):
                self._wheel_left.append(idx)
            elif token.endswith('r'):
                self._wheel_right.append(idx)
            else:
                # Unknown side; default to right so it still gets driven.
                self._wheel_right.append(idx)

    def set_motors(self, left, right):
        """
        Set motor speeds for differential drive.

        Args:
            left: Left motor speed (-1.0 to 1.0).
            right: Right motor speed (-1.0 to 1.0).
        """
        # Clamp speeds
        self.left_speed = float(np.clip(left, -self.max_speed, self.max_speed))
        self.right_speed = float(np.clip(right, -self.max_speed, self.max_speed))

        # Track current values
        self.left_value = self.left_speed
        self.right_value = self.right_speed

        if self.locomotion_mode == 'wheels' and (self._wheel_left or self._wheel_right):
            self._apply_wheel_velocities()
        else:
            self._apply_base_velocity()

    def _apply_base_velocity(self):
        """Velocity mode: set base linear/angular velocity directly (legacy)."""
        linear_vel = (self.left_speed + self.right_speed) / 2.0
        angular_vel = (self.right_speed - self.left_speed) / self.wheel_base

        _, orn = p.getBasePositionAndOrientation(self.robot_id)
        euler = p.getEulerFromQuaternion(orn)
        yaw = euler[2]

        vel_x = linear_vel * np.cos(yaw) * self.speed_scale
        vel_y = linear_vel * np.sin(yaw) * self.speed_scale

        p.resetBaseVelocity(
            self.robot_id,
            linearVelocity=[vel_x, vel_y, 0],
            angularVelocity=[0, 0, angular_vel * self.speed_scale]
        )

    def _apply_wheel_velocities(self):
        """Wheels mode: drive wheel joints via velocity control (realistic)."""
        # Convert motor value (-1..1) to wheel angular velocity (rad/s).
        # linear speed at wheel contact = motor_value * speed_scale (m/s)
        # wheel angular vel = linear / radius
        left_ang = (self.left_speed * self.speed_scale) / self.wheel_radius
        right_ang = (self.right_speed * self.speed_scale) / self.wheel_radius
        left_ang *= self.wheel_direction_sign
        right_ang *= self.wheel_direction_sign

        for idx in self._wheel_left:
            p.setJointMotorControl2(
                self.robot_id, idx, p.VELOCITY_CONTROL,
                targetVelocity=left_ang, force=self.max_force
            )
        for idx in self._wheel_right:
            p.setJointMotorControl2(
                self.robot_id, idx, p.VELOCITY_CONTROL,
                targetVelocity=right_ang, force=self.max_force
            )

    def forward(self, speed=0.2):
        """Move forward."""
        self.set_motors(speed, speed)

    def backward(self, speed=0.2):
        """Move backward."""
        self.set_motors(-speed, -speed)

    def turn_left(self, speed=0.15):
        """Turn left."""
        self.set_motors(-speed, speed)

    def turn_right(self, speed=0.15):
        """Turn right."""
        self.set_motors(speed, -speed)

    def stop(self):
        """Stop all motors."""
        self.set_motors(0, 0)

    def get_motor_values(self):
        """Get current motor values."""
        return (self.left_value, self.right_value)


class ArmController:
    """Simulated 4-DOF arm - mimics hardware.arm.ArmController."""

    # Pose names accepted by move_to_pose() as strings.
    _POSE_NAMES = ('home', 'pickup', 'carry', 'deposit')

    def __init__(self, robot_id, config=None, sim=None, joint_map=None):
        """
        Initialize simulated arm.

        Args:
            robot_id: PyBullet robot body ID.
            config: Configuration dict with arm_poses.
            sim: Optional SimulationCore instance (used for stepping physics
                during pickup/deposit sequences and for ball grasping).
            joint_map: Optional role -> joint index map (e.g. from
                ``SimulationCore.get_joint_map()``). Falls back to hardcoded
                defaults matching the original jetank.urdf.
        """
        self.robot_id = robot_id
        self.config = config or {}
        self.sim = sim

        self.joint_indices = dict(_DEFAULT_JOINT_MAP)
        if joint_map:
            # Merge discovered map over defaults (keep any role that was found)
            for role, idx in joint_map.items():
                if idx is not None:
                    self.joint_indices[role] = idx

        # Claw state (gripper in hardware terminology)
        self.claw_open_angle = 0.0       # 0 rad = open
        self.claw_closed_angle = -1.05   # -60 deg = closed (hook down)

        # Get poses from config
        poses = self.config.get('arm_poses', {})
        self.pose_home = poses.get('home', [0, 0, 0, 0])
        self.pose_pickup = poses.get('pickup', [0, -35, -55, -25])
        self.pose_carry = poses.get('carry', [0, 15, 25, 50])
        self.pose_deposit = poses.get('deposit', [0, 35, 35, 35])

        # Motion parameters (match hardware)
        self.default_speed = 150  # Servo speed (not used in sim but kept for API)
        self.slow_speed = 80      # Slow speed for precise movements

        # Current pose tracking
        self.current_pose = list(self.pose_home)

        # Steps to wait between sub-actions in pickup/deposit sequences.
        # Each step is 1/240 s; 240 steps ~ 1 second of sim time.
        self._settle_steps = 240

    def _degrees_to_radians(self, angles):
        """Convert list of angles from degrees to radians."""
        return [np.deg2rad(a) for a in angles]

    def _resolve_pose(self, pose):
        """Resolve a pose argument (name string or list) to a list of angles."""
        if isinstance(pose, str):
            key = f'pose_{pose}'
            if not hasattr(self, key):
                raise ValueError(f"Unknown pose name: {pose!r}. "
                                 f"Expected one of {self._POSE_NAMES}.")
            return list(getattr(self, key))
        return list(pose)

    def set_joint_angles(self, angles, speed=1.0):
        """
        Set arm joint angles.

        Args:
            angles: [base, shoulder, elbow, wrist] in degrees.
            speed: Movement speed (not used in simulation).
        """
        radians = self._degrees_to_radians(angles)
        joint_names = ['base', 'shoulder', 'elbow', 'wrist']

        for i, name in enumerate(joint_names):
            joint_idx = self.joint_indices.get(name)
            if joint_idx is None:
                logger.warning("No joint index for role %r; skipping", name)
                continue
            p.setJointMotorControl2(
                self.robot_id,
                joint_idx,
                p.POSITION_CONTROL,
                targetPosition=radians[i],
                force=50
            )

    def gripper_open(self):
        """Open gripper (hardware-compatible name)."""
        try:
            idx = self.joint_indices.get('claw')
            if idx is None:
                logger.warning("No claw joint index; gripper_open no-op")
                return True
            p.setJointMotorControl2(
                self.robot_id,
                idx,
                p.POSITION_CONTROL,
                targetPosition=self.claw_open_angle,
                force=10
            )
            if self.sim is not None:
                self.sim.detach_ball()
            return True
        except Exception as e:
            logger.error("Gripper open failed: %s", e)
            return False

    def gripper_close(self):
        """Close gripper to grip (hardware-compatible name)."""
        try:
            idx = self.joint_indices.get('claw')
            if idx is None:
                logger.warning("No claw joint index; gripper_close no-op")
                return True
            p.setJointMotorControl2(
                self.robot_id,
                idx,
                p.POSITION_CONTROL,
                targetPosition=self.claw_closed_angle,
                force=10
            )
            self._try_grasp_contacted_ball()
            return True
        except Exception as e:
            logger.error("Gripper close failed: %s", e)
            return False

    def move_to_pose(self, pose, speed=None):
        """
        Move arm to a predefined pose (hardware-compatible signature).

        Args:
            pose: Either a list of 4 angles [base, shoulder, elbow, wrist] in
                degrees, or a pose name string ('home', 'pickup', 'carry',
                'deposit').
            speed: Servo speed (ignored in simulation, kept for API
                compatibility).

        Returns:
            True if successful.
        """
        if speed is None:
            speed = self.default_speed

        try:
            angles = self._resolve_pose(pose)
            self.set_joint_angles(angles)
            self.current_pose = list(angles)  # Track current pose
            return True
        except Exception as e:
            logger.error("Arm movement failed: %s", e)
            return False

    def home(self):
        """Move to home position."""
        return self.move_to_pose(self.pose_home)

    def move_base(self, angle, speed=None):
        """Move base servo only."""
        if speed is None:
            speed = self.default_speed
        try:
            radians = np.deg2rad(angle)
            idx = self.joint_indices.get('base')
            if idx is None:
                logger.warning("No base joint index; move_base no-op")
                return True
            p.setJointMotorControl2(
                self.robot_id, idx, p.POSITION_CONTROL,
                targetPosition=radians, force=50
            )
            self.current_pose[0] = angle
            return True
        except Exception as e:
            logger.error("Base movement failed: %s", e)
            return False

    def move_shoulder(self, angle, speed=None):
        """Move shoulder servo only."""
        if speed is None:
            speed = self.default_speed
        try:
            radians = np.deg2rad(angle)
            idx = self.joint_indices.get('shoulder')
            if idx is None:
                logger.warning("No shoulder joint index; move_shoulder no-op")
                return True
            p.setJointMotorControl2(
                self.robot_id, idx, p.POSITION_CONTROL,
                targetPosition=radians, force=50
            )
            self.current_pose[1] = angle
            return True
        except Exception as e:
            logger.error("Shoulder movement failed: %s", e)
            return False

    def move_elbow(self, angle, speed=None):
        """Move elbow servo only."""
        if speed is None:
            speed = self.default_speed
        try:
            radians = np.deg2rad(angle)
            idx = self.joint_indices.get('elbow')
            if idx is None:
                logger.warning("No elbow joint index; move_elbow no-op")
                return True
            p.setJointMotorControl2(
                self.robot_id, idx, p.POSITION_CONTROL,
                targetPosition=radians, force=50
            )
            self.current_pose[2] = angle
            return True
        except Exception as e:
            logger.error("Elbow movement failed: %s", e)
            return False

    def emergency_stop(self):
        """Stop all arm movement (return to home)."""
        return self.home()

    def get_current_pose(self):
        """Get current arm pose."""
        return self.current_pose.copy()

    def _step_settle(self, steps=None):
        """Advance the simulation to let arm motion settle."""
        if self.sim is None:
            return
        n = steps if steps is not None else self._settle_steps
        for _ in range(n):
            self.sim.step()

    def pickup_sequence(self):
        """
        Execute ball pickup sequence (hardware-compatible).

        Mirrors hardware.arm.ArmController.pickup_sequence: open gripper ->
        move to pickup -> close gripper -> lift to carry. In simulation, each
        sub-action is followed by physics steps so the arm visibly moves. If a
        ``sim`` with ball-grasping support is attached, the closest ball in
        contact with the robot is attached to the gripper when it closes.

        Returns:
            True if successful.
        """
        logger.info("Pickup sequence starting...")

        # 1. Open gripper
        if not self.gripper_open():
            return False
        self._step_settle(int(self._settle_steps * 0.3))

        # 2. Move to pickup position (lower arm)
        if not self.move_to_pose(self.pose_pickup, speed=self.slow_speed):
            return False
        self._step_settle(self._settle_steps)

        # 3. Close gripper (and optionally attach a contacted ball)
        if not self.gripper_close():
            return False
        self._step_settle(int(self._settle_steps * 0.5))
        self._try_grasp_contacted_ball()

        # 4. Lift to carry position
        if not self.move_to_pose(self.pose_carry, speed=self.default_speed):
            return False
        self._step_settle(self._settle_steps)

        logger.info("Pickup complete!")
        return True

    def deposit_sequence(self):
        """
        Execute ball deposit sequence (hardware-compatible).

        Mirrors hardware.arm.ArmController.deposit_sequence: move to deposit
        -> open gripper (drop) -> return home. Any attached ball is released
        when the gripper opens.

        Returns:
            True if successful.
        """
        logger.info("Deposit sequence starting...")

        # 1. Move to deposit position (over basket)
        if not self.move_to_pose(self.pose_deposit, speed=self.default_speed):
            return False
        self._step_settle(self._settle_steps)

        # 2. Open gripper (drop ball) and release any grasp constraint
        if not self.gripper_open():
            return False
        if self.sim is not None:
            self.sim.detach_ball()
        self._step_settle(int(self._settle_steps * 0.5))

        # 3. Return to home
        if not self.home():
            return False
        self._step_settle(self._settle_steps)

        logger.info("Deposit complete!")
        return True

    def _try_grasp_contacted_ball(self):
        """Attach the nearest ball to the gripper when it closes.

        Uses contact detection first, then falls back to proximity-based
        attachment (within a small radius of the gripper link). The
        proximity fallback makes grasping usable without precise gripper
        geometry tuning.
        """
        if self.sim is None:
            return
        ball_id = self.sim.check_ball_contact(self.sim.robot_id)
        if ball_id is None:
            # Proximity fallback: nearest ball to the gripper link
            link_index = self.joint_indices.get('claw')
            if link_index is None:
                link_index = self.joint_indices.get('wrist')
            if link_index is not None:
                ball_id = self.sim.find_nearest_ball_to_link(link_index,
                                                             max_distance=0.10)
        if ball_id is None:
            # Coarser pickup-zone fallback. This keeps the sim useful even
            # though the URDF hook geometry is only approximate.
            ball_id = self.sim.find_nearest_ball_to_robot_front(max_distance=0.18)
        if ball_id is not None:
            self.sim.attach_ball_to_gripper(ball_id)

    def calibrate_pickup_height(self, test_angles):
        """
        Calibration helper (no-op in simulation).

        Args:
            test_angles: List of shoulder angles to test.

        Returns:
            None
        """
        logger.info("Calibration not needed in simulation")
        return None


class CameraController:
    """Simulated camera - mimics hardware.camera.CameraController."""

    def __init__(self, config=None, robot_id=None, sim=None, renderer='auto'):
        """
        Initialize simulated camera (hardware-compatible signature).

        Args:
            config: Optional configuration dict.
            robot_id: PyBullet robot body ID (simulation-specific).
            sim: Optional SimulationCore instance (used for renderer preference
                and shared rendering helper).
            renderer: 'auto' | 'opengl' | 'tiny' (used when ``sim`` is None).
        """
        # Camera parameters
        if config and 'camera' in config:
            cam_config = config['camera']
            self.width = cam_config.get('width', 320)
            self.height = cam_config.get('height', 240)
            self.fps = cam_config.get('fps', 30)
        else:
            self.width = 320
            self.height = 240
            self.fps = 30

        # Pan/tilt servo IDs (for API compatibility)
        if config and 'servos' in config:
            servo_config = config['servos']
            self.pan_id = servo_config.get('pan', 1)
            self.tilt_id = servo_config.get('tilt', 5)
        else:
            self.pan_id = 1
            self.tilt_id = 5

        # Simulation-specific
        self.robot_id = robot_id
        self.sim = sim

        # FOV: prefer simulation config, then camera config, then default 160.
        sim_config = (config or {}).get('simulation', {}) or {}
        self.fov = sim_config.get('camera_fov',
                                  (config or {}).get('camera', {}).get('fov', 160))
        self.renderer_pref = sim_config.get('renderer', renderer)

        # Camera instance (simulated)
        self.camera = None
        self.camera_source = 'pybullet'

        # Current pan/tilt angles
        self.pan_angle = 0
        self.tilt_angle = 0

    def read(self):
        """
        Capture frame from simulated camera.

        Returns:
            BGR image as numpy array (OpenCV format), or None if no robot.
        """
        if self.robot_id is None:
            return None

        pos, orn = p.getBasePositionAndOrientation(self.robot_id)
        euler = p.getEulerFromQuaternion(orn)

        # Camera position (on top of robot, slightly forward)
        cam_pos = [
            pos[0] + 0.10 * np.cos(euler[2]),
            pos[1] + 0.10 * np.sin(euler[2]),
            pos[2] + 0.12
        ]

        # Camera looks forward and slightly down. Hardware tilt convention uses
        # negative angles for looking down, so subtract tilt from the base
        # downward pitch.
        yaw = euler[2] + np.deg2rad(self.pan_angle)
        pitch = np.deg2rad(12 - self.tilt_angle)

        target_dist = 1.0
        target = [
            cam_pos[0] + target_dist * np.cos(yaw),
            cam_pos[1] + target_dist * np.sin(yaw),
            cam_pos[2] - target_dist * np.sin(pitch)
        ]

        rgb, _ = render_camera(cam_pos, target, self.width, self.height,
                               self.fov, renderer=self.renderer_pref)

        # Convert RGB -> BGR (OpenCV format). Imported lazily so the module
        # can be imported in environments without OpenCV (e.g. CI for the
        # core smoke tests).
        try:
            import cv2  # noqa: WPS433
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        except Exception:
            bgr = rgb[:, :, ::-1].copy()
        return bgr

    def initialize(self):
        """
        Initialize camera (hardware-compatible method).
        In simulation, camera is always ready.

        Returns:
            True if successful.
        """
        logger.info("PyBullet Camera initialized (%dx%d)", self.width, self.height)
        return True

    def release(self):
        """Release camera resources (no-op in simulation)."""
        pass

    def set_pan(self, angle, speed=150):
        """
        Set pan angle (hardware-compatible signature).

        Args:
            angle: Pan angle in degrees (-90 to +90).
            speed: Servo speed (ignored in simulation).

        Returns:
            True if successful.
        """
        angle = max(-90, min(90, angle))
        self.pan_angle = angle
        return True

    def get_pan(self):
        """Return current pan angle in degrees."""
        return self.pan_angle

    def set_tilt(self, angle, speed=150):
        """
        Set tilt angle (hardware-compatible signature).

        Args:
            angle: Tilt angle in degrees (-60 to +60).
            speed: Servo speed (ignored in simulation).

        Returns:
            True if successful.
        """
        angle = max(-60, min(60, angle))
        self.tilt_angle = angle
        return True

    def center(self):
        """Center pan/tilt servos."""
        self.set_pan(0)
        self.set_tilt(0)
        return True

    def look_down(self):
        """Tilt camera down for ground view."""
        self.set_tilt(-30)
        return True

    def look_forward(self):
        """Tilt camera forward for horizon view."""
        self.set_tilt(0)
        return True

    def get_frame_size(self):
        """Get frame dimensions."""
        return (self.width, self.height)


def create_sim_hardware(robot_id, config, sim=None):
    """
    Factory function to create all simulated hardware interfaces.

    Args:
        robot_id: PyBullet robot body ID.
        config: Configuration dictionary.
        sim: Optional SimulationCore instance. When provided, hardware
            controllers get access to discovered joint maps, physics stepping
            for arm sequences, ball grasping, and renderer preferences.

    Returns:
        (chassis, arm, camera) tuple.
    """
    sim_config = (config or {}).get('simulation', {}) or {}
    locomotion_mode = sim_config.get('locomotion_mode', 'velocity')
    renderer = sim_config.get('renderer', 'auto')

    joint_map = sim.get_joint_map() if sim is not None else None
    wheel_indices = sim.get_wheel_joint_indices() if sim is not None else None

    chassis = ChassisController(
        robot_id,
        max_speed=config.get('motors', {}).get('max_speed', 0.25),
        sim=sim,
        locomotion_mode=locomotion_mode,
        wheel_joint_indices=wheel_indices,
    )
    arm = ArmController(robot_id, config=config, sim=sim, joint_map=joint_map)
    camera = CameraController(config=config, robot_id=robot_id, sim=sim, renderer=renderer)

    return chassis, arm, camera
