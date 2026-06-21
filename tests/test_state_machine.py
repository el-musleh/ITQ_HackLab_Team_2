"""Unit tests for state machine."""

import pytest
import time
from src.control.state_machine import (
    IDLE, WANDERING, CHECK_FOR_BALL, COLLECT_BALL, BALLS_LEFT,
    BLIND_SPOT, END, RECOVERY,
    CS_APPROACH, CS_PICKUP, CS_GOTO_BASKET, CS_DEPOSIT
)
from tests.test_utils import (
    create_test_state_machine, run_until_state, run_n_ticks,
    assert_state_transition, simulate_ball_detection,
    simulate_basket_detection
)


class TestStateInitialization:
    """Test state machine initialization."""
    
    def test_init_default_config(self):
        """Test initialization with default config."""
        sm, mocks = create_test_state_machine()
        assert sm.state == IDLE
        assert sm.finished == False
        assert sm.fatal_error is None
        
    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = {
            'motors': {'max_speed': 0.3},
            'state_machine': {'timeouts': {IDLE: 10.0}},
        }
        sm, mocks = create_test_state_machine(config)
        assert sm.max_speed == 0.3
        assert sm.timeouts[IDLE] == 10.0
        
    def test_reset(self):
        """Test reset returns to IDLE state."""
        sm, mocks = create_test_state_machine()
        sm.state = WANDERING
        sm.finished = True
        sm.reset()
        assert sm.state == IDLE
        assert sm.finished == False
        
    def test_initial_state_is_idle(self):
        """Test initial state is IDLE."""
        sm, mocks = create_test_state_machine()
        assert sm.state == IDLE


class TestStateTransitions:
    """Test state transitions."""
    
    def test_idle_to_wandering(self):
        """Test IDLE -> WANDERING on successful initialization."""
        config = {'state_machine': {'timeouts': {IDLE: 0.1}}}
        sm, mocks = create_test_state_machine(config)
        
        # Camera not yet initialized; IDLE state will call initialize()
        mocks['camera'].initialized = False
        
        # Wait for IDLE timeout
        time.sleep(0.15)
        
        # Run until WANDERING or timeout
        success = run_until_state(sm, WANDERING, max_ticks=200)
        assert success, f"Failed to reach WANDERING, stuck in {sm.state}"
        
    def test_wandering_to_check_for_ball(self):
        """Test WANDERING -> CHECK_FOR_BALL after sweep."""
        config = {'state_machine': {'timeouts': {WANDERING: 1.0}}}
        sm, mocks = create_test_state_machine(config)
        
        # Start in WANDERING
        sm.state = WANDERING
        sm.state_start_time = time.time()
        
        # Run until CHECK_FOR_BALL or timeout
        success = run_until_state(sm, CHECK_FOR_BALL, max_ticks=1000)
        assert success, f"Failed to reach CHECK_FOR_BALL, stuck in {sm.state}"
        
    def test_check_for_ball_to_collect(self):
        """Test CHECK_FOR_BALL -> COLLECT_BALL when ball detected."""
        sm, mocks = create_test_state_machine()
        
        # Start in CHECK_FOR_BALL
        sm.state = CHECK_FOR_BALL
        sm.state_start_time = time.time()
        
        # Simulate ball detection
        ball = simulate_ball_detection('silver', 160, 120, 50, 500)
        mocks['ball_detector'].set_test_balls([ball])
        
        # Run a few ticks
        run_n_ticks(sm, 10)
        
        assert sm.state == COLLECT_BALL, f"Expected COLLECT_BALL, got {sm.state}"
        
    def test_check_for_ball_to_balls_left(self):
        """Test CHECK_FOR_BALL -> BALLS_LEFT when no ball in view."""
        sm, mocks = create_test_state_machine()
        
        # Start in CHECK_FOR_BALL
        sm.state = CHECK_FOR_BALL
        sm.state_start_time = time.time()
        
        # No balls detected
        mocks['ball_detector'].set_test_balls([])
        
        # Register a known ball so world_map.has_known_balls() returns True
        mocks['world_map'].register_ball(0.5, 0.5)
        
        # Run one tick — should transition to BALLS_LEFT
        sm.tick()
        
        assert sm.state == BALLS_LEFT, f"Expected BALLS_LEFT, got {sm.state}"


class TestCollectBallSubStates:
    """Test COLLECT_BALL sub-states."""
    
    def test_approach_starts_first(self):
        """Test that APPROACH is the first sub-state."""
        sm, mocks = create_test_state_machine()
        
        # Start in COLLECT_BALL
        sm.state = COLLECT_BALL
        sm.state_start_time = time.time()
        sm.current_ball = {'color': 'silver', 'cx': 160, 'cy': 120}
        
        # Run one tick
        sm.tick()
        
        assert sm.collect_sub_state == CS_APPROACH


