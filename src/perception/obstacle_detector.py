#!/usr/bin/env python3
"""
Obstacle Detector — Yellow tape and edge detection for obstacle avoidance.

Detects yellow-taped obstacles and boundaries in the arena.
Returns obstacle presence and recommended avoidance direction.
"""

import cv2
import numpy as np


class ObstacleDetector:
    """Detects obstacles using yellow tape HSV detection and edge analysis."""
    
    def __init__(self, config=None):
        """
        Initialize obstacle detector.
        
        Args:
            config: Optional dict with 'obstacles' configuration
        """
        if config and 'obstacles' in config:
            obs_config = config['obstacles']
            self.yellow_lower = np.array(obs_config.get('yellow_hsv_lower', [20, 100, 100]))
            self.yellow_upper = np.array(obs_config.get('yellow_hsv_upper', [40, 255, 255]))
            self.threshold_px = obs_config.get('threshold_px', 1800)
            self.edge_threshold = obs_config.get('edge_threshold', 500)
        else:
            self.yellow_lower = np.array([20, 100, 100])
            self.yellow_upper = np.array([40, 255, 255])
            self.threshold_px = 1800
            self.edge_threshold = 500
        
        # ROI settings (Region of Interest)
        self.bottom_roi_frac = 0.30  # Bottom 30% for boundary detection
        self.front_roi_top_frac = 0.15  # Front obstacle zone: 15% to 65%
        self.front_roi_bottom_frac = 0.65
    
    def get_yellow_mask(self, frame):
        """
        Return full-frame yellow HSV mask for cross-validation.

        Used to check if a ball detection centroid overlaps with
        yellow tape pixels (indicating a false positive).

        Args:
            frame: BGR image from camera

        Returns:
            Binary mask (same size as frame) where yellow pixels are 255.
        """
        if frame is None or frame.size == 0:
            return None
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.yellow_lower, self.yellow_upper)
        return mask

    def detect_boundary(self, frame):
        """
        Detect yellow boundary tape (arena edges).
        
        Args:
            frame: BGR image from camera
            
        Returns:
            Tuple: (boundary_detected: bool, turn_direction: str, yellow_pixels: int)
            turn_direction is 'left', 'right', or 'reverse'
        """
        if frame is None or frame.size == 0:
            return False, 'none', 0
        
        h, w = frame.shape[:2]
        
        # ROI: Bottom portion of frame (where boundary tape appears)
        roi_top = int(h * (1 - self.bottom_roi_frac))
        roi = frame[roi_top:h, 0:w]
        
        # Convert to HSV and detect yellow
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.yellow_lower, self.yellow_upper)
        
        # Count yellow pixels
        yellow_pixels = cv2.countNonZero(mask)
        
        # Check if boundary detected
        boundary_detected = yellow_pixels > self.threshold_px
        
        if not boundary_detected:
            return False, 'none', yellow_pixels
        
        # Determine turn direction based on yellow distribution
        turn_direction = self._determine_turn_direction(mask)
        
        return True, turn_direction, yellow_pixels
    
    def detect_obstacle(self, frame):
        """
        Detect obstacles in front of robot using edge detection.
        
        Args:
            frame: BGR image from camera
            
        Returns:
            Tuple: (obstacle_detected: bool, turn_direction: str, edge_pixels: int)
        """
        if frame is None or frame.size == 0:
            return False, 'none', 0
        
        h, w = frame.shape[:2]
        
        # ROI: Front zone (middle section of frame)
        roi_top = int(h * self.front_roi_top_frac)
        roi_bottom = int(h * self.front_roi_bottom_frac)
        roi = frame[roi_top:roi_bottom, 0:w]
        
        # Convert to grayscale
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        # Edge detection
        edges = cv2.Canny(gray, 50, 150)
        
        # Count edge pixels
        edge_pixels = cv2.countNonZero(edges)
        
        # Check if obstacle detected
        obstacle_detected = edge_pixels > self.edge_threshold
        
        if not obstacle_detected:
            return False, 'none', edge_pixels
        
        # Determine turn direction based on edge distribution
        turn_direction = self._determine_turn_direction(edges)
        
        return True, turn_direction, edge_pixels
    
    def detect_combined(self, frame):
        """
        Combined detection: boundary takes priority over obstacles.
        
        Args:
            frame: BGR image from camera
            
        Returns:
            Dict with detection results:
            {
                'boundary_detected': bool,
                'obstacle_detected': bool,
                'turn_direction': str,
                'yellow_pixels': int,
                'edge_pixels': int,
                'priority': str  # 'boundary', 'obstacle', or 'none'
            }
        """
        boundary_detected, boundary_dir, yellow_px = self.detect_boundary(frame)
        obstacle_detected, obstacle_dir, edge_px = self.detect_obstacle(frame)
        
        # Boundary takes priority
        if boundary_detected:
            priority = 'boundary'
            turn_direction = boundary_dir
        elif obstacle_detected:
            priority = 'obstacle'
            turn_direction = obstacle_dir
        else:
            priority = 'none'
            turn_direction = 'none'
        
        return {
            'boundary_detected': boundary_detected,
            'obstacle_detected': obstacle_detected,
            'turn_direction': turn_direction,
            'yellow_pixels': yellow_px,
            'edge_pixels': edge_px,
            'priority': priority
        }
    
    def _determine_turn_direction(self, mask):
        """
        Determine which direction to turn based on pixel distribution.
        
        Args:
            mask: Binary mask (yellow or edges)
            
        Returns:
            'left', 'right', or 'reverse'
        """
        h, w = mask.shape[:2]
        
        # Split mask into left and right halves
        left_half = mask[:, 0:w//2]
        right_half = mask[:, w//2:w]
        
        left_pixels = cv2.countNonZero(left_half)
        right_pixels = cv2.countNonZero(right_half)
        
        # Turn away from the side with more detection
        if left_pixels > right_pixels * 1.2:  # 20% threshold to avoid jitter
            return 'right'  # More on left, turn right
        elif right_pixels > left_pixels * 1.2:
            return 'left'  # More on right, turn left
        else:
            return 'reverse'  # Equal or uncertain, reverse
    
    def draw_detections(self, frame, detection_result):
        """
        Draw detection overlays on frame.
        
        Args:
            frame: BGR image
            detection_result: Dict from detect_combined()
            
        Returns:
            Frame with overlays
        """
        overlay = frame.copy()
        h, w = frame.shape[:2]
        
        # Draw ROI boundaries
        # Bottom ROI (boundary detection)
        roi_top = int(h * (1 - self.bottom_roi_frac))
        cv2.line(overlay, (0, roi_top), (w, roi_top), (0, 255, 255), 1)
        cv2.putText(overlay, "Boundary ROI", (10, roi_top - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        
        # Front ROI (obstacle detection)
        front_top = int(h * self.front_roi_top_frac)
        front_bottom = int(h * self.front_roi_bottom_frac)
        cv2.rectangle(overlay, (0, front_top), (w, front_bottom), (255, 0, 255), 1)
        cv2.putText(overlay, "Obstacle ROI", (10, front_top - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 255), 1)
        
        # Draw status
        y_offset = 20
        
        if detection_result['boundary_detected']:
            status = f"BOUNDARY! Turn {detection_result['turn_direction']}"
            color = (0, 0, 255)  # Red
            cv2.putText(overlay, status, (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            y_offset += 25
        
        if detection_result['obstacle_detected']:
            status = f"OBSTACLE! Turn {detection_result['turn_direction']}"
            color = (0, 165, 255)  # Orange
            cv2.putText(overlay, status, (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            y_offset += 25
        
        # Draw pixel counts
        info = f"Yellow: {detection_result['yellow_pixels']} px"
        cv2.putText(overlay, info, (10, h - 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        
        info = f"Edges: {detection_result['edge_pixels']} px"
        cv2.putText(overlay, info, (10, h - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 255), 1)
        
        return overlay
    
    def get_avoidance_command(self, detection_result):
        """
        Convert detection result to motor command.
        
        Args:
            detection_result: Dict from detect_combined()
            
        Returns:
            Tuple: (action: str, duration: float)
            action is 'reverse', 'turn_left', 'turn_right', or 'none'
        """
        if detection_result['priority'] == 'none':
            return 'none', 0.0
        
        turn_dir = detection_result['turn_direction']
        
        if turn_dir == 'reverse':
            return 'reverse', 0.5  # Reverse for 0.5 seconds
        elif turn_dir == 'left':
            return 'turn_left', 0.3  # Turn left for 0.3 seconds
        elif turn_dir == 'right':
            return 'turn_right', 0.3  # Turn right for 0.3 seconds
        else:
            return 'none', 0.0
