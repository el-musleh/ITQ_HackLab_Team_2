#!/usr/bin/env python3
"""
Ball Detector — Multi-color HSV-based detection for blue, red, and silver balls.

Detects bottle caps in camera frames using HSV color segmentation.
Returns list of detected balls with color, position, and estimated distance.
"""

import cv2
import numpy as np
from collections import deque


class BallDetector:
    """Detects colored balls (blue, red, silver) using HSV color segmentation."""
    
    def __init__(self, config=None):
        """
        Initialize ball detector with HSV color ranges.
        
        Args:
            config: Optional dict with 'balls' configuration
        """
        if config and 'balls' in config:
            ball_config = config['balls']
            # Convert config colors to numpy arrays
            colors = ball_config.get('colors', {})
            self.color_ranges = self._convert_color_ranges(colors) if colors else self._default_colors()
            self.min_area = ball_config.get('min_area_px', 100)
            self.validation_frames = ball_config.get('validation_frames', 3)
            self.max_ball_diameter_cm = ball_config.get('max_ball_diameter_cm', 5.0)
            self.min_aspect_ratio = ball_config.get('min_aspect_ratio', 0.6)
            self.max_aspect_ratio = ball_config.get('max_aspect_ratio', 1.4)
        else:
            self.color_ranges = self._default_colors()
            self.min_area = 100
            self.validation_frames = 3
            self.max_ball_diameter_cm = 5.0
            self.min_aspect_ratio = 0.6
            self.max_aspect_ratio = 1.4
        
        # Multi-frame validation buffer
        self.detection_buffer = deque(maxlen=self.validation_frames)
        
        # Distance estimation parameters (calibrate on-site)
        self.known_ball_diameter_cm = 3.5  # Bottle cap ~3.5 cm
        self.focal_length_px = 300  # Approximate, tune with calibration
    
    def _convert_color_ranges(self, colors_config):
        """Convert color ranges from config (lists) to numpy arrays."""
        converted = {}
        for color_name, color_data in colors_config.items():
            converted[color_name] = {
                'hsv_lower': np.array(color_data['hsv_lower']),
                'hsv_upper': np.array(color_data['hsv_upper'])
            }
        return converted
    
    def _default_colors(self):
        """Default HSV ranges for each ball color."""
        return {
            'blue': {
                'hsv_lower': np.array([100, 150, 50]),
                'hsv_upper': np.array([130, 255, 255])
            },
            'red_1': {  # Red wraps around hue wheel
                'hsv_lower': np.array([0, 150, 50]),
                'hsv_upper': np.array([10, 255, 255])
            },
            'red_2': {
                'hsv_lower': np.array([170, 150, 50]),
                'hsv_upper': np.array([180, 255, 255])
            },
            'silver': {  # Low saturation, high value (tightened)
                'hsv_lower': np.array([0, 0, 180]),
                'hsv_upper': np.array([180, 25, 255])
            }
        }
    
    def detect(self, frame):
        """
        Detect all colored balls in frame.
        
        Args:
            frame: BGR image from camera
            
        Returns:
            List of tuples: [(color, centroid, distance_cm, area), ...]
            Sorted by distance (closest first)
        """
        if frame is None or frame.size == 0:
            return []
        
        # Convert to HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        detections = []
        
        # Detect blue balls
        blue_detections = self._detect_color(hsv, 'blue', self.color_ranges['blue'])
        detections.extend(blue_detections)
        
        # Detect red balls (two ranges)
        red_mask_1 = cv2.inRange(hsv, 
                                  self.color_ranges['red_1']['hsv_lower'],
                                  self.color_ranges['red_1']['hsv_upper'])
        red_mask_2 = cv2.inRange(hsv,
                                  self.color_ranges['red_2']['hsv_lower'],
                                  self.color_ranges['red_2']['hsv_upper'])
        red_mask = cv2.bitwise_or(red_mask_1, red_mask_2)
        red_detections = self._process_mask(red_mask, 'red')
        detections.extend(red_detections)
        
        # Detect silver balls
        silver_detections = self._detect_color(hsv, 'silver', self.color_ranges['silver'])
        detections.extend(silver_detections)
        
        # Sort by distance (closest first)
        detections.sort(key=lambda x: x[2])
        
        return detections
    
    def _detect_color(self, hsv, color_name, color_range):
        """Detect balls of a specific color."""
        mask = cv2.inRange(hsv, color_range['hsv_lower'], color_range['hsv_upper'])
        return self._process_mask(mask, color_name)
    
    def _process_mask(self, mask, color_name):
        """Process color mask to find ball contours."""
        # Morphological operations to reduce noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        detections = []
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filter by minimum area
            if area < self.min_area:
                continue
            
            # Check circularity (balls should be roughly circular)
            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue
            
            circularity = 4 * np.pi * area / (perimeter * perimeter)
            if circularity < 0.5:  # Not circular enough
                continue
            
            # Aspect ratio check (balls should be roughly square)
            x, y, w, h = cv2.boundingRect(contour)
            if h == 0:
                continue
            aspect_ratio = w / h
            if aspect_ratio < self.min_aspect_ratio or aspect_ratio > self.max_aspect_ratio:
                continue
            
            # Calculate centroid
            M = cv2.moments(contour)
            if M['m00'] == 0:
                continue
            
            cx = int(M['m10'] / M['m00'])
            cy = int(M['m01'] / M['m00'])
            centroid = (cx, cy)
            
            # Estimate distance from pixel area
            distance_cm = self._estimate_distance(area)
            
            # Max size check: reject objects larger than claw capacity
            pixel_diameter = 2 * np.sqrt(area / np.pi)
            if distance_cm > 0 and self.focal_length_px > 0:
                real_diameter_cm = (pixel_diameter * distance_cm) / self.focal_length_px
                if real_diameter_cm > self.max_ball_diameter_cm:
                    continue
            
            detections.append((color_name, centroid, distance_cm, area))
        
        return detections
    
    def _estimate_distance(self, pixel_area):
        """
        Estimate distance to ball based on pixel area.
        
        Uses: distance = (known_diameter * focal_length) / pixel_diameter
        
        Args:
            pixel_area: Area of ball contour in pixels
            
        Returns:
            Estimated distance in cm
        """
        # Approximate diameter from area (assuming circle)
        pixel_diameter = 2 * np.sqrt(pixel_area / np.pi)
        
        if pixel_diameter == 0:
            return 999.0  # Very far
        
        distance = (self.known_ball_diameter_cm * self.focal_length_px) / pixel_diameter
        return distance
    
    def validate_detection(self, detections):
        """
        Multi-frame validation to reduce false positives.
        
        Args:
            detections: Current frame detections
            
        Returns:
            Validated detections (present in N consecutive frames)
        """
        self.detection_buffer.append(detections)
        
        if len(self.detection_buffer) < self.validation_frames:
            return []  # Not enough frames yet
        
        # Find detections present in all frames
        validated = []
        
        if not detections:
            return []
        
        for current_det in detections:
            color, centroid, distance, area = current_det
            
            # Check if similar detection exists in all buffered frames
            present_in_all = True
            for buffered_frame in self.detection_buffer:
                found = False
                for buf_det in buffered_frame:
                    buf_color, buf_centroid, _, _ = buf_det
                    
                    # Same color and close position (within 30 pixels)
                    if buf_color == color:
                        dx = centroid[0] - buf_centroid[0]
                        dy = centroid[1] - buf_centroid[1]
                        dist_px = np.sqrt(dx*dx + dy*dy)
                        
                        if dist_px < 30:
                            found = True
                            break
                
                if not found:
                    present_in_all = False
                    break
            
            if present_in_all:
                validated.append(current_det)
        
        return validated
    
    def draw_detections(self, frame, detections, validated_only=False):
        """
        Draw detection overlays on frame.
        
        Args:
            frame: BGR image
            detections: List of detections to draw
            validated_only: If True, only draw validated detections
            
        Returns:
            Frame with overlays
        """
        overlay = frame.copy()
        
        color_map = {
            'blue': (255, 0, 0),      # BGR
            'red': (0, 0, 255),
            'silver': (192, 192, 192)
        }
        
        for detection in detections:
            color_name, centroid, distance, area = detection
            draw_color = color_map.get(color_name, (0, 255, 0))
            
            # Draw circle at centroid
            cv2.circle(overlay, centroid, 10, draw_color, 2)
            
            # Draw crosshair
            cv2.line(overlay, (centroid[0]-15, centroid[1]), 
                    (centroid[0]+15, centroid[1]), draw_color, 1)
            cv2.line(overlay, (centroid[0], centroid[1]-15), 
                    (centroid[0], centroid[1]+15), draw_color, 1)
            
            # Draw label
            label = f"{color_name} {distance:.0f}cm"
            cv2.putText(overlay, label, (centroid[0]+15, centroid[1]-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, draw_color, 1, cv2.LINE_AA)
        
        return overlay
    
    def calibrate_distance(self, frame, actual_distance_cm):
        """
        Calibrate distance estimation by measuring a ball at known distance.
        
        Args:
            frame: Frame with ball at known distance
            actual_distance_cm: Actual distance to ball in cm
            
        Returns:
            Calibrated focal length
        """
        detections = self.detect(frame)
        
        if not detections:
            print("No balls detected for calibration")
            return None
        
        # Use largest detection (closest ball)
        _, _, _, area = max(detections, key=lambda x: x[3])
        pixel_diameter = 2 * np.sqrt(area / np.pi)
        
        # focal_length = (pixel_diameter * distance) / known_diameter
        self.focal_length_px = (pixel_diameter * actual_distance_cm) / self.known_ball_diameter_cm
        
        print(f"Calibrated focal length: {self.focal_length_px:.1f} px")
        return self.focal_length_px
