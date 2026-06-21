"""
PyBullet Simulation Core
Initializes physics engine, loads models, and manages simulation loop.
"""

import logging
import os
import time

import numpy as np
import pybullet as p
import pybullet_data


logger = logging.getLogger(__name__)


# Joint name -> logical role. Used to discover joint indices from the URDF
# at runtime instead of hardcoding fragile numeric indices.
_JOINT_NAME_ROLES = {
    'arm_base_joint': 'base',
    'arm_shoulder_joint': 'shoulder',
    'arm_elbow_joint': 'elbow',
    'arm_wrist_joint': 'wrist',
    'claw_joint': 'claw',
    'gripper_joint': 'claw',  # alternate naming
}

_WHEEL_NAME_PREFIXES = ('wheel_',)


def _renderer_choice(preference='auto'):
    """Pick a PyBullet renderer, falling back gracefully on headless systems."""
    opengl = getattr(p, 'ER_BULLET_HARDWARE_OPENGL', None)
    tiny = getattr(p, 'ER_TINY_RENDERER', None)
    if preference == 'opengl':
        return opengl if opengl is not None else tiny
    if preference == 'tiny':
        return tiny if tiny is not None else opengl
    # auto: prefer OpenGL, fall back to Tiny
    return opengl if opengl is not None else tiny


