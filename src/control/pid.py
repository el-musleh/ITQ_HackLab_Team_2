#!/usr/bin/env python3
"""
PID Controller — Proportional-Integral-Derivative controller for ball tracking.

Keeps target (ball or basket) centered in camera frame by adjusting motor speeds.
"""

import time


class PIDController:
    """PID controller for smooth target tracking."""
    
    def __init__(self, kp=3.0, ki=0.0, kd=0.5, setpoint=0.0):
        """
        Initialize PID controller.
        
        Args:
            kp: Proportional gain
            ki: Integral gain
            kd: Derivative gain
            setpoint: Target value (0.0 = center of frame)
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint
        
        # State variables
        self.last_error = 0.0
        self.integral = 0.0
        self.last_time = time.time()
        
        # Limits
        self.integral_limit = 100.0  # Anti-windup
        self.output_limit = 1.0      # Max output
    
    def update(self, measurement):
        """
        Calculate PID output.
        
        Args:
            measurement: Current value (e.g., pixel offset from center)
            
        Returns:
            Control output (motor correction)
        """
        current_time = time.time()
        dt = current_time - self.last_time
        
        if dt <= 0.0:
            dt = 0.01  # Prevent division by zero
        
        # Calculate error
        error = self.setpoint - measurement
        
        # Proportional term
        p_term = self.kp * error
        
        # Integral term (with anti-windup)
        self.integral += error * dt
        self.integral = max(-self.integral_limit, min(self.integral_limit, self.integral))
        i_term = self.ki * self.integral
        
        # Derivative term
        d_term = self.kd * (error - self.last_error) / dt
        
        # Calculate output
        output = p_term + i_term + d_term
        
        # Clamp output
        output = max(-self.output_limit, min(self.output_limit, output))
        
        # Update state
        self.last_error = error
        self.last_time = current_time
        
        return output
    
    def reset(self):
        """Reset PID state."""
        self.last_error = 0.0
        self.integral = 0.0
        self.last_time = time.time()
    
    def set_gains(self, kp=None, ki=None, kd=None):
        """Update PID gains."""
        if kp is not None:
            self.kp = kp
        if ki is not None:
            self.ki = ki
        if kd is not None:
            self.kd = kd
    
    def set_setpoint(self, setpoint):
        """Update target setpoint."""
        self.setpoint = setpoint


class DualPIDController:
    """Dual PID controller for X and Y tracking."""
    
    def __init__(self, kp=3.0, ki=0.0, kd=0.5):
        """
        Initialize dual PID controller.
        
        Args:
            kp: Proportional gain
            ki: Integral gain
            kd: Derivative gain
        """
        self.pid_x = PIDController(kp, ki, kd, setpoint=0.0)
        self.pid_y = PIDController(kp, ki, kd, setpoint=0.0)
    
    def update(self, target_x, target_y, frame_width, frame_height):
        """
        Calculate motor commands to center target.
        
        Args:
            target_x: Target X position in pixels
            target_y: Target Y position in pixels
            frame_width: Frame width in pixels
            frame_height: Frame height in pixels
            
        Returns:
            Tuple: (left_motor, right_motor) speeds (-1.0 to 1.0)
        """
        # Calculate pixel offset from center
        center_x = frame_width / 2
        center_y = frame_height / 2
        
        offset_x = target_x - center_x
        offset_y = target_y - center_y
        
        # Normalize to -1.0 to 1.0
        normalized_x = offset_x / center_x
        normalized_y = offset_y / center_y
        
        # Get PID corrections
        correction_x = self.pid_x.update(normalized_x)
        correction_y = self.pid_y.update(normalized_y)
        
        # Convert to differential drive
        # Forward speed based on Y (closer = slower)
        forward = -correction_y * 0.5  # Negative because closer = lower Y
        
        # Turn rate based on X (left = negative, right = positive)
        turn = -correction_x
        
        # Calculate motor speeds
        left_motor = forward - turn
        right_motor = forward + turn
        
        # Clamp to [-1.0, 1.0]
        left_motor = max(-1.0, min(1.0, left_motor))
        right_motor = max(-1.0, min(1.0, right_motor))
        
        return left_motor, right_motor
    
    def reset(self):
        """Reset both PID controllers."""
        self.pid_x.reset()
        self.pid_y.reset()
    
    def set_gains(self, kp=None, ki=None, kd=None):
        """Update PID gains for both controllers."""
        self.pid_x.set_gains(kp, ki, kd)
        self.pid_y.set_gains(kp, ki, kd)
