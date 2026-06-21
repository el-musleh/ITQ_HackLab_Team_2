#!/usr/bin/env python3
"""
Basket Detector — Gray basket localization for ball deposit.

Detects the gray basket in the arena center using HSV color segmentation.
Requires initial calibration to learn basket appearance.
"""

import cv2
import numpy as np


class BasketDetector:
    """Detects gray basket using HSV color segmentation and shape matching."""
    
    def __init__(self, config=None):
        """
        Initialize basket detector.
        
        Args:
            config: Optional dict with 'basket' configuration
        """
        if config and 'basket' in config:
            basket_config = config['basket']
            self.gray_lower = np.array(basket_config.get('hsv_lower', [0, 0, 50]))
            self.gray_upper = np.array(basket_config.get('hsv_upper', [180, 50, 200]))
            self.calibrated_size = basket_config.get('size_px', None)
            self.calibrated_location = (
                basket_config.get('location_x', None),
                basket_config.get('location_y', None)
            )
        else:
            self.gray_lower = np.array([0, 0, 50])
            self.gray_upper = np.array([180, 50, 200])
            self.calibrated_size = None
            self.calibrated_location = (None, None)
        
        # Detection parameters
        self.min_area = 500  # Minimum basket area in pixels
        self.size_tolerance = 0.4  # 40% tolerance for size matching
        
        # Distance estimation (calibrate on-site)
        self.known_basket_width_cm = 30.0  # Approximate, measure on-site
        self.focal_length_px = 300  # Approximate
    
    def calibrate(self, frames, verbose=True):
        """
        Calibrate basket detector using multiple frames.
        
        User should position robot ~30 cm from basket and call this.
        
        Args:
            frames: List of BGR images (10+ recommended)
            verbose: Print calibration info
            
        Returns:
            Dict with calibration results or None if failed
        """
        if not frames:
            if verbose:
                print("No frames provided for calibration")
            return None
        
        detections = []
        
        for frame in frames:
            result = self.detect(frame, use_calibration=False)
            if result['basket_found']:
                detections.append({
                    'centroid': result['centroid'],
                    'area': result['area'],
                    'width': result['width']
                })
        
        if len(detections) < len(frames) * 0.5:
            if verbose:
                print(f"Calibration failed: Only {len(detections)}/{len(frames)} frames detected basket")
            return None
        
        # Calculate average size and location
        avg_area = np.mean([d['area'] for d in detections])
        avg_width = np.mean([d['width'] for d in detections])
        avg_x = np.mean([d['centroid'][0] for d in detections])
        avg_y = np.mean([d['centroid'][1] for d in detections])
        
        self.calibrated_size = avg_area
        self.calibrated_location = (int(avg_x), int(avg_y))
        
        calibration_result = {
            'size_px': avg_area,
            'width_px': avg_width,
            'location_x': int(avg_x),
            'location_y': int(avg_y),
            'detections': len(detections),
            'total_frames': len(frames)
        }
        
        if verbose:
            print("=" * 50)
            print("Basket Calibration Complete")
            print("=" * 50)
            print(f"Size: {avg_area:.0f} px² (width: {avg_width:.0f} px)")
            print(f"Location: ({avg_x:.0f}, {avg_y:.0f})")
            print(f"Success rate: {len(detections)}/{len(frames)} frames")
            print("\nAdd to config.yaml:")
            print("basket:")
            print(f"  size_px: {avg_area:.0f}")
            print(f"  location_x: {int(avg_x)}")
            print(f"  location_y: {int(avg_y)}")
        
        return calibration_result
    
    def detect(self, frame, use_calibration=True):
        """
        Detect basket in frame.
        
        Args:
            frame: BGR image from camera
            use_calibration: If True, use calibrated size for validation
            
        Returns:
            Dict with detection results:
            {
                'basket_found': bool,
                'centroid': (x, y) or None,
                'bearing': float (degrees, -90 to +90) or None,
                'distance': float (cm) or None,
                'area': float or None,
                'width': float or None
            }
        """
        result = {
            'basket_found': False,
            'centroid': None,
            'bearing': None,
            'distance': None,
            'area': None,
            'width': None
        }
        
        if frame is None or frame.size == 0:
            return result
        
        h, w = frame.shape[:2]
        
        # Convert to HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Detect gray regions
        mask = cv2.inRange(hsv, self.gray_lower, self.gray_upper)
        
        # Morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return result
        
        # Find best matching contour
        best_contour = None
        best_score = 0
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filter by minimum area
            if area < self.min_area:
                continue
            
            # If calibrated, check size match
            if use_calibration and self.calibrated_size is not None:
                size_ratio = area / self.calibrated_size
                if size_ratio < (1 - self.size_tolerance) or size_ratio > (1 + self.size_tolerance):
                    continue  # Size doesn't match
            
            # Score based on area (larger = better, up to a point)
            score = min(area, 5000)  # Cap at 5000 to avoid preferring huge regions
            
            if score > best_score:
                best_score = score
                best_contour = contour
        
        if best_contour is None:
            return result
        
        # Calculate properties
        area = cv2.contourArea(best_contour)
        M = cv2.moments(best_contour)
        
        if M['m00'] == 0:
            return result
        
        cx = int(M['m10'] / M['m00'])
        cy = int(M['m01'] / M['m00'])
        centroid = (cx, cy)
        
        # Calculate bounding box width
        x, y, bw, bh = cv2.boundingRect(best_contour)
        
        # Calculate bearing (angle from center)
        frame_center_x = w / 2
        pixel_offset = cx - frame_center_x
        bearing_deg = (pixel_offset / frame_center_x) * 45  # Approximate FOV = 90°
        
        # Estimate distance
        distance_cm = self._estimate_distance(bw)
        
        result = {
            'basket_found': True,
            'centroid': centroid,
            'bearing': bearing_deg,
            'distance': distance_cm,
            'area': area,
            'width': bw
        }
        
        return result
    
    def _estimate_distance(self, pixel_width):
        """
        Estimate distance to basket based on pixel width.
        
        Args:
            pixel_width: Width of basket in pixels
            
        Returns:
            Estimated distance in cm
        """
        if pixel_width == 0:
            return 999.0
        
        distance = (self.known_basket_width_cm * self.focal_length_px) / pixel_width
        return distance
    
    def draw_detection(self, frame, detection_result):
        """
        Draw detection overlay on frame.
        
        Args:
            frame: BGR image
            detection_result: Dict from detect()
            
        Returns:
            Frame with overlays
        """
        overlay = frame.copy()
        
        if not detection_result['basket_found']:
            cv2.putText(overlay, "Basket: NOT FOUND", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            return overlay
        
        centroid = detection_result['centroid']
        bearing = detection_result['bearing']
        distance = detection_result['distance']
        
        # Draw circle at centroid
        cv2.circle(overlay, centroid, 15, (0, 255, 0), 3)
        
        # Draw crosshair
        cv2.line(overlay, (centroid[0]-25, centroid[1]), 
                (centroid[0]+25, centroid[1]), (0, 255, 0), 2)
        cv2.line(overlay, (centroid[0], centroid[1]-25), 
                (centroid[0], centroid[1]+25), (0, 255, 0), 2)
        
        # Draw label
        label = f"BASKET: {distance:.0f}cm, {bearing:.0f}deg"
        cv2.putText(overlay, label, (centroid[0]+20, centroid[1]-20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Draw bearing arrow
        h, w = frame.shape[:2]
        frame_center = (w // 2, h // 2)
        cv2.arrowedLine(overlay, frame_center, centroid, (0, 255, 0), 2)
        
        return overlay
    
    def is_aligned(self, detection_result, bearing_tolerance=10):
        """
        Check if basket is aligned (centered in frame).
        
        Args:
            detection_result: Dict from detect()
            bearing_tolerance: Degrees tolerance for alignment
            
        Returns:
            True if basket is centered
        """
        if not detection_result['basket_found']:
            return False
        
        bearing = detection_result['bearing']
        return abs(bearing) < bearing_tolerance
    
    def is_close_enough(self, detection_result, target_distance_cm=20):
        """
        Check if robot is close enough to basket for deposit.
        
        Args:
            detection_result: Dict from detect()
            target_distance_cm: Target distance in cm
            
        Returns:
            True if close enough
        """
        if not detection_result['basket_found']:
            return False
        
        distance = detection_result['distance']
        return distance < target_distance_cm
