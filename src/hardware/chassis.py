#!/usr/bin/env python3
"""
Chassis Controller — Motor control wrapper for tracked chassis.

Provides clean interface to robot motors with safety limits.
"""


class ChassisController:
    """Wrapper for robot chassis motor control."""
    
    def __init__(self, robot, max_speed=0.25):
        """
        Initialize chassis controller.
        
        Args:
            robot: Robot instance with left_motor and right_motor
            max_speed: Maximum allowed speed (0.0 to 1.0)
        """
        self.robot = robot
        self.max_speed = max_speed
        
        # Current motor values
        self.left_value = 0.0
        self.right_value = 0.0
    
    def set_motors(self, left, right):
        """
        Set motor speeds with safety clamping.
        
        Args:
            left: Left motor speed (-1.0 to 1.0)
            right: Right motor speed (-1.0 to 1.0)
        """
        # Clamp to max speed
        left = max(-self.max_speed, min(self.max_speed, left))
        right = max(-self.max_speed, min(self.max_speed, right))
        
        # Apply to robot
        self.robot.left_motor.value = left
        self.robot.right_motor.value = right
        
        # Track current values
        self.left_value = left
        self.right_value = right
    
    def stop(self):
        """Stop all motors."""
        self.set_motors(0.0, 0.0)
    
    def forward(self, speed=0.15):
        """Drive forward."""
        speed = min(speed, self.max_speed)
        self.set_motors(speed, speed)
    
    def backward(self, speed=0.15):
        """Drive backward."""
        speed = min(speed, self.max_speed)
        self.set_motors(-speed, -speed)
    
    def turn_left(self, speed=0.10):
        """Turn left in place."""
        speed = min(speed, self.max_speed)
        self.set_motors(-speed, speed)
    
    def turn_right(self, speed=0.10):
        """Turn right in place."""
        speed = min(speed, self.max_speed)
        self.set_motors(speed, -speed)
    
    def get_motor_values(self):
        """Get current motor values."""
        return (self.left_value, self.right_value)
