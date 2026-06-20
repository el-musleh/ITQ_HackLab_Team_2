#!/usr/bin/env python3
"""
Navigator — Motion planning and execution for ball collection.

Converts high-level commands (approach, return, avoid) into motor commands.
Uses PID controller for smooth tracking.
"""

import time
from control.pid import DualPIDController


class Navigator:
    """Handles robot navigation and motion control."""
    
    def __init__(self, robot, config=None):
        """
        Initialize navigator.
        
        Args:
            robot: Robot instance (with left_motor, right_motor)
            config: Optional configuration dict
        """
        self.robot = robot
        
        # Load config
        if config:
            motor_config = config.get('motors', {})
            self.max_speed = motor_config.get('max_speed', 0.25)
            self.approach_speed = motor_config.get('approach_speed', 0.15)
            self.search_speed = motor_config.get('search_speed', 0.10)
        else:
            self.max_speed = 0.25
            self.approach_speed = 0.15
            self.search_speed = 0.10
        
        # PID controller for tracking
        pid_config = config.get('pid', {}) if config else {}
        kp = pid_config.get('kp', 3.0)
        ki = pid_config.get('ki', 0.0)
        kd = pid_config.get('kd', 0.5)
        self.pid = DualPIDController(kp, ki, kd)
        
        # Frame dimensions (set by camera)
        self.frame_width = 320
        self.frame_height = 240
    
    def set_frame_size(self, width, height):
        """Set camera frame dimensions."""
        self.frame_width = width
        self.frame_height = height
    
    def execute_action(self, action, target=None):
        """
        Execute navigation action.
        
        Args:
            action: Action string ('approach', 'return', 'rotate', 'avoid', 'stop')
            target: Target info (ball or basket detection result)
            
        Returns:
            True if action executed, False if invalid
        """
        if action == 'stop':
            return self.stop()
        
        elif action == 'rotate':
            return self.rotate_search()
        
        elif action == 'approach':
            if target:
                return self.approach_target(target)
            return False
        
        elif action == 'return':
            if target:
                return self.return_to_basket(target)
            return False
        
        elif action == 'avoid':
            return self.avoid_maneuver(target)
        
        elif action == 'avoid_boundary':
            return self.avoid_boundary(target)
        
        elif action == 'avoid_obstacle':
            return self.avoid_obstacle(target)
        
        else:
            return False
    
    def stop(self):
        """Stop all motors."""
        self.robot.left_motor.value = 0.0
        self.robot.right_motor.value = 0.0
        self.pid.reset()
        return True
    
    def rotate_search(self):
        """Rotate in place to search for balls."""
        # Slow rotation
        speed = self.search_speed
        self.robot.left_motor.value = -speed
        self.robot.right_motor.value = speed
        return True
    
    def approach_target(self, target):
        """
        Approach a ball using PID tracking.
        
        Args:
            target: Tuple (color, centroid, distance, area) or dict
            
        Returns:
            True if approaching
        """
        # Extract centroid
        if isinstance(target, tuple):
            _, centroid, _, _ = target
        elif isinstance(target, dict):
            centroid = target.get('centroid')
        else:
            return False
        
        if centroid is None:
            return False
        
        # Use PID to calculate motor speeds
        left, right = self.pid.update(centroid[0], centroid[1], 
                                      self.frame_width, self.frame_height)
        
        # Scale to approach speed
        left *= self.approach_speed
        right *= self.approach_speed
        
        # Clamp to max speed
        left = max(-self.max_speed, min(self.max_speed, left))
        right = max(-self.max_speed, min(self.max_speed, right))
        
        # Apply to motors
        self.robot.left_motor.value = left
        self.robot.right_motor.value = right
        
        return True
    
    def return_to_basket(self, basket_detection):
        """
        Navigate to basket using PID tracking.
        
        Args:
            basket_detection: Dict from basket detector
            
        Returns:
            True if navigating
        """
        if not basket_detection.get('basket_found', False):
            return False
        
        centroid = basket_detection.get('centroid')
        if centroid is None:
            return False
        
        # Use PID to calculate motor speeds
        left, right = self.pid.update(centroid[0], centroid[1],
                                      self.frame_width, self.frame_height)
        
        # Scale to approach speed (slower for basket)
        left *= self.approach_speed * 0.8
        right *= self.approach_speed * 0.8
        
        # Clamp to max speed
        left = max(-self.max_speed, min(self.max_speed, left))
        right = max(-self.max_speed, min(self.max_speed, right))
        
        # Apply to motors
        self.robot.left_motor.value = left
        self.robot.right_motor.value = right
        
        return True
    
    def avoid_boundary(self, target):
        """
        Execute boundary avoidance maneuver.
        
        Args:
            target: Dict with 'direction' key
            
        Returns:
            True if executing
        """
        if target is None:
            direction = 'reverse'
        else:
            direction = target.get('direction', 'reverse')
        
        speed = self.approach_speed
        
        if direction == 'reverse':
            # Reverse
            self.robot.left_motor.value = -speed
            self.robot.right_motor.value = -speed
        elif direction == 'left':
            # Turn left (reverse right motor more)
            self.robot.left_motor.value = -speed * 0.5
            self.robot.right_motor.value = -speed
        elif direction == 'right':
            # Turn right (reverse left motor more)
            self.robot.left_motor.value = -speed
            self.robot.right_motor.value = -speed * 0.5
        
        return True
    
    def avoid_obstacle(self, target):
        """
        Execute obstacle avoidance maneuver.
        
        Args:
            target: Dict with 'direction' key
            
        Returns:
            True if executing
        """
        # Same as boundary avoidance for now
        return self.avoid_boundary(target)
    
    def avoid_maneuver(self, target):
        """Generic avoidance (delegates to specific handler)."""
        return self.avoid_obstacle(target)
    
    def drive_forward(self, speed=None):
        """Drive straight forward."""
        if speed is None:
            speed = self.approach_speed
        
        speed = min(speed, self.max_speed)
        self.robot.left_motor.value = speed
        self.robot.right_motor.value = speed
        return True
    
    def drive_backward(self, speed=None):
        """Drive straight backward."""
        if speed is None:
            speed = self.approach_speed
        
        speed = min(speed, self.max_speed)
        self.robot.left_motor.value = -speed
        self.robot.right_motor.value = -speed
        return True
    
    def turn_left(self, speed=None):
        """Turn left in place."""
        if speed is None:
            speed = self.search_speed
        
        self.robot.left_motor.value = -speed
        self.robot.right_motor.value = speed
        return True
    
    def turn_right(self, speed=None):
        """Turn right in place."""
        if speed is None:
            speed = self.search_speed
        
        self.robot.left_motor.value = speed
        self.robot.right_motor.value = -speed
        return True
