"""
Simulated Hardware Interfaces
Drop-in replacements for hardware.chassis, hardware.arm, hardware.camera
"""

import pybullet as p
import numpy as np
import cv2


class SimChassis:
    """Simulated chassis - mimics hardware.chassis.Chassis"""
    
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


class SimArm:
    """Simulated 4-DOF arm - mimics hardware.arm.Arm"""
    
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
        
        # Claw state
        self.claw_open_angle = 0.0      # 0° = open
        self.claw_closed_angle = -1.05  # -60° = closed (hook down)
        
        # Get poses from config
        poses = self.config.get('arm_poses', {})
        self.poses = {
            'home': poses.get('home', [0, 0, 0, 0]),
            'pickup': poses.get('pickup', [0, -40, -60, 0]),
            'carry': poses.get('carry', [0, 20, 30, 90]),
            'deposit': poses.get('deposit', [0, 40, 40, 0])
        }
        
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
            
    def open_claw(self):
        """Open the hook claw"""
        p.setJointMotorControl2(
            self.robot_id,
            self.joint_indices['claw'],
            p.POSITION_CONTROL,
            targetPosition=self.claw_open_angle,
            force=10
        )
    
    def close_claw(self):
        """Close the hook claw to grip"""
        p.setJointMotorControl2(
            self.robot_id,
            self.joint_indices['claw'],
            p.POSITION_CONTROL,
            targetPosition=self.claw_closed_angle,
            force=10
        )
            
    def move_to_pose(self, pose_name):
        """Move to predefined pose"""
        if pose_name in self.poses:
            self.set_joint_angles(self.poses[pose_name])
        else:
            print(f"[SimArm] Unknown pose: {pose_name}")
            
    def pickup_sequence(self):
        """
        Execute pickup sequence with hook claw:
        1. Open claw
        2. Lower arm close to ground
        3. Close claw to grip ball
        4. Lift ball from ground
        """
        print("[SimArm] Executing pickup sequence")
        # Note: Actual timing handled by calling code with sim.step()
        
    def deposit_sequence(self):
        """
        Execute deposit sequence:
        1. Position arm over basket
        2. Open claw to drop ball
        3. Return to home
        """
        print("[SimArm] Executing deposit sequence")
        # Note: Actual timing handled by calling code with sim.step()
        
    def home(self):
        """Return to home position"""
        self.move_to_pose('home')


class SimCamera:
    """Simulated camera - mimics hardware.camera.Camera"""
    
    def __init__(self, robot_id, width=320, height=240, fov=160):
        """
        Initialize simulated camera
        
        Args:
            robot_id: PyBullet robot body ID
            width: Image width
            height: Image height
            fov: Field of view in degrees
        """
        self.robot_id = robot_id
        self.width = width
        self.height = height
        self.fov = fov
        
        # Pan/tilt state (not implemented yet)
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
        
    def set_pan(self, angle):
        """Set camera pan angle (degrees)"""
        self.pan_angle = angle
        
    def set_tilt(self, angle):
        """Set camera tilt angle (degrees)"""
        self.tilt_angle = angle
        
    def center(self):
        """Center camera"""
        self.pan_angle = 0
        self.tilt_angle = 0
        
    def look_down(self):
        """Look down at ground"""
        self.tilt_angle = 30
        
    def look_forward(self):
        """Look forward"""
        self.tilt_angle = 0


def create_sim_hardware(robot_id, config):
    """
    Factory function to create all simulated hardware interfaces
    
    Args:
        robot_id: PyBullet robot body ID
        config: Configuration dictionary
        
    Returns:
        (chassis, arm, camera) tuple
    """
    chassis = SimChassis(robot_id, max_speed=config.get('motors', {}).get('max_speed', 0.25))
    arm = SimArm(robot_id, config)
    camera = SimCamera(robot_id, width=320, height=240, fov=160)
    
    return chassis, arm, camera
