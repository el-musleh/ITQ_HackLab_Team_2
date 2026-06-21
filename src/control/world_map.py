"""WorldMap — lightweight ball registry and blind-spot exploration grid.

Tracks estimated ball positions, visited viewpoints, and candidate blind-spot
cells. Works with simulation ground truth or camera-derived estimates.
"""

import math
import numpy as np


class WorldMap:
    """Map of balls, visited areas, and candidate blind-spot viewpoints."""

    def __init__(self, arena_bounds, obstacle_positions=None, grid_resolution=0.2,
                 view_radius=0.8, merge_distance=0.1, min_margin=0.15,
                 camera_fov_deg=160, basket_position=None):
        """
        Initialize world map.

        Args:
            arena_bounds: Dict with 'x_min', 'x_max', 'y_min', 'y_max' (meters).
            obstacle_positions: Optional list of dicts with 'x', 'y', 'width', 'height'.
            grid_resolution: Cell size for coverage grid (m).
            view_radius: Distance a camera sweep can cover (m).
            merge_distance: Merge two ball detections if closer than this (m).
            min_margin: Keep candidate points at least this far from obstacle edges.
            camera_fov_deg: Horizontal camera field of view for bearing calculation.
            basket_position: Optional (x, y) tuple for basket location in world coords.
        """
        self.arena_bounds = arena_bounds
        self.obstacle_positions = obstacle_positions or []
        self.grid_resolution = grid_resolution
        self.view_radius = view_radius
        self.merge_distance = merge_distance
        self.min_margin = min_margin
        self.camera_fov_deg = camera_fov_deg
        self.basket_position = basket_position

        self.balls = []
        self._ball_id_counter = 0
        self._visited = set()
        self._generate_candidate_cells()

    def set_basket_position(self, x, y):
        """Store estimated basket world coordinates."""
        self.basket_position = (x, y)

    def get_basket_position(self):
        """Return (x, y) basket position or None if unknown."""
        return self.basket_position

    def _generate_candidate_cells(self):
        """Build list of candidate viewpoint cells inside the arena and outside obstacles.

        Uses adaptive refinement: cells near obstacle edges (within
        ``min_margin * 2``) are subdivided at half resolution to catch
        narrow gaps between obstacles without increasing cell count
        across the whole arena.
        """
        self._candidate_cells = []
        coarse = self.grid_resolution
        fine = coarse / 2.0
        refine_band = self.min_margin * 2

        x_min, x_max = self.arena_bounds['x_min'], self.arena_bounds['x_max']
        y_min, y_max = self.arena_bounds['y_min'], self.arena_bounds['y_max']

        x = x_min + coarse / 2
        while x < x_max:
            y = y_min + coarse / 2
            while y < y_max:
                if self._is_inside_arena((x, y)) and not self._is_near_obstacle((x, y)):
                    self._candidate_cells.append((x, y))
                    # Adaptive refinement: add sub-cells near obstacle edges
                    if self._is_near_obstacle_edge((x, y), refine_band):
                        for dx in (-fine / 2, fine / 2):
                            for dy in (-fine / 2, fine / 2):
                                sub = (x + dx, y + dy)
                                if (self._is_inside_arena(sub) and
                                        not self._is_near_obstacle(sub) and
                                        sub not in self._candidate_cells):
                                    self._candidate_cells.append(sub)
                y += coarse
            x += coarse

    def _is_near_obstacle_edge(self, point, band):
        """Return True if point is within ``band`` of an obstacle but not inside it."""
        x, y = point
        for obs in self.obstacle_positions:
            ox, oy = obs['x'], obs['y']
            half_w = obs.get('width', 0) / 2
            half_h = obs.get('height', 0) / 2
            dx = abs(x - ox) - half_w
            dy = abs(y - oy) - half_h
            # Distance to obstacle edge (0 if inside, positive if outside)
            edge_dist = max(dx, dy)
            if 0 < edge_dist <= band:
                return True
        return False

    def _is_inside_arena(self, point):
        x, y = point
        b = self.arena_bounds
        return (b['x_min'] + 0.05 <= x <= b['x_max'] - 0.05 and
                b['y_min'] + 0.05 <= y <= b['y_max'] - 0.05)

    def _is_near_obstacle(self, point):
        x, y = point
        for obs in self.obstacle_positions:
            ox, oy = obs['x'], obs['y']
            half_w = obs.get('width', 0) / 2 + self.min_margin
            half_h = obs.get('height', 0) / 2 + self.min_margin
            if abs(x - ox) <= half_w and abs(y - oy) <= half_h:
                return True
        return False

    def register_ball(self, x, y, source='camera', confidence=1.0, color=None):
        """Register a ball at world coordinates; merge duplicates."""
        if not self._is_inside_arena((x, y)):
            return None

        # Check if already known
        for ball in self.balls:
            if ball['collected']:
                continue
            dx = ball['x'] - x
            dy = ball['y'] - y
            if math.hypot(dx, dy) < self.merge_distance:
                # Update average position and confidence
                ball['x'] = (ball['x'] * ball['confidence'] + x * confidence) / (ball['confidence'] + confidence)
                ball['y'] = (ball['y'] * ball['confidence'] + y * confidence) / (ball['confidence'] + confidence)
                ball['confidence'] += confidence
                ball['source'] = source
                if color is not None:
                    ball['color'] = color
                return ball['id']

        self._ball_id_counter += 1
        ball = {
            'id': self._ball_id_counter,
            'x': x,
            'y': y,
            'source': source,
            'confidence': confidence,
            'collected': False,
            'color': color,
        }
        self.balls.append(ball)
        return ball['id']

    def mark_unreachable(self, ball_id):
        """Mark a ball as unreachable (do not try again)."""
        for ball in self.balls:
            if ball['id'] == ball_id:
                ball['unreachable'] = True
                return True
        return False

    def register_ball_from_detection(self, detection, robot_pose,
                                       camera_pan_deg=0, source='camera'):
        """Convert a camera detection (distance in cm, bearing) into world coordinates (m)."""
        rx, ry, ryaw = robot_pose
        color, (cx, cy), distance, area = detection
        # Ball detector returns distance in cm -> convert to meters
        distance_m = distance / 100.0
        # Frame width; assume 320 if not given
        frame_width = 320
        half_fov = math.radians(self.camera_fov_deg) / 2
        bearing = (cx - frame_width / 2) / (frame_width / 2) * half_fov
        # Camera heading in world frame = robot yaw + pan angle
        camera_yaw = ryaw + math.radians(camera_pan_deg)
        x = rx + distance_m * math.cos(camera_yaw + bearing)
        y = ry + distance_m * math.sin(camera_yaw + bearing)
        return self.register_ball(x, y, source=source, color=color)

    def mark_collected(self, ball_id):
        """Mark a ball as collected."""
        for ball in self.balls:
            if ball['id'] == ball_id:
                ball['collected'] = True
                return True
        return False

    def mark_visited(self, robot_pose):
        """Mark arena cells visible from the robot as visited."""
        rx, ry, _ = robot_pose
        for cell in self._candidate_cells:
            dx = cell[0] - rx
            dy = cell[1] - ry
            if math.hypot(dx, dy) <= self.view_radius:
                self._visited.add(cell)

    def has_known_balls(self):
        """Return True if there are reachable, uncollected balls in the map."""
        return any(not b['collected'] and not b.get('unreachable') for b in self.balls)

    def get_nearest_ball(self, robot_pose):
        """Return the nearest uncollected and reachable ball dict, or None."""
        rx, ry, _ = robot_pose
        best = None
        best_dist = float('inf')
        for ball in self.balls:
            if ball['collected'] or ball.get('unreachable'):
                continue
            d = math.hypot(ball['x'] - rx, ball['y'] - ry)
            if d < best_dist:
                best_dist = d
                best = ball
        return best

    def get_nearest_blind_spot(self, robot_pose):
        """Return the nearest unvisited candidate cell, or None."""
        rx, ry, _ = robot_pose
        best = None
        best_dist = float('inf')
        for cell in self._candidate_cells:
            if cell in self._visited:
                continue
            d = math.hypot(cell[0] - rx, cell[1] - ry)
            if d < best_dist:
                best_dist = d
                best = cell
        return best

    def has_blind_spots(self):
        """Return True if there are candidate cells not yet visited."""
        for cell in self._candidate_cells:
            if cell not in self._visited:
                return True
        return False

    def get_ball_count(self):
        """Return total, collected, remaining, unreachable ball counts."""
        total = len(self.balls)
        collected = sum(1 for b in self.balls if b['collected'])
        unreachable = sum(1 for b in self.balls if b.get('unreachable'))
        return total, collected, total - collected - unreachable, unreachable

    def reset_visited(self):
        """Clear visited cells (e.g., for a new run)."""
        self._visited.clear()
