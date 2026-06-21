"""Mock objects for testing state machine without hardware."""

import numpy as np
import time


class MockChassisController:
    """Mock chassis controller for testing."""
    
    def __init__(self, max_speed=0.25):
        self.max_speed = max_speed
        self.left_value = 0.0
        self.right_value = 0.0
        self.stopped = True
        
    def set_motors(self, left, right):
        """Set motor speeds."""
        self.left_value = left
        self.right_value = right
        self.stopped = (left == 0 and right == 0)
        
    def stop(self):
        """Stop all motors."""
        self.set_motors(0, 0)
        
    def turn_left(self, speed=0.1):
        """Turn left in place."""
        self.set_motors(-speed, speed)
        
    def turn_right(self, speed=0.1):
        """Turn right in place."""
        self.set_motors(speed, -speed)
        
    def get_motor_values(self):
        """Get current motor values."""
        return (self.left_value, self.right_value)


class MockArmController:
    """Mock arm controller for testing."""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.current_pose = [0, 0, 0, 0]
        self.gripper_state = 'open'
        self.pose_home = [0, 0, 0, 0]
        self.pose_pickup = [0, -35, -55, -25]
        self.pose_carry = [0, 15, 25, 50]
        self.pose_deposit = [0, 35, 35, 35]
        
    def move_to_pose(self, pose, speed=None):
        """Move to pose."""
        self.current_pose = list(pose)
        return True
        
    def gripper_open(self):
        """Open gripper."""
        self.gripper_state = 'open'
        return True
        
    def gripper_close(self):
        """Close gripper."""
        self.gripper_state = 'closed'
        return True
        
    def home(self):
        """Move to home position."""
        return self.move_to_pose(self.pose_home)
        
    def get_current_pose(self):
        """Get current pose."""
        return self.current_pose.copy()
        
    def emergency_stop(self):
        """Emergency stop."""
        return self.home()
        
    def is_extended(self):
        """Return True if arm is in an extended (pickup/deposit) pose."""
        for ext_pose in (self.pose_pickup, self.pose_deposit):
            if all(abs(a - b) < 1.0 for a, b in
                   zip(self.current_pose, ext_pose)):
                return True
        return False


class MockCameraController:
    """Mock camera controller for testing."""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.width = 320
        self.height = 240
        self.pan_angle = 0
        self.tilt_angle = 0
        self.initialized = False
        self.test_frame = None
        
    def initialize(self):
        """Initialize camera."""
        self.initialized = True
        return True
        
    def release(self):
        """Release camera."""
        self.initialized = False
        
    def read(self):
        """Read frame."""
        if self.test_frame is not None:
            return self.test_frame
        # Return a realistic mid-gray frame (not all-zeros which triggers
        # dark-frame detection in the safety monitor)
        return np.full((self.height, self.width, 3), 128, dtype=np.uint8)
        
    def set_pan(self, angle, speed=150):
        """Set pan angle."""
        self.pan_angle = max(-90, min(90, angle))
        return True
        
    def get_pan(self):
        """Get pan angle."""
        return self.pan_angle
        
    def set_tilt(self, angle, speed=150):
        """Set tilt angle."""
        self.tilt_angle = max(-60, min(60, angle))
        return True
        
    def center(self):
        """Center camera."""
        self.set_pan(0)
        self.set_tilt(0)
        return True
        
    def look_down(self):
        """Look down."""
        self.set_tilt(-30)
        return True
        
    def look_forward(self):
        """Look forward."""
        self.set_tilt(0)
        return True
        
    def get_frame_size(self):
        """Get frame size."""
        return (self.width, self.height)


class MockBallDetector:
    """Mock ball detector for testing."""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.test_balls = []
        self._validation_calls = 0
        
    def detect(self, frame):
        """Detect balls in frame."""
        return self.test_balls
    
    def validate_detection(self, detections):
        """Pass-through validation for testing (returns detections as-is)."""
        self._validation_calls += 1
        return list(detections) if detections else []
    
    def set_test_balls(self, balls):
        """Set test ball detections."""
        self.test_balls = balls


class MockBasketDetector:
    """Mock basket detector for testing."""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.test_basket = {'basket_found': False}
        self.calibrated = False
        
    def detect(self, frame):
        """Detect basket in frame."""
        return self.test_basket
        
    def calibrate(self, frames):
        """Calibrate basket detection."""
        self.calibrated = True
        return True
        
    def set_test_basket(self, basket):
        """Set test basket detection."""
        self.test_basket = basket


