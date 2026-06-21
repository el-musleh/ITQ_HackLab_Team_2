"""Test scenario: Happy path - single ball collection."""

import sys
import os
import time
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.simulation.sim_core import SimulationCore
from src.simulation import create_sim_hardware
from src.perception.ball_detector import BallDetector
from src.perception.basket_detector import BasketDetector
from src.perception.obstacle_detector import ObstacleDetector
from src.control.state_machine import StateMachine, IDLE, WANDERING, CHECK_FOR_BALL, COLLECT_BALL, END
from src.control.world_map import WorldMap
from src.utils import load_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Test happy path: spawn 1 ball, collect it, deposit it."""
    logger.info("="*60)
    logger.info("TEST SCENARIO: HAPPY PATH - Single Ball Collection")
    logger.info("="*60)
    
    config = load_config()
    arena = config.get('arena', {})
    arena_bounds = {
        'x_min': 0.0,
        'x_max': arena.get('width_cm', 175) / 100.0,
        'y_min': 0.0,
        'y_max': arena.get('height_cm', 180) / 100.0,
    }
    
    # Obstacle positions
    obstacle_positions = [
        {'x': 0.9 - 0.40, 'y': 0.875 + 0.40, 'width': 0.30, 'height': 0.20},
        {'x': 0.9 + 0.40, 'y': 0.875 - 0.40, 'width': 0.40, 'height': 0.30},
    ]
    
    # Initialize simulation
    logger.info("Initializing simulation...")
    sim = SimulationCore(gui=True, real_time=True)
    sim.initialize()
    
    # Load robot at start corner
    robot_id = sim.load_robot(start_pos=[0, 0, 0.15])
    
    # Spawn only 1 ball near the robot for easy collection
    logger.info("Spawning 1 ball near robot...")
    sim.spawn_balls(num_balls=1)
    
    # Create hardware
    chassis, arm, camera = create_sim_hardware(robot_id, config)
    ball_detector = BallDetector(config)
    basket_detector = BasketDetector(config)
    obstacle_detector = ObstacleDetector(config)
    
    world_map = WorldMap(arena_bounds, obstacle_positions=obstacle_positions)
    
    def get_pose():
        state = sim.get_robot_state()
        pos = state['position']
        yaw = state['orientation'][2]
        return pos[0], pos[1], yaw
    
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
        pose_provider=get_pose,
        start_corner=(0.0, 0.0),
        logger=logger,
    )
    
    logger.info("Initialization complete")
    
    # Let robot settle
    logger.info("Letting robot settle...")
    for _ in range(120):
        sim.step()
    
    logger.info("Starting state machine...")
    
    # Track state transitions
    states_visited = []
    last_state = None
    
    try:
        tick_count = 0
        max_ticks = 5000  # ~3 minutes at 30Hz
        
        while tick_count < max_ticks:
            # Track state changes
            if state_machine.state != last_state:
                states_visited.append(state_machine.state)
                logger.info(f"State transition: {last_state} -> {state_machine.state}")
                last_state = state_machine.state
            
            # Run state machine tick
            running = state_machine.tick()
            
            # Step simulation
            for _ in range(12):
                sim.step()
                time.sleep(0.001)
            
            tick_count += 1
            
            if not running:
                status = state_machine.get_status()
                if status['fatal_error']:
                    logger.error(f"Run ended with error: {status['fatal_error']}")
                    break
                else:
                    logger.info("Mission complete!")
                    break
        
        if tick_count >= max_ticks:
            logger.warning("Test timeout reached")
        
        # Report results
        logger.info("="*60)
        logger.info("TEST RESULTS")
        logger.info("="*60)
        logger.info(f"States visited: {' -> '.join(states_visited)}")
        logger.info(f"Balls collected: {state_machine.balls_collected}")
        logger.info(f"Total ticks: {tick_count}")
        
        # Verify expected path
        expected_states = [IDLE, WANDERING, CHECK_FOR_BALL, COLLECT_BALL]
        success = all(state in states_visited for state in expected_states)
        
        if success and state_machine.balls_collected >= 1:
            logger.info("✓ TEST PASSED: Ball successfully collected and deposited")
            return 0
        else:
            logger.error("✗ TEST FAILED: Did not complete expected path")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Test stopped by user")
        return 1
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        sim.close()
        logger.info("Simulation closed")


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