class SimulationCore:
    """Core simulation manager for PyBullet."""

    def __init__(self, gui=True, real_time=False, config=None,
                 locomotion_mode='velocity', renderer='auto', verbose=False):
        """
        Initialize PyBullet simulation.

        Args:
            gui: Show PyBullet GUI window.
            real_time: Run at real-time speed (vs. as fast as possible).
            config: Optional configuration dict. When provided, simulation
                defaults (locomotion_mode, renderer, ball spawn seed, ...) are
                read from ``config['simulation']`` unless overridden by the
                explicit kwargs above.
            locomotion_mode: 'velocity' (default, stable; sets base velocity
                directly) or 'wheels' (drive wheel joints via velocity control).
            renderer: 'auto' | 'opengl' | 'tiny' for camera rendering.
            verbose: Print per-joint info when loading the robot.
        """
        self.gui = gui
        self.real_time = real_time
        self.physics_client = None
        self.robot_id = None
        self.arena_id = None
        self.ball_ids = []
        self.time_step = 1.0 / 240.0  # 240 Hz physics

        sim_config = {}
        if config:
            sim_config = config.get('simulation', {}) or {}

        self.locomotion_mode = sim_config.get('locomotion_mode', locomotion_mode)
        self.renderer_pref = sim_config.get('renderer', renderer)
        self.ball_spawn_seed = sim_config.get('ball_spawn_seed', 42)
        self.verbose = verbose

        # Joint discovery results (populated by load_robot)
        self.joint_map = {}        # role name -> joint index
        self.wheel_joint_indices = []
        self.num_joints = 0

        # Start pose (recorded so reset() can restore it)
        self._start_pos = [0, 0, 0.15]
        self._start_orientation = [0, 0, 0]

        # Ball grasp state
        self.attached_ball_id = None
        self._grasp_constraint_id = None
        self.deposited_ball_ids = set()
        self.basket_position = (0.9, 0.875)
        self.basket_deposit_radius = 0.23

        # Get paths
        self.base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.models_path = os.path.join(self.base_path, 'simulation', 'models')

    def initialize(self):
        """Initialize PyBullet physics engine."""
        if self.gui:
            self.physics_client = p.connect(p.GUI)
        else:
            self.physics_client = p.connect(p.DIRECT)

        # Set additional search path for PyBullet data
        p.setAdditionalSearchPath(pybullet_data.getDataPath())

        # Configure physics
        p.setGravity(0, 0, -9.81)
        p.setTimeStep(self.time_step)
        p.setRealTimeSimulation(0)  # We'll step manually

        logger.info("PyBullet initialized (GUI: %s, locomotion: %s)",
                    self.gui, self.locomotion_mode)

    def load_arena(self):
        """Load arena model (floor, walls, obstacles, basket)."""
        arena_urdf = os.path.join(self.models_path, 'arena.urdf')

        if not os.path.exists(arena_urdf):
            raise FileNotFoundError(f"Arena URDF not found: {arena_urdf}")

        # Load arena at ground level
        self.arena_id = p.loadURDF(
            arena_urdf,
            basePosition=[0, 0, 0],
            baseOrientation=[0, 0, 0, 1],
            useFixedBase=True
        )

        logger.info("Arena loaded (ID: %s)", self.arena_id)

    def _discover_joints(self):
        """Build joint_map (role -> index) and wheel_joint_indices from URDF."""
        self.joint_map = {}
        self.wheel_joint_indices = []
        for i in range(self.num_joints):
            joint_info = p.getJointInfo(self.robot_id, i)
            name = joint_info[1].decode('utf-8')
            if name in _JOINT_NAME_ROLES:
                role = _JOINT_NAME_ROLES[name]
                # Don't overwrite an already-discovered role (e.g. gripper alias)
                if role not in self.joint_map:
                    self.joint_map[role] = i
            if any(name.startswith(prefix) for prefix in _WHEEL_NAME_PREFIXES):
                self.wheel_joint_indices.append(i)

        # Fallbacks for older URDFs that may not have a claw_joint
        if 'claw' not in self.joint_map:
            self.joint_map['claw'] = self.joint_map.get('wrist')

        if self.verbose:
            for i in range(self.num_joints):
                joint_info = p.getJointInfo(self.robot_id, i)
                logger.info("  Joint %d: %s (Type: %s)",
                            i, joint_info[1].decode('utf-8'), joint_info[2])
        logger.debug("Discovered joint map: %s", self.joint_map)
        logger.debug("Wheel joint indices: %s", self.wheel_joint_indices)

    def load_robot(self, start_pos=None, start_orientation=None):
        """
        Load robot model.

        Args:
            start_pos: [x, y, z] starting position in meters (default [0,0,0.15]).
            start_orientation: [roll, pitch, yaw] in radians (default [0,0,0]).
        """
        if start_pos is None:
            start_pos = [0, 0, 0.15]
        if start_orientation is None:
            start_orientation = [0, 0, 0]

        # Record for reset()
        self._start_pos = list(start_pos)
        self._start_orientation = list(start_orientation)

        robot_urdf = os.path.join(self.models_path, 'jetank.urdf')

        if not os.path.exists(robot_urdf):
            raise FileNotFoundError(f"Robot URDF not found: {robot_urdf}")

        # Convert orientation to quaternion
        quat = p.getQuaternionFromEuler(start_orientation)

        # Load robot
        self.robot_id = p.loadURDF(
            robot_urdf,
            basePosition=start_pos,
            baseOrientation=quat,
            useFixedBase=False
        )

        # Get joint info
        self.num_joints = p.getNumJoints(self.robot_id)
        self._discover_joints()
        logger.info("Robot loaded (ID: %s, Joints: %d)", self.robot_id, self.num_joints)

        return self.robot_id

    def get_joint_map(self):
        """Return discovered role -> joint index map (e.g. {'base': 5, ...})."""
        return dict(self.joint_map)

    def get_wheel_joint_indices(self):
        """Return list of wheel joint indices discovered from the URDF."""
        return list(self.wheel_joint_indices)

    def spawn_balls(self, num_balls=22, colors=None, seed=None):
        """
        Spawn colored balls randomly in arena.

        Args:
            num_balls: Number of balls to spawn.
            colors: List of color names to distribute (default blue/red/silver).
            seed: RNG seed for reproducible positions. Defaults to
                ``self.ball_spawn_seed``.
        """
        if colors is None:
            colors = ['blue', 'red', 'silver']
        if seed is None:
            seed = self.ball_spawn_seed

        # Color mapping (RGB)
        color_map = {
            'blue': [0.2, 0.4, 1.0, 1],
            'red': [1.0, 0.2, 0.2, 1],
            'silver': [0.8, 0.8, 0.8, 1]
        }

        ball_radius = 0.02  # 2cm radius (4cm diameter)
        rng = np.random.default_rng(seed)

        # Obstacle footprints (world frame) to avoid spawning inside crates.
        # Matches arena.urdf: ground is centered at (0.9, 0.875); obstacle
        # origins are relative to ground.
        obstacles = [
            {'center': (0.9 - 0.40, 0.875 + 0.40), 'half': (0.15, 0.10)},  # 0.30x0.20
            {'center': (0.9 + 0.40, 0.875 - 0.40), 'half': (0.20, 0.15)},  # 0.40x0.30
        ]
        basket_x, basket_y = 0.9, 0.875
        min_basket_dist = 0.25
        min_ball_dist = 2 * ball_radius + 0.005

        spawned = []
        attempts = 0
        max_attempts = num_balls * 50

        while len(spawned) < num_balls and attempts < max_attempts:
            attempts += 1
            x = float(rng.uniform(0.2, 1.6))
            y = float(rng.uniform(0.2, 1.5))

            # Avoid basket
            if np.hypot(x - basket_x, y - basket_y) < min_basket_dist:
                continue
            # Avoid obstacles
            inside_obstacle = False
            for obs in obstacles:
                if (abs(x - obs['center'][0]) < obs['half'][0] + ball_radius and
                        abs(y - obs['center'][1]) < obs['half'][1] + ball_radius):
                    inside_obstacle = True
                    break
            if inside_obstacle:
                continue
            # Avoid other balls
            too_close = False
            for (px, py) in spawned:
                if np.hypot(x - px, y - py) < min_ball_dist:
                    too_close = True
                    break
            if too_close:
                continue

            spawned.append((x, y))

        for i, (x, y) in enumerate(spawned):
            self.spawn_ball_at(x, y, color=colors[i % len(colors)])

        if len(spawned) < num_balls:
            logger.warning("Only spawned %d/%d balls (could not find free space)",
                           len(spawned), num_balls)
        logger.info("Spawned %d balls", len(spawned))

    def spawn_ball_at(self, x, y, color='blue', radius=0.02, mass=0.005):
        """
        Spawn one colored ball at a specific world-frame arena position.

        Args:
            x: World x coordinate in meters.
            y: World y coordinate in meters.
            color: 'blue', 'red', or 'silver'.
            radius: Ball radius in meters.
            mass: Ball mass in kg.

        Returns:
            The created PyBullet body ID.
        """
        color_map = {
            'blue': [0.2, 0.4, 1.0, 1],
            'red': [1.0, 0.2, 0.2, 1],
            'silver': [0.8, 0.8, 0.8, 1],
        }
        rgba = color_map.get(color, color_map['blue'])
        z = radius + 0.01
        col_shape = p.createCollisionShape(p.GEOM_SPHERE, radius=radius)
        vis_shape = p.createVisualShape(
            p.GEOM_SPHERE,
            radius=radius,
            rgbaColor=rgba,
        )
        ball_id = p.createMultiBody(
            baseMass=mass,
            baseCollisionShapeIndex=col_shape,
            baseVisualShapeIndex=vis_shape,
            basePosition=[x, y, z],
        )
        self.ball_ids.append(ball_id)
        return ball_id

    def step(self):
        """Step physics simulation forward by one timestep."""
        p.stepSimulation()

        if self.real_time:
            time.sleep(self.time_step)

    def reset(self):
        """Reset simulation to the initial robot pose and respawn balls."""
        # Remove all balls (and detach any grasp)
        self.detach_ball()
        for ball_id in self.ball_ids:
            p.removeBody(ball_id)
        self.ball_ids = []
        self.deposited_ball_ids.clear()

        # Reset robot to the recorded start pose
        if self.robot_id is not None:
            quat = p.getQuaternionFromEuler(self._start_orientation)
            p.resetBasePositionAndOrientation(
                self.robot_id,
                self._start_pos,
                quat
            )
            # Reset joint positions
            for i in range(self.num_joints):
                p.resetJointState(self.robot_id, i, 0)

        # Respawn balls
        self.spawn_balls()

        logger.info("Simulation reset")

    def get_robot_state(self):
        """Get current robot position and orientation."""
        if self.robot_id is None:
            return None

        pos, orn = p.getBasePositionAndOrientation(self.robot_id)
        euler = p.getEulerFromQuaternion(orn)

        return {
            'position': pos,
            'orientation': euler,
            'quaternion': orn
        }

    def check_collision(self, body_a, body_b):
        """Check if two bodies are in collision."""
        contact_points = p.getContactPoints(body_a, body_b)
        return len(contact_points) > 0

    def check_arm_link_collision(self, link_indices, other_body_id=None):
        """Check whether any arm link is in contact with another body.

        Args:
            link_indices: List of robot link indices to check (e.g. arm joints).
            other_body_id: Body ID to check against.  If ``None``, uses the
                arena body.

        Returns:
            ``True`` if any arm link has a contact point with the other body.
        """
        if other_body_id is None:
            other_body_id = self.arena_id
        if other_body_id is None or self.robot_id is None:
            return False
        for link_idx in link_indices:
            contacts = p.getContactPoints(self.robot_id, other_body_id,
                                          linkIndexA=link_idx)
            if contacts:
                return True
        return False

    def get_ball_ids(self):
        """Return list of currently spawned ball body IDs."""
        return list(self.ball_ids)

    def check_ball_contact(self, body_id, ball_ids=None):
        """
        Return the first ball in contact with ``body_id``, or None.

        Args:
            body_id: PyBullet body to test (e.g. the robot).
            ball_ids: Optional list of ball IDs to test. Defaults to all spawned.
        """
        if ball_ids is None:
            ball_ids = self.ball_ids
        for ball_id in ball_ids:
            if p.getContactPoints(body_id, ball_id):
                return ball_id
        return None

    def find_nearest_ball_to_link(self, link_index, max_distance=0.08,
                                  ball_ids=None):
        """
        Return the ball nearest to a robot link within ``max_distance``, or None.

        Args:
            link_index: Robot link index (e.g. the gripper link). Use -1 for
                the base link.
            max_distance: Maximum distance (meters) between the link and the
                ball for a match.
            ball_ids: Optional list of ball IDs to consider. Defaults to all
                spawned balls.
        """
        if ball_ids is None:
            ball_ids = self.ball_ids
        if not ball_ids:
            return None
        try:
            link_state = p.getLinkState(self.robot_id, link_index)
            link_pos = np.array(link_state[0])
        except Exception:
            link_pos = np.array(self.get_robot_state()['position'])

        nearest = None
        nearest_dist = max_distance
        for ball_id in ball_ids:
            ball_pos = np.array(p.getBasePositionAndOrientation(ball_id)[0])
            d = float(np.linalg.norm(link_pos - ball_pos))
            if d < nearest_dist:
                nearest_dist = d
                nearest = ball_id
        return nearest

    def find_nearest_ball_to_robot_front(self, max_distance=0.18,
                                         forward_offset=0.16,
                                         lateral_tolerance=0.12,
                                         ball_ids=None):
        """
        Return a nearby ball in front of the robot pickup zone, or None.

        This complements exact gripper contact detection. The simplified URDF
        gripper is not tuned enough for reliable physical contact, so the
        pickup zone approximates the real robot's hook reach.
        """
        if ball_ids is None:
            ball_ids = self.ball_ids
        if self.robot_id is None or not ball_ids:
            return None

        pos, orn = p.getBasePositionAndOrientation(self.robot_id)
        yaw = p.getEulerFromQuaternion(orn)[2]
        forward = np.array([np.cos(yaw), np.sin(yaw), 0.0])
        lateral = np.array([-np.sin(yaw), np.cos(yaw), 0.0])
        origin = np.array(pos)
        pickup_center = origin + forward * forward_offset

        nearest = None
        nearest_dist = max_distance
        for ball_id in ball_ids:
            ball_pos = np.array(p.getBasePositionAndOrientation(ball_id)[0])
            rel = ball_pos - pickup_center
            forward_error = abs(float(np.dot(rel, forward)))
            lateral_error = abs(float(np.dot(rel, lateral)))
            planar_dist = float(np.linalg.norm(rel[:2]))
            if (planar_dist < nearest_dist and
                    forward_error < max_distance and
                    lateral_error < lateral_tolerance):
                nearest = ball_id
                nearest_dist = planar_dist
        return nearest

    def attach_ball_to_gripper(self, ball_id, link_index=None):
        """
        Attach a ball to the gripper via a fixed constraint (physical grasp).

        Args:
            ball_id: Ball body ID to attach.
            link_index: Gripper link index. If None, uses the 'claw' joint's
                child link, falling back to the wrist link, then -1 (base).

        Returns:
            constraint ID, or None on failure.
        """
        if self.robot_id is None or ball_id is None:
            return None
        if self._grasp_constraint_id is not None:
            self.detach_ball()

        if link_index is None:
            for role in ('claw', 'wrist'):
                if role in self.joint_map:
                    link_index = self.joint_map[role]
                    break
            if link_index is None:
                link_index = -1

        try:
            constraint_id = p.createConstraint(
                self.robot_id, link_index,
                ball_id, -1,
                p.JOINT_FIXED,
                [0, 0, 0], [0, 0, 0],
                [0, 0, 0.02]  # attach point slightly below gripper
            )
            self.attached_ball_id = ball_id
            self._grasp_constraint_id = constraint_id
            logger.info("Attached ball %d to gripper link %d (constraint %d)",
                        ball_id, link_index, constraint_id)
            return constraint_id
        except Exception as e:  # pragma: no cover - defensive
            logger.error("Failed to attach ball: %s", e)
            return None

    def detach_ball(self):
        """Detach the currently attached ball (if any).

        If the release happens inside the basket drop zone, the ball is marked
        as deposited for simulation assertions and telemetry, and removed from
        the physics world and ``ball_ids`` so it is no longer detected.
        """
        ball_id = self.attached_ball_id
        if self._grasp_constraint_id is not None:
            deposited = False
            if ball_id is not None:
                ball_pos = p.getBasePositionAndOrientation(ball_id)[0]
                if np.hypot(ball_pos[0] - self.basket_position[0],
                            ball_pos[1] - self.basket_position[1]) <= self.basket_deposit_radius:
                    self.deposited_ball_ids.add(ball_id)
                    deposited = True
            try:
                p.removeConstraint(self._grasp_constraint_id)
            except Exception as e:  # pragma: no cover - defensive
                logger.debug("Constraint removal error: %s", e)
            self._grasp_constraint_id = None
            self.attached_ball_id = None
            if deposited and ball_id is not None:
                if ball_id in self.ball_ids:
                    self.ball_ids.remove(ball_id)
                try:
                    p.removeBody(ball_id)
                except Exception as e:  # pragma: no cover - defensive
                    logger.debug("Ball removal error: %s", e)

    def get_deposited_count(self):
        """Return the number of balls released in the basket drop zone."""
        return len(self.deposited_ball_ids)

    def get_camera_view(self, width=320, height=240, fov=160,
                        cam_pos=None, target=None):
        """
        Get camera view from robot's perspective.

        Args:
            width: Image width in pixels.
            height: Image height in pixels.
            fov: Field of view in degrees.
            cam_pos: Optional [x,y,z] camera eye position. Defaults to
                robot base + 12cm height offset.
            target: Optional [x,y,z] camera target. Defaults to a point 1m
                forward and slightly down from the camera.

        Returns:
            RGB image as numpy array (height, width, 3).
        """
        if self.robot_id is None:
            return None

        robot_state = self.get_robot_state()
        if cam_pos is None:
            cam_pos = list(robot_state['position'])
            cam_pos[2] += 0.12  # Camera height offset

        if target is None:
            yaw = robot_state['orientation'][2]
            pitch = 0.2  # Look down 0.2 radians
            target_dist = 1.0
            target = [
                cam_pos[0] + target_dist * np.cos(yaw),
                cam_pos[1] + target_dist * np.sin(yaw),
                cam_pos[2] - target_dist * np.sin(pitch)
            ]

        rgb, _ = render_camera(cam_pos, target, width, height, fov,
                               renderer=self.renderer_pref)
        return rgb

    def close(self):
        """Shutdown simulation (safe to call multiple times)."""
        if self.physics_client is not None and p.isConnected(self.physics_client):
            try:
                p.disconnect(self.physics_client)
            except Exception as e:  # pragma: no cover - defensive
                logger.debug("Disconnect error: %s", e)
            self.physics_client = None
            logger.info("Simulation closed")