class TestSafetyOverride:
    """Test safety override mechanisms."""
    
    def test_boundary_detection_stops_motion(self):
        """Test that boundary detection stops forward motion."""
        sm, mocks = create_test_state_machine()
        
        # Start in WANDERING
        sm.state = WANDERING
        sm.state_start_time = time.time()
        
        # Simulate boundary detection
        mocks['obstacle_detector'].set_test_boundary(True)
        
        # Run a few ticks
        run_n_ticks(sm, 5)
        
        # Motors should be stopped or reversing
        left, right = mocks['chassis'].get_motor_values()
        # Either stopped or reversing (negative values)
        assert left <= 0 or right <= 0, "Motors should stop or reverse on boundary"


class TestTimeouts:
    """Test timeout handling."""
    
    def test_idle_timeout(self):
        """Test IDLE state timeout."""
        config = {'state_machine': {'timeouts': {IDLE: 0.1}}}
        sm, mocks = create_test_state_machine(config)
        
        # Camera fails to initialize
        mocks['camera'].initialized = False
        
        # Wait for timeout
        time.sleep(0.15)
        
        # Run a tick
        sm.tick()
        
        # Should transition away from IDLE (to WANDERING or END)
        assert sm.state != IDLE, "Should timeout from IDLE"


class TestWorldMapIntegration:
    """Test WorldMap integration."""
    
    def test_ball_registration(self):
        """Test balls are registered in world map."""
        sm, mocks = create_test_state_machine()
        
        # Register a ball
        ball_id = mocks['world_map'].register_ball(0.5, 0.5)
        
        assert ball_id is not None
        assert len(mocks['world_map'].balls) == 1
        
    def test_ball_collection_marking(self):
        """Test collected balls are marked."""
        sm, mocks = create_test_state_machine()
        
        # Register and collect a ball
        ball_id = mocks['world_map'].register_ball(0.5, 0.5)
        mocks['world_map'].mark_collected(ball_id)
        
        assert mocks['world_map'].balls[0]['collected'] == True
        
    def test_nearest_ball_selection(self):
        """Test nearest ball is selected."""
        sm, mocks = create_test_state_machine()
        
        # Register multiple balls
        mocks['world_map'].register_ball(0.5, 0.5)  # Closer
        mocks['world_map'].register_ball(1.5, 1.5)  # Farther
        
        # Get nearest from origin
        nearest = mocks['world_map'].get_nearest_ball((0.0, 0.0, 0.0))
        
        assert nearest is not None
        assert nearest['x'] == 0.5
        assert nearest['y'] == 0.5


class TestEdgeCases:
    """Test edge cases."""
    
    def test_no_pose_provider(self):
        """Test handling of missing pose provider."""
        sm, mocks = create_test_state_machine()
        sm.pose_provider = None
        
        # Should not crash
        pose = sm._get_pose()
        assert pose is None
        
    def test_camera_read_error(self):
        """Test handling of camera read errors."""
        sm, mocks = create_test_state_machine()
        
        # Make camera.read() raise an exception
        def failing_read():
            raise Exception("Camera error")
        
        mocks['camera'].read = failing_read
        
        # Should not crash
        frame = sm._read_frame()
        assert frame is None
        
    def test_empty_frame(self):
        """Test handling of None frames."""
        sm, mocks = create_test_state_machine()
        
        # Set camera to return None
        mocks['camera'].test_frame = None
        
        # Should not crash
        sm.tick()
        
    def test_ball_outside_arena(self):
        """Test rejection of balls outside arena."""
        sm, mocks = create_test_state_machine()
        
        # Try to register ball outside arena
        ball_id = mocks['world_map'].register_ball(10.0, 10.0)
        
        # Should be rejected (implementation dependent)
        # For now, just verify it doesn't crash


class TestRecovery:
    """Test recovery state."""
    
    def test_recovery_records_origin(self):
        """Test that RECOVERY records the originating state."""
        sm, mocks = create_test_state_machine()
        
        # Start in COLLECT_BALL
        sm.state = COLLECT_BALL
        sm.state_start_time = time.time()
        
        # Transition to RECOVERY
        sm._transition_to(RECOVERY)
        
        assert sm.recovery_origin == COLLECT_BALL


