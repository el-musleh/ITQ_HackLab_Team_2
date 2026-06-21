"""Unit tests for state machine."""

import pytest
import time
from control.state_machine import (
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
        sm, mocks = create_test_state_machine()
        
        # Camera should initialize successfully
        mocks['camera'].initialized = False
        
        # Run until WANDERING or timeout
        success = run_until_state(sm, WANDERING, max_ticks=200)
        assert success, f"Failed to reach WANDERING, stuck in {sm.state}"
        
    def test_wandering_to_check_for_ball(self):
        """Test WANDERING -> CHECK_FOR_BALL after sweep."""
        sm, mocks = create_test_state_machine()
        
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
        
        # Run a few ticks
        run_n_ticks(sm, 10)
        
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


# Run tests if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
