"""Dedicated unit tests for WorldMap ball registry and blind-spot grid."""

import math
import pytest
from src.control.world_map import WorldMap


# Shared fixtures

ARENA_BOUNDS = {
    'x_min': 0.0,
    'x_max': 1.8,
    'y_min': 0.0,
    'y_max': 1.75,
}

OBSTACLES = [
    {'x': 0.9, 'y': 0.5, 'width': 0.30, 'height': 0.20},
]


@pytest.fixture
def wm():
    return WorldMap(ARENA_BOUNDS, obstacle_positions=OBSTACLES,
                    grid_resolution=0.2, view_radius=0.8,
                    merge_distance=0.1)


@pytest.fixture
def wm_no_obs():
    return WorldMap(ARENA_BOUNDS, obstacle_positions=[],
                    grid_resolution=0.2, view_radius=0.8,
                    merge_distance=0.1)


# --- Registration ---

class TestRegisterBall:
    def test_register_ball_basic(self, wm):
        ball_id = wm.register_ball(0.5, 0.5)
        assert ball_id is not None
        assert len(wm.balls) == 1
        assert wm.balls[0]['x'] == 0.5
        assert wm.balls[0]['y'] == 0.5
        assert wm.balls[0]['collected'] is False

    def test_register_ball_with_color(self, wm):
        ball_id = wm.register_ball(0.5, 0.5, color='blue')
        assert ball_id is not None
        assert wm.balls[0]['color'] == 'blue'

    def test_register_ball_outside_arena(self, wm):
        ball_id = wm.register_ball(10.0, 10.0)
        assert ball_id is None
        assert len(wm.balls) == 0

    def test_register_ball_merge_duplicates(self, wm):
        id1 = wm.register_ball(0.5, 0.5, confidence=1.0)
        id2 = wm.register_ball(0.52, 0.51, confidence=1.0)
        assert id1 == id2
        assert len(wm.balls) == 1
        # Position should be averaged
        assert abs(wm.balls[0]['x'] - 0.51) < 0.01
        assert abs(wm.balls[0]['y'] - 0.505) < 0.01
        assert wm.balls[0]['confidence'] == 2.0

    def test_register_ball_no_merge_when_far(self, wm):
        id1 = wm.register_ball(0.2, 0.2)
        id2 = wm.register_ball(1.0, 1.0)
        assert id1 != id2
        assert len(wm.balls) == 2

    def test_register_ball_merge_updates_color(self, wm):
        id1 = wm.register_ball(0.5, 0.5)
        assert wm.balls[0]['color'] is None
        id2 = wm.register_ball(0.51, 0.51, color='red')
        assert id1 == id2
        assert wm.balls[0]['color'] == 'red'


# --- Detection-based registration ---

class TestRegisterBallFromDetection:
    def test_register_ball_from_detection(self, wm):
        # Robot at (0.5, 0.5, 0), ball straight ahead at 50cm
        detection = ('blue', (160, 120), 50.0, 500)
        pose = (0.5, 0.5, 0.0)
        ball_id = wm.register_ball_from_detection(detection, pose)
        assert ball_id is not None
        assert len(wm.balls) == 1
        # Ball should be ~0.5m ahead in x
        assert abs(wm.balls[0]['x'] - 1.0) < 0.05
        assert abs(wm.balls[0]['y'] - 0.5) < 0.05
        assert wm.balls[0]['color'] == 'blue'

    def test_register_ball_from_detection_with_pan(self, wm):
        # Robot at (0.5, 0.5, 0), camera panned 90 degrees, ball at 50cm
        detection = ('red', (160, 120), 50.0, 500)
        pose = (0.5, 0.5, 0.0)
        ball_id = wm.register_ball_from_detection(detection, pose, camera_pan_deg=90)
        assert ball_id is not None
        # Ball should be ~0.5m to the left (y direction)
        assert abs(wm.balls[0]['x'] - 0.5) < 0.05
        assert abs(wm.balls[0]['y'] - 1.0) < 0.05


# --- Ball status ---

class TestBallStatus:
    def test_mark_collected(self, wm):
        ball_id = wm.register_ball(0.5, 0.5)
        result = wm.mark_collected(ball_id)
        assert result is True
        assert wm.balls[0]['collected'] is True

    def test_mark_collected_invalid_id(self, wm):
        result = wm.mark_collected(999)
        assert result is False

    def test_mark_unreachable(self, wm):
        ball_id = wm.register_ball(0.5, 0.5)
        result = wm.mark_unreachable(ball_id)
        assert result is True
        assert wm.balls[0].get('unreachable') is True

    def test_mark_unreachable_invalid_id(self, wm):
        result = wm.mark_unreachable(999)
        assert result is False


# --- Nearest ball ---

