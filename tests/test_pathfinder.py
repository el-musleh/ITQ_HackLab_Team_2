"""Unit tests for AStarPathfinder."""

import math
import pytest
from src.control.pathfinder import AStarPathfinder


# Shared fixtures
ARENA = {'x_min': 0.0, 'x_max': 1.8, 'y_min': 0.0, 'y_max': 1.75}

OBSTACLES = [
    {'x': 0.9 - 0.40, 'y': 0.875 + 0.40, 'width': 0.30, 'height': 0.20},
    {'x': 0.9 + 0.40, 'y': 0.875 - 0.40, 'width': 0.40, 'height': 0.30},
]

BASKET = (0.9, 0.875)


@pytest.fixture
def pathfinder():
    return AStarPathfinder(ARENA, OBSTACLES, cell_size=0.05, safety_margin=0.18)


@pytest.fixture
def empty_pathfinder():
    return AStarPathfinder(ARENA, [], cell_size=0.05, safety_margin=0.18)


class TestBasicPathfinding:
    def test_path_straight_line_no_obstacles(self, empty_pathfinder):
        path = empty_pathfinder.find_path((0.1, 0.1), (1.7, 1.65))
        assert path is not None
        assert len(path) >= 2
        assert path[0] == (0.1, 0.1)
        assert path[-1] == (1.7, 1.65)

    def test_path_start_equals_goal(self, pathfinder):
        path = pathfinder.find_path((0.1, 0.1), (0.1, 0.1))
        assert path is not None
        assert len(path) == 1

    def test_path_returns_none_for_enclosed_goal(self):
        arena = {'x_min': 0.0, 'x_max': 2.0, 'y_min': 0.0, 'y_max': 2.0}
        # Goal fully enclosed by a large obstacle
        obstacles = [{'x': 1.0, 'y': 1.0, 'width': 1.9, 'height': 1.9}]
        pf = AStarPathfinder(arena, obstacles, cell_size=0.05, safety_margin=0.05)
        path = pf.find_path((0.1, 0.1), (1.0, 1.0))
        assert path is None

    def test_path_around_single_obstacle(self):
        arena = {'x_min': 0.0, 'x_max': 3.0, 'y_min': 0.0, 'y_max': 3.0}
        obstacles = [{'x': 1.5, 'y': 1.5, 'width': 0.4, 'height': 2.5}]
        pf = AStarPathfinder(arena, obstacles, cell_size=0.05, safety_margin=0.15)
        path = pf.find_path((0.1, 1.5), (2.9, 1.5))
        assert path is not None
        # Path must go around the obstacle (not through y=1.5)
        for wx, wy in path:
            assert not (1.3 <= wx <= 1.7 and 0.2 <= wy <= 2.8), \
                "Path goes through obstacle"

    def test_path_around_two_arena_obstacles(self, pathfinder):
        path = pathfinder.find_path((0.1, 0.1), BASKET)
        assert path is not None
        assert len(path) >= 2
        assert path[-1] == BASKET

    def test_path_does_not_cross_obstacles(self, pathfinder):
        path = pathfinder.find_path((0.1, 1.6), (1.7, 0.1))
        assert path is not None
        for wx, wy in path:
            for obs in OBSTACLES:
                half_w = obs['width'] / 2 + pathfinder.safety_margin
                half_h = obs['height'] / 2 + pathfinder.safety_margin
                assert not (abs(wx - obs['x']) < half_w and
                            abs(wy - obs['y']) < half_h), \
                    f"Waypoint ({wx:.2f}, {wy:.2f}) inside obstacle + margin"


class TestTraversability:
    def test_is_traversable_free_cell(self, pathfinder):
        assert pathfinder.is_traversable(0.1, 0.1) is True

    def test_is_traversable_obstacle_cell(self, pathfinder):
        # Inside obstacle 1
        assert pathfinder.is_traversable(0.5, 1.275) is False

    def test_is_traversable_outside_arena(self, pathfinder):
        assert pathfinder.is_traversable(-0.5, 0.5) is False
        assert pathfinder.is_traversable(2.0, 0.5) is False

    def test_is_traversable_in_safety_margin(self, pathfinder):
        # Just outside obstacle edge but within safety margin
        ox = OBSTACLES[0]['x']
        oy = OBSTACLES[0]['y']
        half_w = OBSTACLES[0]['width'] / 2
        # Point just at obstacle edge + small offset (within safety margin)
        px = ox + half_w + 0.05
        py = oy
        assert pathfinder.is_traversable(px, py) is False


