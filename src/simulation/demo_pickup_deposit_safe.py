"""
Safe autonomous pickup and deposit demonstration using the shared state machine.

Runs in PyBullet simulation and uses the same control.state_machine.StateMachine
that drives the real robot.
"""

import sys
import os
import time
import yaml
import cv2
import numpy as np
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.simulation.sim_core import SimulationCore
from src.simulation import create_sim_hardware
from src.perception.ball_detector import BallDetector
from src.perception.basket_detector import BasketDetector
from src.perception.obstacle_detector import ObstacleDetector
from src.control.state_machine import StateMachine
from src.control.world_map import WorldMap
from src.utils import load_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('simulation_demo.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def check_robot_stability(sim, robot_id):
    """Check if robot is upright and stable."""
    state = sim.get_robot_state()
    pos = state['position']
    orn = state['orientation']

    if pos[2] < 0.01 or pos[2] > 0.3:
        logger.error(f"Robot height abnormal: {pos[2]:.3f}m")
        return False, "height"

    roll, pitch, yaw = orn
    max_tilt = 0.5
    if abs(roll) > max_tilt:
        logger.error(f"Robot rolled over! Roll: {np.rad2deg(roll):.1f}°")
        return False, "roll"
    if abs(pitch) > max_tilt:
        logger.error(f"Robot pitched over! Pitch: {np.rad2deg(pitch):.1f}°")
        return False, "pitch"

    return True, "stable"


def main():
    logger.info("=" * 60)
    logger.info("SAFE AUTONOMOUS PICKUP & DEPOSIT (State Machine)")
    logger.info("=" * 60)

    config = load_config()
    arena = config.get('arena', {})
    arena_bounds = {
        'x_min': 0.0,
        'x_max': arena.get('width_cm', 175) / 100.0,
        'y_min': 0.0,
        'y_max': arena.get('height_cm', 180) / 100.0,
    }

    # Obstacle positions in world coordinates (arena ground is at world 0.9, 0.875)
    obstacle_positions = [
        {'x': 0.9 - 0.40, 'y': 0.875 + 0.40, 'width': 0.30, 'height': 0.20},
        {'x': 0.9 + 0.40, 'y': 0.875 - 0.40, 'width': 0.40, 'height': 0.30},
    ]

    logger.info("Initializing simulation...")
    sim = SimulationCore(gui=True, real_time=True)
    sim.initialize()
    sim.load_arena()
    robot_id = sim.load_robot(start_pos=[0, 0, 0.15])
    sim.spawn_balls(num_balls=22)

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
    logger.info("Letting robot settle...")
    for _ in range(120):
        sim.step()

    stable, reason = check_robot_stability(sim, robot_id)
    if not stable:
        logger.error(f"Robot unstable at start: {reason}")
        sim.close()
        return

    logger.info("Robot stable, starting state machine...")

    try:
        while True:
            running = state_machine.tick()

            for _ in range(12):
                sim.step()
                time.sleep(0.001)

            stable, reason = check_robot_stability(sim, robot_id)
            if not stable:
                logger.error(f"Robot became unstable: {reason}")
                break

            if not running:
                status = state_machine.get_status()
                if status['fatal_error']:
                    logger.error(f"Run ended with error: {status['fatal_error']}")
                else:
                    logger.info("Mission complete!")
                break

    except KeyboardInterrupt:
        logger.info("Demo stopped by user")
    except Exception as e:
        logger.error(f"Error during demo: {e}", exc_info=True)
    finally:
        chassis.stop()
        cv2.destroyAllWindows()
        sim.close()
        logger.info("Demo ended")


if __name__ == "__main__":
    main()