class TestNearestBall:
    def test_get_nearest_ball(self, wm):
        wm.register_ball(0.3, 0.3)
        wm.register_ball(1.0, 1.0)
        nearest = wm.get_nearest_ball((0.0, 0.0, 0.0))
        assert nearest is not None
        assert nearest['x'] == 0.3
        assert nearest['y'] == 0.3

    def test_get_nearest_ball_skips_collected(self, wm):
        id1 = wm.register_ball(0.3, 0.3)
        wm.register_ball(1.0, 1.0)
        wm.mark_collected(id1)
        nearest = wm.get_nearest_ball((0.0, 0.0, 0.0))
        assert nearest is not None
        assert nearest['x'] == 1.0

    def test_get_nearest_ball_skips_unreachable(self, wm):
        id1 = wm.register_ball(0.3, 0.3)
        wm.register_ball(1.0, 1.0)
        wm.mark_unreachable(id1)
        nearest = wm.get_nearest_ball((0.0, 0.0, 0.0))
        assert nearest is not None
        assert nearest['x'] == 1.0

    def test_get_nearest_ball_none(self, wm):
        nearest = wm.get_nearest_ball((0.0, 0.0, 0.0))
        assert nearest is None


# --- Known balls check ---

class TestHasKnownBalls:
    def test_has_known_balls_true(self, wm):
        wm.register_ball(0.5, 0.5)
        assert wm.has_known_balls() is True

    def test_has_known_balls_false_after_collect(self, wm):
        ball_id = wm.register_ball(0.5, 0.5)
        wm.mark_collected(ball_id)
        assert wm.has_known_balls() is False

    def test_has_known_balls_false_after_unreachable(self, wm):
        ball_id = wm.register_ball(0.5, 0.5)
        wm.mark_unreachable(ball_id)
        assert wm.has_known_balls() is False

    def test_has_known_balls_false_empty(self, wm):
        assert wm.has_known_balls() is False


# --- Coverage & blind spots ---

class TestCoverageAndBlindSpots:
    def test_mark_visited(self, wm):
        wm.mark_visited((0.1, 0.1, 0.0))
        assert len(wm._visited) > 0

    def test_has_blind_spots_initially(self, wm):
        assert wm.has_blind_spots() is True

    def test_has_blind_spots_false_after_full_coverage(self, wm_no_obs):
        # Visit from multiple positions to cover the whole arena
        for x in [0.1, 0.5, 0.9, 1.3, 1.7]:
            for y in [0.1, 0.5, 0.9, 1.3, 1.7]:
                wm_no_obs.mark_visited((x, y, 0.0))
        assert wm_no_obs.has_blind_spots() is False

    def test_get_nearest_blind_spot(self, wm):
        spot = wm.get_nearest_blind_spot((0.0, 0.0, 0.0))
        assert spot is not None
        assert spot not in wm._visited

    def test_get_nearest_blind_spot_after_visit(self, wm):
        wm.mark_visited((0.1, 0.1, 0.0))
        spot = wm.get_nearest_blind_spot((0.1, 0.1, 0.0))
        if spot is not None:
            assert spot not in wm._visited

    def test_reset_visited(self, wm):
        wm.mark_visited((0.1, 0.1, 0.0))
        assert len(wm._visited) > 0
        wm.reset_visited()
        assert len(wm._visited) == 0


# --- Ball count ---

class TestBallCount:
    def test_get_ball_count_empty(self, wm):
        total, collected, remaining, unreachable = wm.get_ball_count()
        assert total == 0
        assert collected == 0
        assert remaining == 0
        assert unreachable == 0

    def test_get_ball_count_with_balls(self, wm):
        id1 = wm.register_ball(0.3, 0.3)
        wm.register_ball(0.5, 0.5)
        wm.mark_collected(id1)
        total, collected, remaining, unreachable = wm.get_ball_count()
        assert total == 2
        assert collected == 1
        assert remaining == 1
        assert unreachable == 0

    def test_get_ball_count_with_unreachable(self, wm):
        id1 = wm.register_ball(0.3, 0.3)
        wm.register_ball(0.5, 0.5)
        wm.mark_unreachable(id1)
        total, collected, remaining, unreachable = wm.get_ball_count()
        assert total == 2
        assert collected == 0
        assert remaining == 1
        assert unreachable == 1


# --- Adaptive refinement (Gap 6) ---

class TestAdaptiveRefinement:
    def test_finer_grid_produces_more_cells(self):
        wm_coarse = WorldMap(ARENA_BOUNDS, obstacle_positions=OBSTACLES,
                             grid_resolution=0.2)
        wm_fine = WorldMap(ARENA_BOUNDS, obstacle_positions=OBSTACLES,
                           grid_resolution=0.1)
        assert len(wm_fine._candidate_cells) > len(wm_coarse._candidate_cells)

    def test_adaptive_refinement_near_obstacles(self):
        wm = WorldMap(ARENA_BOUNDS, obstacle_positions=OBSTACLES,
                      grid_resolution=0.2)
        # Check that there are cells near the obstacle edge
        obs = OBSTACLES[0]
        near_edge = [
            c for c in wm._candidate_cells
            if abs(c[0] - obs['x']) < obs['width'] and
               abs(c[1] - obs['y']) < obs['height'] + 0.3
        ]
        # With adaptive refinement, there should be some cells near edges
        assert len(near_edge) > 0

    def test_is_near_obstacle_edge(self, wm):
        # Point just outside obstacle edge
        assert wm._is_near_obstacle_edge((0.9, 0.5 + 0.1 + 0.01), 0.3) is True
        # Point far from obstacle
        assert wm._is_near_obstacle_edge((0.1, 0.1), 0.3) is False
        # Point inside obstacle (not an edge)
        assert wm._is_near_obstacle_edge((0.9, 0.5), 0.3) is False