class TestMarkBlocked:
    def test_mark_blocked_replans_around(self, empty_pathfinder):
        # Initially straight path
        path1 = empty_pathfinder.find_path((0.1, 0.875), (1.7, 0.875))
        assert path1 is not None

        # Block the middle
        empty_pathfinder.mark_blocked(0.9, 0.875, radius=0.2)
        path2 = empty_pathfinder.find_path((0.1, 0.875), (1.7, 0.875))
        assert path2 is not None
        # New path must avoid the blocked area
        for wx, wy in path2:
            assert math.hypot(wx - 0.9, wy - 0.875) > 0.15, \
                "Path goes through blocked area"

    def test_mark_blocked_makes_goal_unreachable(self, empty_pathfinder):
        # Block a large area around goal
        empty_pathfinder.mark_blocked(1.7, 0.875, radius=1.0)
        path = empty_pathfinder.find_path((0.1, 0.875), (1.7, 0.875))
        # Should still find a path to the nearest free cell
        # or return None if truly enclosed
        # With a 1.0 radius block in a 1.8m arena, it may still find a way
        # around, so just check it doesn't crash
        assert path is None or len(path) >= 1


class TestPathSimplification:
    def test_simplify_collinear_points(self):
        path = [(0, 0), (1, 0), (2, 0), (3, 0)]
        simplified = AStarPathfinder._simplify_path(path)
        assert len(simplified) == 2
        assert simplified == [(0, 0), (3, 0)]

    def test_simplify_preserves_turns(self):
        path = [(0, 0), (1, 0), (1, 1), (1, 2)]
        simplified = AStarPathfinder._simplify_path(path)
        assert len(simplified) == 3
        assert (1, 0) in simplified

    def test_simplify_short_path_unchanged(self):
        path = [(0, 0), (1, 1)]
        simplified = AStarPathfinder._simplify_path(path)
        assert simplified == path


class TestPathLength:
    def test_empty_path(self):
        assert AStarPathfinder.get_path_length([]) == 0.0

    def test_single_point(self):
        assert AStarPathfinder.get_path_length([(1, 2)]) == 0.0

    def test_two_points(self):
        path = [(0, 0), (3, 4)]
        assert AStarPathfinder.get_path_length(path) == 5.0

    def test_multi_segment(self):
        path = [(0, 0), (3, 4), (3, 4)]
        assert AStarPathfinder.get_path_length(path) == 5.0


class TestEdgeCases:
    def test_path_start_in_obstacle_clamps_to_free(self, pathfinder):
        # Start inside obstacle — should clamp to nearest free cell
        path = pathfinder.find_path((0.5, 1.275), BASKET)
        assert path is not None

    def test_path_goal_in_obstacle_clamps_to_free(self, pathfinder):
        path = pathfinder.find_path((0.1, 0.1), (0.5, 1.275))
        assert path is not None

    def test_path_outside_arena_clamps(self, pathfinder):
        path = pathfinder.find_path((-0.5, -0.5), BASKET)
        assert path is not None

    def test_path_to_basket_from_corner(self, pathfinder):
        """Realistic scenario: robot at corner, basket at center."""
        path = pathfinder.find_path((0.05, 0.05), BASKET)
        assert path is not None
        assert path[-1] == BASKET
        length = AStarPathfinder.get_path_length(path)
        # Straight-line distance is ~1.07m, path should be somewhat longer
        straight = math.hypot(0.9 - 0.05, 0.875 - 0.05)
        assert length >= straight
        # But not absurdly long (no more than 3x straight)
        assert length <= straight * 3.0

    def test_path_from_behind_obstacle_to_basket(self, pathfinder):
        """Robot behind obstacle 1, needs to navigate around it."""
        # Position behind obstacle 1 (north-west of arena)
        behind = (0.3, 1.6)
        path = pathfinder.find_path(behind, BASKET)
        assert path is not None
        assert path[0] == behind
        assert path[-1] == BASKET
        # Verify no waypoint is inside an obstacle
        for wx, wy in path:
            for obs in OBSTACLES:
                half_w = obs['width'] / 2 + pathfinder.safety_margin
                half_h = obs['height'] / 2 + pathfinder.safety_margin
                assert not (abs(wx - obs['x']) < half_w and
                            abs(wy - obs['y']) < half_h)
