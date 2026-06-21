"""Test utilities for state machine testing."""

import time
from tests.mocks import (
    MockChassisController, MockArmController, MockCameraController,
    MockBallDetector, MockBasketDetector, MockObstacleDetector,
    MockWorldMap
)


def create_test_state_machine(config=None, logger=None):
    """
    Create a state machine with mock hardware for testing.
    
    Args:
        config: Optional configuration dict
        logger: Optional logger
        
    Returns:
        (state_machine, mocks) tuple where mocks is a dict of all mock objects
    """
    from control.state_machine import StateMachine
    
    config = config or {}
    
    # Create mock hardware
    chassis = MockChassisController()
    arm = MockArmController(config)
    camera = MockCameraController(config)
    
    # Create mock perception
    ball_detector = MockBallDetector(config)
    basket_detector = MockBasketDetector(config)
    obstacle_detector = MockObstacleDetector(config)
    
    # Create mock world map
    arena_bounds = {
        'x_min': 0.0,
        'x_max': 1.8,
        'y_min': 0.0,
        'y_max': 1.75,
    }
    world_map = MockWorldMap(arena_bounds)
    
    # Create pose provider
    test_pose = [0.0, 0.0, 0.0]  # x, y, yaw
    
    def pose_provider():
        return tuple(test_pose)
    
    # Create state machine
    state_machine = StateMachine(
        ball_detector=ball_detector,
        basket_detector=basket_detector,
        obstacle_detector=obstacle_detector,
        chassis=chassis,
        arm=arm,
        camera=camera,
        world_map=world_map,
        config=config,
        pose_provider=pose_provider,
        start_corner=(0.0, 0.0),
        logger=logger,
    )
    
    # Return state machine and mocks for test manipulation
    mocks = {
        'chassis': chassis,
        'arm': arm,
        'camera': camera,
        'ball_detector': ball_detector,
        'basket_detector': basket_detector,
        'obstacle_detector': obstacle_detector,
        'world_map': world_map,
        'pose': test_pose,
        'pose_provider': pose_provider,
    }
    
    return state_machine, mocks


def run_until_state(sm, target_state, max_ticks=1000):
    """
    Run state machine until target state is reached.
    
    Args:
        sm: StateMachine instance
        target_state: Target state name
        max_ticks: Maximum ticks to run
        
    Returns:
        True if target state reached, False if timeout
    """
    for _ in range(max_ticks):
        if sm.state == target_state:
            return True
        if not sm.tick():
            return False
        time.sleep(0.001)  # Small delay to prevent busy loop
    return False


def run_n_ticks(sm, n):
    """
    Run state machine for n ticks.
    
    Args:
        sm: StateMachine instance
        n: Number of ticks
        
    Returns:
        True if still running, False if finished
    """
    for _ in range(n):
        if not sm.tick():
            return False
        time.sleep(0.001)
    return True


def assert_state_transition(sm, from_state, to_state, max_ticks=100):
    """
    Assert that state machine transitions from one state to another.
    
    Args:
        sm: StateMachine instance
        from_state: Expected current state
        to_state: Expected next state
        max_ticks: Maximum ticks to wait for transition
        
    Returns:
        True if transition occurred, False otherwise
    """
    if sm.state != from_state:
        return False
    
    for _ in range(max_ticks):
        sm.tick()
        if sm.state == to_state:
            return True
        if sm.state != from_state and sm.state != to_state:
            # Transitioned to unexpected state
            return False
        time.sleep(0.001)
    
    return False


def simulate_ball_detection(color='silver', cx=160, cy=120, distance=50, area=500):
    """
    Create a simulated ball detection.
    
    Args:
        color: Ball color
        cx, cy: Center coordinates
        distance: Distance in cm
        area: Contour area
        
    Returns:
        Ball detection tuple
    """
    return (color, (cx, cy), distance, area)


def simulate_basket_detection(detected=True, center_x=160, distance_px=100):
    """
    Create a simulated basket detection.
    
    Args:
        detected: Whether basket is detected
        center_x: Center X coordinate
        distance_px: Distance in pixels
        
    Returns:
        Basket detection dict
    """
    if not detected:
        return {'detected': False}
    
    return {
        'detected': True,
        'center_x': center_x,
        'distance_px': distance_px,
        'angle': 0.0,
    }


def count_state_visits(sm, state_name):
    """
    Count how many times a state has been visited.
    
    Note: This requires the state machine to track visit counts,
    which is not currently implemented. This is a placeholder.
    
    Args:
        sm: StateMachine instance
        state_name: State name to count
        
    Returns:
        Visit count (currently always 0)
    """
    # TODO: Implement state visit tracking in StateMachine
    return 0


def get_state_history(sm):
    """
    Get the history of state transitions.
    
    Note: This requires the state machine to track history,
    which is not currently implemented. This is a placeholder.
    
    Args:
        sm: StateMachine instance
        
    Returns:
        List of state names (currently empty)
    """
    # TODO: Implement state history tracking in StateMachine
    return []


def wait_for_condition(condition_fn, timeout=5.0, check_interval=0.01):
    """
    Wait for a condition to become true.
    
    Args:
        condition_fn: Callable that returns True when condition is met
        timeout: Maximum time to wait in seconds
        check_interval: How often to check condition
        
    Returns:
        True if condition met, False if timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition_fn():
            return True
        time.sleep(check_interval)
    return False
