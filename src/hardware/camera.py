#!/usr/bin/env python3
"""
Camera Controller — CSI camera interface with pan/tilt control.

Handles camera initialization and frame capture with fallback options.
"""

import cv2
import numpy as np
from src.SCSCtrl import TTLServo


class CameraController:
    """Manages camera capture and pan/tilt servos."""
    
    def __init__(self, config=None):
        """
        Initialize camera controller.
        
        Args:
            config: Optional configuration dict
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
        
        # Pan/tilt servo IDs
        if config and 'servos' in config:
            servo_config = config['servos']
            self.pan_id = servo_config.get('pan', 1)
            self.tilt_id = servo_config.get('tilt', 5)
        else:
            self.pan_id = 1
            self.tilt_id = 5
        
        # Camera instance
        self.camera = None
        self.camera_source = None
        
        # Current pan/tilt angles
        self.pan_angle = 0
        self.tilt_angle = 0
    
    def initialize(self):
        """
        Initialize camera (try jetbot first, fallback to OpenCV).
        
        Returns:
            True if successful
        """
        # Try jetbot camera
        try:
            from jetbot import Camera
            self.camera = Camera.instance(width=self.width, height=self.height)
            self.camera_source = 'jetbot'
            print(f"✓ JetBot Camera initialized ({self.width}x{self.height})")
            return True
        except Exception as e:
            print(f"JetBot camera failed: {e}")
        
        # Try OpenCV fallback
        try:
            self.camera = cv2.VideoCapture(0)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.camera.set(cv2.CAP_PROP_FPS, self.fps)
            self.camera_source = 'opencv'
            print(f"✓ OpenCV Camera initialized ({self.width}x{self.height})")
            return True
        except Exception as e:
            print(f"OpenCV camera failed: {e}")
        
        print("ERROR: No camera available!")
        return False
    
    def read(self):
        """
        Read frame from camera.
        
        Returns:
            BGR frame (numpy array) or None if failed
        """
        if self.camera is None:
            return None
        
        try:
            if self.camera_source == 'jetbot':
                # JetBot camera returns RGB
                frame = self.camera.value
                if frame is not None:
                    # Convert RGB to BGR for OpenCV
                    return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            elif self.camera_source == 'opencv':
                ret, frame = self.camera.read()
                if ret:
                    return frame
        
        except Exception as e:
            print(f"Frame read failed: {e}")
        
        return None
    
    def release(self):
        """Release camera resources."""
        if self.camera_source == 'opencv' and self.camera is not None:
            self.camera.release()
    
    def set_pan(self, angle, speed=150):
        """
        Set pan angle.
        
        Args:
            angle: Pan angle in degrees (-90 to +90)
            speed: Servo speed
            
        Returns:
            True if successful
        """
        # Clamp angle
        angle = max(-90, min(90, angle))
        
        try:
            TTLServo.servoAngleCtrl(self.pan_id, angle, 1, speed)
            self.pan_angle = angle
            return True
        except Exception as e:
            print(f"Pan failed: {e}")
            return False
    
    def get_pan(self):
        """Return current pan angle in degrees."""
        return self.pan_angle
    
    def set_tilt(self, angle, speed=150):
        """
        Set tilt angle.
        
        Args:
            angle: Tilt angle in degrees (-60 to +60)
            speed: Servo speed
            
        Returns:
            True if successful
        """
        # Clamp angle
        angle = max(-60, min(60, angle))
        
        try:
            TTLServo.servoAngleCtrl(self.tilt_id, angle, 1, speed)
            self.tilt_angle = angle
            return True
        except Exception as e:
            print(f"Tilt failed: {e}")
            return False
    
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
