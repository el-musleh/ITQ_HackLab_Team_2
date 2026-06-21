#!/usr/bin/env python3
"""
Arm Controller — 4-DOF robotic arm control with predefined poses.

Controls servos for ball pickup and deposit operations.
Servo IDs: 2 (base), 3 (shoulder), 4 (elbow), 6 (gripper)
"""

import time
from src.SCSCtrl import TTLServo


class ArmController:
    """Controls 4-DOF robotic arm for ball manipulation."""
    
    def __init__(self, config=None):
        """
        Initialize arm controller.
        
        Args:
            config: Optional configuration dict with servo IDs and poses
        """
        # Servo IDs
        if config and 'servos' in config:
            servo_config = config['servos']
            self.base_id = servo_config.get('arm_base', 2)
            self.shoulder_id = servo_config.get('arm_shoulder', 3)
            self.elbow_id = servo_config.get('arm_elbow', 4)
            self.gripper_id = servo_config.get('gripper', 6)
        else:
            self.base_id = 2
            self.shoulder_id = 3
            self.elbow_id = 4
            self.gripper_id = 6
        
        # Predefined poses (angles in degrees)
        if config and 'arm_poses' in config:
            poses = config['arm_poses']
            self.pose_home = poses.get('home', [0, 0, 0, 0])
            self.pose_pickup = poses.get('pickup', [0, -40, -60, 0])
            self.pose_carry = poses.get('carry', [0, 20, 30, 90])
            self.pose_deposit = poses.get('deposit', [0, 40, 40, 0])
        else:
            # Default poses
            self.pose_home = [0, 0, 0, 0]        # All servos centered
            self.pose_pickup = [0, -40, -60, 0]  # Lower to ground, gripper open
            self.pose_carry = [0, 20, 30, 90]    # Lift with gripper closed
            self.pose_deposit = [0, 40, 40, 0]   # Over basket, gripper open
        
        # Motion parameters
        self.default_speed = 150  # Servo speed (1-1500)
        self.slow_speed = 80      # Slow speed for precise movements
        
        # Current pose tracking
        self.current_pose = self.pose_home.copy()
    
    def move_to_pose_ramped(self, pose, max_speed=None, num_steps=10):
        """Move arm to a pose with trapezoidal velocity profile.

        Accelerates during the first 30% of steps, cruises at max_speed
        for the middle 40%, and decelerates during the final 30%.

        Args:
            pose: List of 4 angles [base, shoulder, elbow, gripper]
            max_speed: Peak servo speed (default: self.default_speed)
            num_steps: Number of interpolation steps (more = smoother)

        Returns:
            True if successful
        """
        if max_speed is None:
            max_speed = self.default_speed

        min_speed = self.slow_speed
        start_pose = self.current_pose.copy()
        target_pose = list(pose)

        try:
            for i in range(1, num_steps + 1):
                progress = i / num_steps

                # Trapezoidal velocity profile
                if progress < 0.3:
                    # Acceleration phase
                    ramp = progress / 0.3
                elif progress > 0.7:
                    # Deceleration phase
                    ramp = (1.0 - progress) / 0.3
                else:
                    # Cruise phase
                    ramp = 1.0
                ramp = max(0.0, min(1.0, ramp))
                step_speed = int(min_speed + ramp * (max_speed - min_speed))

                # Interpolate angles
                interp_pose = [
                    start + progress * (target - start)
                    for start, target in zip(start_pose, target_pose)
                ]

                TTLServo.servoAngleCtrl(self.base_id, int(interp_pose[0]), 1, step_speed)
                TTLServo.servoAngleCtrl(self.shoulder_id, int(interp_pose[1]), 1, step_speed)
                TTLServo.servoAngleCtrl(self.elbow_id, int(interp_pose[2]), 1, step_speed)
                TTLServo.servoAngleCtrl(self.gripper_id, int(interp_pose[3]), 1, step_speed)

                time.sleep(0.02)

            self.current_pose = target_pose
            return True

        except Exception as e:
            print(f"Ramped arm movement failed: {e}")
            return False

    def move_to_pose(self, pose, speed=None):
        """
        Move arm to a predefined pose.
        
        Args:
            pose: List of 4 angles [base, shoulder, elbow, gripper]
            speed: Servo speed (default: self.default_speed)
            
        Returns:
            True if successful
        """
        if speed is None:
            speed = self.default_speed
        
        base_angle, shoulder_angle, elbow_angle, gripper_angle = pose
        
        try:
            # Move all servos simultaneously
            TTLServo.servoAngleCtrl(self.base_id, base_angle, 1, speed)
            TTLServo.servoAngleCtrl(self.shoulder_id, shoulder_angle, 1, speed)
            TTLServo.servoAngleCtrl(self.elbow_id, elbow_angle, 1, speed)
            TTLServo.servoAngleCtrl(self.gripper_id, gripper_angle, 1, speed)
            
            self.current_pose = pose.copy()
            return True
        
        except Exception as e:
            print(f"Arm movement failed: {e}")
            return False
    
    def home(self):
        """Move to home position."""
        return self.move_to_pose(self.pose_home)
    
    def pickup_sequence(self):
        """
        Execute ball pickup sequence.
        
        Returns:
            True if successful
        """
        print("Pickup sequence starting...")
        
        # 1. Open gripper
        if not self.gripper_open():
            return False
        time.sleep(0.3)
        
        # 2. Move to pickup position (lower arm, ramped)
        if not self.move_to_pose_ramped(self.pose_pickup, max_speed=self.slow_speed):
            return False
        time.sleep(0.5)  # Wait for arm to settle
        
        # 3. Close gripper
        if not self.gripper_close():
            return False
        time.sleep(0.5)  # Wait for gripper to close
        
        # 4. Lift to carry position (ramped)
        if not self.move_to_pose_ramped(self.pose_carry, max_speed=self.default_speed):
            return False
        time.sleep(0.5)
        
        print("Pickup complete!")
        return True
    
    def deposit_sequence(self):
        """
        Execute ball deposit sequence.
        
        Returns:
            True if successful
        """
        print("Deposit sequence starting...")
        
        # 1. Move to deposit position (over basket, ramped)
        if not self.move_to_pose_ramped(self.pose_deposit, max_speed=self.default_speed):
            return False
        time.sleep(0.5)
        
        # 2. Open gripper (drop ball)
        if not self.gripper_open():
            return False
        time.sleep(0.5)
        
        # 3. Return to home (ramped)
        if not self.move_to_pose_ramped(self.pose_home, max_speed=self.default_speed):
            return False
        time.sleep(0.5)
        
        print("Deposit complete!")
        return True
    
    def gripper_open(self):
        """Open gripper."""
        try:
            TTLServo.servoAngleCtrl(self.gripper_id, 0, 1, self.default_speed)
            return True
        except Exception as e:
            print(f"Gripper open failed: {e}")
            return False
    
    def gripper_close(self):
        """Close gripper."""
        try:
            TTLServo.servoAngleCtrl(self.gripper_id, 90, 1, self.default_speed)
            return True
        except Exception as e:
            print(f"Gripper close failed: {e}")
            return False
    
    def move_base(self, angle, speed=None):
        """Move base servo only."""
        if speed is None:
            speed = self.default_speed
        
        try:
            TTLServo.servoAngleCtrl(self.base_id, angle, 1, speed)
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
            TTLServo.servoAngleCtrl(self.shoulder_id, angle, 1, speed)
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
            TTLServo.servoAngleCtrl(self.elbow_id, angle, 1, speed)
            self.current_pose[2] = angle
            return True
        except Exception as e:
            print(f"Elbow movement failed: {e}")
            return False
    
    def is_extended(self):
        """Return True if the arm is in an extended (pickup/deposit) pose."""
        for ext_pose in (self.pose_pickup, self.pose_deposit):
            if all(abs(a - b) < 1.0 for a, b in
                   zip(self.current_pose, ext_pose)):
                return True
        return False

    def emergency_stop(self):
        """Stop all arm movement (return to home)."""
        return self.home()
    
    def get_current_pose(self):
        """Get current arm pose."""
        return self.current_pose.copy()
    
    def calibrate_pickup_height(self, test_angles):
        """
        Test different pickup heights to find optimal angle.
        
        Args:
            test_angles: List of shoulder angles to test
            
        Returns:
            None (interactive calibration)
        """
        print("Pickup height calibration")
        print("Testing different shoulder angles...")
        
        for angle in test_angles:
            print(f"\nTesting shoulder angle: {angle}°")
            pose = [0, angle, -60, 0]  # Base centered, elbow down, gripper open
            self.move_to_pose(pose, speed=self.slow_speed)
            time.sleep(2.0)
            
            response = input("Is this height good for pickup? (y/n): ")
            if response.lower() == 'y':
                print(f"Optimal pickup angle: {angle}°")
                print(f"Update config.yaml: arm_poses.pickup = [0, {angle}, -60, 0]")
                break
        
        self.home()