class MockObstacleDetector:
    """Mock obstacle detector for testing."""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.test_boundary = False
        self.test_obstacle = False
        
    def detect_boundary(self, frame):
        """Detect yellow boundary tape."""
        if self.test_boundary:
            return True, 'reverse', 2000
        return False, 'none', 0

    def get_yellow_mask(self, frame):
        """Return mock yellow mask (None = no cross-validation)."""
        return None

    def detect_combined(self, frame):
        """Detect obstacles and boundaries."""
        return {
            'boundary_detected': self.test_boundary,
            'obstacle_detected': self.test_obstacle,
            'boundary_side': 'left' if self.test_boundary else None,
            'priority': 'boundary' if self.test_boundary else ('obstacle' if self.test_obstacle else None),
            'turn_direction': 'reverse' if self.test_boundary else None,
        }
        
    def set_test_boundary(self, detected):
        """Set test boundary detection."""
        self.test_boundary = detected
        
    def set_test_obstacle(self, detected):
        """Set test obstacle detection."""
        self.test_obstacle = detected


class MockWorldMap:
    """Mock world map for testing."""
    
    def __init__(self, arena_bounds, obstacle_positions=None):
        self.arena_bounds = arena_bounds
        self.obstacle_positions = obstacle_positions or []
        self.balls = []
        self.visited = set()
        self.blind_spots = []
        self.basket_position = None
        
    def register_ball(self, x, y, source='camera', confidence=1.0, color=None):
        """Register a ball."""
        b = self.arena_bounds
        if not (b['x_min'] + 0.05 <= x <= b['x_max'] - 0.05 and
                b['y_min'] + 0.05 <= y <= b['y_max'] - 0.05):
            return None
        ball_id = len(self.balls)
        ball = {
            'id': ball_id,
            'x': x,
            'y': y,
            'source': source,
            'confidence': confidence,
            'collected': False,
            'color': color,
        }
        self.balls.append(ball)
        return ball_id
        
    def mark_collected(self, ball_id):
        """Mark ball as collected."""
        for ball in self.balls:
            if ball['id'] == ball_id:
                ball['collected'] = True
                return True
        return False
        
    def get_nearest_ball(self, pose):
        """Get nearest uncollected ball."""
        if pose is None:
            return None
        x, y, _ = pose
        nearest = None
        min_dist = float('inf')
        for ball in self.balls:
            if ball['collected']:
                continue
            dist = ((ball['x'] - x)**2 + (ball['y'] - y)**2)**0.5
            if dist < min_dist:
                min_dist = dist
                nearest = ball
        return nearest
        
    def has_known_balls(self):
        """Check if any uncollected balls are known."""
        return any(not ball['collected'] for ball in self.balls)
        
    def mark_visited(self, pose):
        """Mark position as visited."""
        if pose is None:
            return
        x, y, _ = pose
        grid_x = int(x / 0.2)
        grid_y = int(y / 0.2)
        self.visited.add((grid_x, grid_y))
        
    def get_blind_spots(self, pose):
        """Get blind spot viewpoints."""
        return self.blind_spots
        
    def has_blind_spots(self):
        """Check if blind spots remain."""
        return len(self.blind_spots) > 0
        
    def set_test_blind_spots(self, spots):
        """Set test blind spots."""
        self.blind_spots = spots

    def register_ball_from_detection(self, ball, pose, camera_pan_deg=0):
        """Register a ball from a detection tuple and current pose."""
        if pose is None:
            return None
        color, (cx, cy), distance, area = ball
        x = pose[0] + (distance / 100.0) * (1 if cx >= 0 else 0)
        y = pose[1]
        return self.register_ball(x, y, source='camera', color=color)

    def get_nearest_blind_spot(self, pose):
        """Get nearest unvisited blind spot."""
        if pose is None or not self.blind_spots:
            return None
        x, y, _ = pose
        nearest = None
        min_dist = float('inf')
        for spot in self.blind_spots:
            dist = ((spot[0] - x)**2 + (spot[1] - y)**2)**0.5
            if dist < min_dist:
                min_dist = dist
                nearest = spot
        return nearest

    def mark_unreachable(self, ball_id):
        """Mark a ball as unreachable."""
        for ball in self.balls:
            if ball['id'] == ball_id:
                ball['unreachable'] = True
                return True
        return False

    def set_basket_position(self, x, y):
        """Store basket world coordinates."""
        self.basket_position = (x, y)

    def get_basket_position(self):
        """Return (x, y) or None."""
        return self.basket_position

    def get_ball_count(self):
        """Return (total, collected, remaining, unreachable) counts."""
        total = len(self.balls)
        collected = sum(1 for b in self.balls if b.get('collected'))
        unreachable = sum(1 for b in self.balls if b.get('unreachable'))
        remaining = total - collected - unreachable
        return (total, collected, remaining, unreachable)
