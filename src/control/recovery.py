#!/usr/bin/env python3
"""
Recovery — Stuck detection and escape behaviors.

Detects when robot is stuck and executes recovery maneuvers.
"""

import time
import numpy as np


class RecoverySystem:
    """Detects stuck conditions and executes recovery maneuvers."""
    
    def __init__(self, robot, config=None):
        """
        Initialize recovery system.
        
        Args:
            robot: Robot instance
            config: Optional configuration dict
        """
        self.robot = robot
        
        # Stuck detection parameters
        self.stuck_timeout = 3.0  # Consider stuck after 3s of no movement
        self.movement_threshold = 0.05  # Minimum motor value to count as moving
        
        # State tracking
        self.last_movement_time = time.time()
        self.last_motor_values = (0.0, 0.0)
        self.stuck_count = 0
        
        # Recovery in progress
        self.recovering = False
        self.recovery_start_time = 0
        self.recovery_duration = 1.5  # Recovery takes 1.5 seconds
    
    def update(self, current_motor_values):
        """
        Update stuck detection.
        
        Args:
            current_motor_values: Tuple (left_motor, right_motor)
            
        Returns:
            True if stuck and recovery needed
        """
        current_time = time.time()
        left, right = current_motor_values
        
        # Check if motors are trying to move
        is_moving = abs(left) > self.movement_threshold or abs(right) > self.movement_threshold
        
        if is_moving:
            # Motors are active
            # In a real system, we'd check encoder feedback here
            # For now, assume if motors are commanded, we're moving
            self.last_movement_time = current_time
            self.last_motor_values = current_motor_values
            return False
        else:
            # Motors are stopped (intentionally)
            self.last_movement_time = current_time
            return False
        
        # Note: Without encoders, we can't detect actual stuck conditions
        # This is a simplified version that would need encoder feedback
    
    def is_stuck(self):
        """
        Check if robot is stuck.
        
        Returns:
            True if stuck
        """
        current_time = time.time()
        time_since_movement = current_time - self.last_movement_time
        
        # Check if motors are commanded but not moving (would need encoders)
        left, right = self.last_motor_values
        motors_active = abs(left) > self.movement_threshold or abs(right) > self.movement_threshold
        
        if motors_active and time_since_movement > self.stuck_timeout:
            return True
        
        return False
    
    def start_recovery(self):
        """Start recovery maneuver."""
        self.recovering = True
        self.recovery_start_time = time.time()
        self.stuck_count += 1
    
    def execute_recovery(self):
        """
        Execute recovery maneuver.
        
        Returns:
            Tuple: (action, duration_remaining)
            action is 'reverse', 'turn_left', 'turn_right', or 'complete'
        """
        if not self.recovering:
            return 'complete', 0.0
        
        current_time = time.time()
        elapsed = current_time - self.recovery_start_time
        
        if elapsed > self.recovery_duration:
            # Recovery complete
            self.recovering = False
            return 'complete', 0.0
        
        # Recovery sequence:
        # 0.0 - 0.5s: Reverse
        # 0.5 - 1.5s: Turn (direction alternates based on stuck_count)
        
        if elapsed < 0.5:
            return 'reverse', self.recovery_duration - elapsed
        else:
            # Alternate turn direction
            if self.stuck_count % 2 == 0:
                return 'turn_right', self.recovery_duration - elapsed
            else:
                return 'turn_left', self.recovery_duration - elapsed
    
    def reset(self):
        """Reset recovery system."""
        self.last_movement_time = time.time()
        self.stuck_count = 0
        self.recovering = False