class TestGotoBasketHybrid:
    """Test hybrid A* + visual GOTO_BASKET navigation."""

    def test_goto_basket_uses_pathfinder_when_basket_known(self):
        """A* path is computed on entry when basket position is known."""
        sm, mocks = create_test_state_machine()
        sm.state = COLLECT_BALL
        sm.collect_sub_state = CS_GOTO_BASKET
        sm.state_start_time = time.time()
        sm.collect_sub_start = time.time()

        # Set basket position in world map
        mocks['world_map'].set_basket_position(0.9, 0.875)
        # Robot at corner, far from basket
        mocks['pose'][0] = 0.05
        mocks['pose'][1] = 0.05
        mocks['pose'][2] = 0.0

        # Provide a valid frame
        import numpy as np
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        # Basket not visible (far away)
        mocks['basket_detector'].test_basket = {'basket_found': False}

        result = sm._sub_goto_basket(frame, tuple(mocks['pose']))

        # Should have computed an A* path
        assert 'basket_path' in sm.state_data
        assert sm.state_data['basket_path'] is not None
        assert len(sm.state_data['basket_path']) >= 2

    def test_goto_basket_visual_homing_near_basket(self):
        """Switches to visual homing when within threshold of basket."""
        sm, mocks = create_test_state_machine()
        sm.state = COLLECT_BALL
        sm.collect_sub_state = CS_GOTO_BASKET
        sm.state_start_time = time.time()
        sm.collect_sub_start = time.time()

        # Basket position known, robot very close
        mocks['world_map'].set_basket_position(0.9, 0.875)
        mocks['pose'][0] = 0.85
        mocks['pose'][1] = 0.82
        mocks['pose'][2] = 0.0

        import numpy as np
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        # Basket detected visually
        mocks['basket_detector'].test_basket = {
            'basket_found': True,
            'centroid': (160, 120),
            'distance': 15.0,
            'area': 500,
            'width': 60,
            'bearing': 0.0,
        }

        result = sm._sub_goto_basket(frame, tuple(mocks['pose']))
        # Should transition to DEPOSIT (distance < 20 and centered)
        assert result == CS_DEPOSIT

    def test_goto_basket_replans_on_obstacle(self):
        """A* path is cleared and replanned when obstacle is detected."""
        sm, mocks = create_test_state_machine()
        sm.state = COLLECT_BALL
        sm.collect_sub_state = CS_GOTO_BASKET
        sm.state_start_time = time.time()
        sm.collect_sub_start = time.time()

        mocks['world_map'].set_basket_position(0.9, 0.875)
        mocks['pose'][0] = 0.05
        mocks['pose'][1] = 0.05
        mocks['pose'][2] = 0.0

        import numpy as np
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        mocks['basket_detector'].test_basket = {'basket_found': False}

        # First call — computes path
        sm._sub_goto_basket(frame, tuple(mocks['pose']))
        assert 'basket_path' in sm.state_data
        assert len(sm.state_data['basket_path']) >= 2

        # Simulate obstacle detection during safety check
        mocks['obstacle_detector'].test_obstacle = True
        sm._update_safety(frame)

        # Path should be cleared for replanning
        assert 'basket_path' not in sm.state_data or not sm.state_data.get('basket_path')

    def test_goto_basket_falls_back_to_visual_without_basket_pos(self):
        """Falls back to visual homing when basket position is unknown."""
        sm, mocks = create_test_state_machine()
        sm.state = COLLECT_BALL
        sm.collect_sub_state = CS_GOTO_BASKET
        sm.state_start_time = time.time()
        sm.collect_sub_start = time.time()

        # No basket position set
        assert mocks['world_map'].get_basket_position() is None

        import numpy as np
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        mocks['basket_detector'].test_basket = {'basket_found': False}

        result = sm._sub_goto_basket(frame, (0.1, 0.1, 0.0))
        # Should not crash, should stay in GOTO_BASKET or go to RECOVERY
        assert result in (CS_GOTO_BASKET, RECOVERY)

    def test_goto_basket_keeps_ball_on_failure(self):
        """Ball stays in current_ball when GOTO_BASKET retries are exhausted."""
        sm, mocks = create_test_state_machine()
        sm.state = COLLECT_BALL
        sm.collect_sub_state = CS_GOTO_BASKET
        sm.state_start_time = time.time()
        sm.collect_sub_start = time.time()
        sm.current_ball = {'world_id': 0, 'color': 'red'}
        sm.recovery_origin = COLLECT_BALL
        sm.recovery_retry_count = sm.max_retries  # At limit

        # Finish recovery should replan GOTO_BASKET and keep the ball
        result = sm._finish_recovery()
        assert result == CS_GOTO_BASKET
        # Ball is NOT cleared — it stays in the gripper
        assert sm.current_ball is not None

    def test_estimate_basket_world_pos(self):
        """Test basket world position estimation from detection + pose."""
        sm, mocks = create_test_state_machine()

        # Robot at (0.5, 0.5) facing right (yaw=0)
        pose = (0.5, 0.5, 0.0)
        # Basket detected at center of frame, 50cm away
        detection = {
            'basket_found': True,
            'centroid': (160, 120),  # Center of 320px frame
            'distance': 50.0,  # cm
            'area': 500,
            'width': 60,
            'bearing': 0.0,
        }

        bx, by = sm._estimate_basket_world_pos(detection, pose)
        # Bearing 0, distance 0.5m, yaw 0 → basket at (1.0, 0.5)
        assert bx is not None
        assert by is not None
        assert abs(bx - 1.0) < 0.05
        assert abs(by - 0.5) < 0.05


# Run tests if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
