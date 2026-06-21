"""
Simulated Hardware Interfaces
Drop-in replacements for hardware.chassis, hardware.arm, hardware.camera

These classes have IDENTICAL APIs to the real hardware classes, allowing
seamless switching between simulation and real robot with a single import change.
"""

import pybullet as p
import numpy as np
import cv2


class ChassisController:
    """Simulated chassis - mimics hardware.chassis.ChassisController"""
    
    def __init__(self, robot_id, max_speed=0.25):
        """
        Initialize simulated chassis
        
        Args:
            robot_id: PyBullet robot body ID
            max_speed: Maximum motor speed (0.0 to 1.0)
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
        
    def set_motors(self, left, right):
        """
        Set motor speeds for differential drive
        
        Args:
            left: Left motor speed (-1.0 to 1.0)
            right: Right motor speed (-1.0 to 1.0)
        """
        # Clamp speeds
        self.left_speed = np.clip(left, -self.max_speed, self.max_speed)
        self.right_speed = np.clip(right, -self.max_speed, self.max_speed)
        
        # Track current values
        self.left_value = self.left_speed
        self.right_value = self.right_speed
        
        # Apply velocity to robot base
        # Convert differential drive to linear and angular velocity
        linear_vel = (self.left_speed + self.right_speed) / 2.0
        angular_vel = (self.right_speed - self.left_speed) / self.wheel_base
        
        # Get current orientation
        _, orn = p.getBasePositionAndOrientation(self.robot_id)
        euler = p.getEulerFromQuaternion(orn)
        yaw = euler[2]
        
        # Convert to world frame velocities
        vel_x = linear_vel * np.cos(yaw) * 2.0  # Scale factor for realistic speed
        vel_y = linear_vel * np.sin(yaw) * 2.0
        
        # Apply velocity
        p.resetBaseVelocity(
            self.robot_id,
            linearVelocity=[vel_x, vel_y, 0],
            angularVelocity=[0, 0, angular_vel * 2.0]
        )
        
    def forward(self, speed=0.2):
        """Move forward"""
        self.set_motors(speed, speed)
        
    def backward(self, speed=0.2):
        """Move backward"""
        self.set_motors(-speed, -speed)
        
    def turn_left(self, speed=0.15):
        """Turn left"""
        self.set_motors(-speed, speed)
        
    def turn_right(self, speed=0.15):
        """Turn right"""
        self.set_motors(speed, -speed)
        
    def stop(self):
        """Stop all motors"""
        self.set_motors(0, 0)
    
    def get_motor_values(self):
        """Get current motor values."""
        return (self.left_value, self.right_value)


class ArmController:
    """Simulated 4-DOF arm - mimics hardware.arm.ArmController"""
    
    def __init__(self, robot_id, config=None):
        """
        Initialize simulated arm
        
        Args:
            robot_id: PyBullet robot body ID
            config: Configuration dict with arm_poses
        """
        self.robot_id = robot_id
        self.config = config or {}
        
        # Joint indices (from URDF)
        # Wheels: 0-3 (continuous joints)
        # Camera: 4 (fixed joint)
        # Arm joints: 5-8 (revolute joints)
        # Gripper base: 9 (fixed joint)
        # Claw: 10 (revolute joint)
        self.joint_indices = {
            'base': 5,      # arm_base_joint (pan)
            'shoulder': 6,  # arm_shoulder_joint
            'elbow': 7,     # arm_elbow_joint
            'wrist': 8,     # arm_wrist_joint
            'claw': 10      # claw_joint (hook open/close)
        }
        
        # Claw state (gripper in hardware terminology)
        self.claw_open_angle = 0.0      # 0° = open
        self.claw_closed_angle = -1.05  # -60° = closed (hook down)
        
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
        self.current_pose = self.pose_home.copy()
        
    def _degrees_to_radians(self, angles):
        """Convert list of angles from degrees to radians"""
        return [np.deg2rad(a) for a in angles]
        
    def set_joint_angles(self, angles, speed=1.0):
        """
        Set arm joint angles
        
        Args:
            angles: [base, shoulder, elbow, wrist] in degrees
            speed: Movement speed (not used in simulation)
        """
        radians = self._degrees_to_radians(angles)
        joint_names = ['base', 'shoulder', 'elbow', 'wrist']
        
        for i, name in enumerate(joint_names):
            joint_idx = self.joint_indices[name]
            p.setJointMotorControl2(
                self.robot_id,
                joint_idx,
                p.POSITION_CONTROL,
                targetPosition=radians[i],
                force=50
            )
            
    def gripper_open(self):
        """Open gripper (hardware-compatible name)"""
        try:
            p.setJointMotorControl2(
                self.robot_id,
                self.joint_indices['claw'],
                p.POSITION_CONTROL,
                targetPosition=self.claw_open_angle,
                force=10
            )
            return True
        except Exception as e:
            print(f"Gripper open failed: {e}")
            return False
    
    def gripper_close(self):
        """Close gripper to grip (hardware-compatible name)"""
        try:
            p.setJointMotorControl2(
                self.robot_id,
                self.joint_indices['claw'],
                p.POSITION_CONTROL,
                targetPosition=self.claw_closed_angle,
                force=10
            )
            return True
        except Exception as e:
            print(f"Gripper close failed: {e}")
            return False
            
    def move_to_pose(self, pose, speed=None):
        """
        Move arm to a predefined pose (hardware-compatible signature).
        
        Args:
            pose: List of 4 angles [base, shoulder, elbow, wrist/gripper] in degrees
            speed: Servo speed (ignored in simulation, kept for API compatibility)
            
        Returns:
            True if successful
        """
        if speed is None:
            speed = self.default_speed
        
        try:
            self.set_joint_angles(pose)
            self.current_pose = list(pose)  # Track current pose
            return True
        except Exception as e:
            print(f"Arm movement failed: {e}")
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
            p.setJointMotorControl2(
                self.robot_id,
                self.joint_indices['base'],
                p.POSITION_CONTROL,
                targetPosition=radians,
                force=50
            )
            self.current_pose[0] = angle
            return True
        except Exception as e:
            print(f"Base movement failed: {e}")
            return False
    
    def move_shoulder(self, angle, speed=None):
        """Move shoulder servo only."""
        if speed is None:
            speed = self.default_speed
        
        try:
            radians = np.deg2rad(angle)
            p.setJointMotorControl2(
                self.robot_id,
                self.joint_indices['shoulder'],
                p.POSITION_CONTROL,
                targetPosition=radians,
                force=50
            )
            self.current_pose[1] = angle
            return True
        except Exception as e:
            print(f"Shoulder movement failed: {e}")
            return False
    
    def move_elbow(self, angle, speed=None):
        """Move elbow servo only."""
        if speed is None:
            speed = self.default_speed
        
        try:
            radians = np.deg2rad(angle)
            p.setJointMotorControl2(
                self.robot_id,
                self.joint_indices['elbow'],
                p.POSITION_CONTROL,
                targetPosition=radians,
                force=50
            )
            self.current_pose[2] = angle
            return True
        except Exception as e:
            print(f"Elbow movement failed: {e}")
            return False
    
    def emergency_stop(self):
        """Stop all arm movement (return to home)."""
        return self.home()
    
    def get_current_pose(self):
        """Get current arm pose."""
        return self.current_pose.copy()
    
    def pickup_sequence(self):
        """
        Execute ball pickup sequence (hardware-compatible).
        Note: In simulation, timing is handled by calling code with sim.step()
        
        Returns:
            True if successful
        """
        print("Pickup sequence starting...")
        return True
        
    def deposit_sequence(self):
        """
        Execute ball deposit sequence (hardware-compatible).
        Note: In simulation, timing is handled by calling code with sim.step()
        
        Returns:
            True if successful
        """
        print("Deposit sequence starting...")
        return True
    
    def calibrate_pickup_height(self, test_angles):
        """
        Calibration helper (no-op in simulation).
        
        Args:
            test_angles: List of shoulder angles to test
            
        Returns:
            None
        """
        print("Calibration not needed in simulation")
        return None


class CameraController:
    """Simulated camera - mimics hardware.camera.CameraController"""
    
    def __init__(self, config=None, robot_id=None):
        """
        Initialize simulated camera (hardware-compatible signature)
        
        Args:
            config: Optional configuration dict
            robot_id: PyBullet robot body ID (simulation-specific)
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
        self.fov = 160
        
        # Camera instance (simulated)
        self.camera = None
        self.camera_source = 'pybullet'
        
        # Current pan/tilt angles
        self.pan_angle = 0
        self.tilt_angle = 0
        
    def read(self):
        """
        Capture frame from simulated camera
        
        Returns:
            BGR image as numpy array (OpenCV format)
        """
        # Get robot position and orientation
        pos, orn = p.getBasePositionAndOrientation(self.robot_id)
        euler = p.getEulerFromQuaternion(orn)
        
        # Camera position (on top of robot, slightly forward)
        cam_pos = [
            pos[0] + 0.10 * np.cos(euler[2]),
            pos[1] + 0.10 * np.sin(euler[2]),
            pos[2] + 0.12
        ]
        
        # Camera looks forward and slightly down
        yaw = euler[2] + np.deg2rad(self.pan_angle)
        pitch = 0.2 + np.deg2rad(self.tilt_angle)  # Look down
        
        target_dist = 1.0
        target = [
            cam_pos[0] + target_dist * np.cos(yaw),
            cam_pos[1] + target_dist * np.sin(yaw),
            cam_pos[2] - target_dist * np.sin(pitch)
        ]
        
        # Compute view matrix
        view_matrix = p.computeViewMatrix(
            cameraEyePosition=cam_pos,
            cameraTargetPosition=target,
            cameraUpVector=[0, 0, 1]
        )
        
        # Compute projection matrix
        proj_matrix = p.computeProjectionMatrixFOV(
            fov=self.fov,
            aspect=self.width / self.height,
            nearVal=0.01,
            farVal=10.0
        )
        
        # Render image
        img_arr = p.getCameraImage(
            self.width,
            self.height,
            view_matrix,
            proj_matrix,
            renderer=p.ER_BULLET_HARDWARE_OPENGL
        )
        
        # Extract RGB and convert to BGR (OpenCV format)
        rgb = np.array(img_arr[2]).reshape(self.height, self.width, 4)[:, :, :3]
        bgr = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2BGR)
        
        return bgr
        
    def initialize(self):
        """
        Initialize camera (hardware-compatible method).
        In simulation, camera is always ready.
        
        Returns:
            True if successful
        """
        print(f"✓ PyBullet Camera initialized ({self.width}x{self.height})")
        return True
    
    def release(self):
        """Release camera resources (no-op in simulation)."""
        pass
    
    def set_pan(self, angle, speed=150):
        """
        Set pan angle (hardware-compatible signature).
        
        Args:
            angle: Pan angle in degrees (-90 to +90)
            speed: Servo speed (ignored in simulation)
            
        Returns:
            True if successful
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
            angle: Tilt angle in degrees (-60 to +60)
            speed: Servo speed (ignored in simulation)
            
        Returns:
            True if successful
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


def create_sim_hardware(robot_id, config):
    """
    Factory function to create all simulated hardware interfaces
    
    Args:
        robot_id: PyBullet robot body ID
        config: Configuration dictionary
        
    Returns:
        (chassis, arm, camera) tuple
    """
    chassis = ChassisController(robot_id, max_speed=config.get('motors', {}).get('max_speed', 0.25))
    arm = ArmController(robot_id, config)
    camera = CameraController(config, robot_id=robot_id)
    
    return chassis, arm, camera