def render_camera(cam_pos, target, width, height, fov,
                  near=0.01, far=10.0, renderer='auto'):
    """
    Render a PyBullet camera image.

    Args:
        cam_pos: [x, y, z] camera eye position.
        target: [x, y, z] camera target position.
        width: Image width in pixels.
        height: Image height in pixels.
        fov: Field of view in degrees.
        near: Near clipping plane.
        far: Far clipping plane.
        renderer: 'auto' | 'opengl' | 'tiny'.

    Returns:
        (rgb, depth) tuple. ``rgb`` is a uint8 array of shape (height, width, 3).
        ``depth`` is a float32 array of shape (height, width).
    """
    view_matrix = p.computeViewMatrix(
        cameraEyePosition=cam_pos,
        cameraTargetPosition=target,
        cameraUpVector=[0, 0, 1]
    )
    proj_matrix = p.computeProjectionMatrixFOV(
        fov=fov,
        aspect=width / height,
        nearVal=near,
        farVal=far
    )

    renderer_enum = _renderer_choice(renderer)
    kwargs = {}
    if renderer_enum is not None:
        kwargs['renderer'] = renderer_enum

    img_arr = p.getCameraImage(width, height, view_matrix, proj_matrix, **kwargs)

    rgb = np.array(img_arr[2]).reshape(height, width, 4)[:, :, :3].astype(np.uint8)
    depth = np.array(img_arr[3]).reshape(height, width).astype(np.float32)
    return rgb, depth


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing SimulationCore...")

    sim = SimulationCore(gui=True, real_time=True)
    sim.initialize()
    sim.load_arena()
    sim.load_robot()
    sim.spawn_balls(num_balls=22)

    print("\nRunning simulation for 5 seconds...")
    for i in range(1200):  # 5 seconds at 240 Hz
        sim.step()

        if i % 240 == 0:
            state = sim.get_robot_state()
            print(f"  t={i/240:.1f}s: pos={state['position']}")

    print("\nTest complete!")
    sim.close()
