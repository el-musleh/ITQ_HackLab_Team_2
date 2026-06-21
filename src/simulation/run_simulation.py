"""
Full Autonomous Simulation - Phase 3
Runs the real StateMachine (detector + chassis + arm + camera + world_map)
against the PyBullet simulation, with optional OpenCV visualization.

This mirrors the wiring used by ``src/simulation/tests/test_scenario_happy_path.py``
but supports the full 22-ball run with a time limit, telemetry, and a run
summary.
"""

import argparse
import logging
import os
import sys
import time

import cv2

# Add project root to path so `src.*` imports work when run as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.control.state_machine import StateMachine
from src.control.world_map import WorldMap
from src.perception.ball_detector import BallDetector
from src.perception.basket_detector import BasketDetector
from src.perception.obstacle_detector import ObstacleDetector
from src.simulation import SimulationCore, create_sim_hardware
from src.utils import load_config


logger = logging.getLogger(__name__)


class SimulationRunner:
    """Manages a full autonomous simulation run using the real StateMachine."""

    def __init__(self, config, gui=True, real_time=True, max_duration=300,
                 num_balls=22, start_corner=(0.0, 0.0),
                 start_pos=(0.0, 0.0, 0.15), show_visualization=True):
        """
        Initialize simulation runner.

        Args:
            config: Configuration dictionary.
            gui: Show PyBullet GUI.
            real_time: Run at real-time speed.
            max_duration: Maximum run duration in seconds.
            num_balls: Number of balls to spawn.
            start_corner: (x, y) starting corner in meters (passed to SM).
            start_pos: (x, y, z) robot spawn position in meters.
            show_visualization: Show OpenCV debug window with detections.
        """
        self.config = config
        self.max_duration = max_duration
        self.show_visualization = show_visualization

        sim_config = config.get('simulation', {}) or {}

        # Initialize simulation
        self.sim = SimulationCore(gui=gui, real_time=real_time, config=config)
        self.sim.initialize()
        self.sim.load_arena()
        robot_id = self.sim.load_robot(start_pos=list(start_pos))
        self.sim.spawn_balls(num_balls=num_balls)

        # Create hardware (pass sim so arm sequences step physics & grasp)
        self.chassis, self.arm, self.camera = create_sim_hardware(
            robot_id, config, sim=self.sim
        )

        # Create perception modules
        self.ball_detector = BallDetector(config)
        self.obstacle_detector = ObstacleDetector(config)
        self.basket_detector = BasketDetector(config)

        # Arena bounds + obstacle positions for the world map (must match
        # arena.urdf: ground centered at (0.9, 0.875); obstacles offset from
        # ground center by (-0.40, +0.40) and (+0.40, -0.40)).
        arena = config.get('arena', {})
        arena_bounds = {
            'x_min': 0.0,
            'x_max': arena.get('width_cm', 175) / 100.0,
            'y_min': 0.0,
            'y_max': arena.get('height_cm', 180) / 100.0,
        }
        obstacle_positions = [
            {'x': 0.9 - 0.40, 'y': 0.875 + 0.40, 'width': 0.30, 'height': 0.20},
            {'x': 0.9 + 0.40, 'y': 0.875 - 0.40, 'width': 0.40, 'height': 0.30},
        ]
        wm_cfg = config.get('world_map', {})
        self.world_map = WorldMap(
            arena_bounds,
            obstacle_positions=obstacle_positions,
            grid_resolution=wm_cfg.get('grid_resolution', 0.1),
            view_radius=wm_cfg.get('view_radius', 0.8),
            merge_distance=wm_cfg.get('merge_distance', 0.1),
            basket_position=self.sim.basket_position,
        )

        def get_pose():
            state = self.sim.get_robot_state()
            pos = state['position']
            yaw = state['orientation'][2]
            return pos[0], pos[1], yaw

        self.pose_provider = get_pose

        # Create state machine (real API)
        self.state_machine = StateMachine(
            ball_detector=self.ball_detector,
            basket_detector=self.basket_detector,
            obstacle_detector=self.obstacle_detector,
            chassis=self.chassis,
            arm=self.arm,
            camera=self.camera,
            world_map=self.world_map,
            config=config,
            pose_provider=self.pose_provider,
            start_corner=start_corner,
            logger=logger,
        )

        # Telemetry
        self.start_time = None
        self.collisions = 0
        self.physics_steps_per_tick = int(sim_config.get('steps_per_tick', 12))

    def visualize(self, frame, state):
        """Create a debug visualization overlay on the camera frame."""
        display = frame.copy()

        # Draw state info
        cv2.putText(display, f"State: {state}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(display, f"Balls: {self.state_machine.balls_collected}",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        elapsed = time.time() - self.start_time
        cv2.putText(display, f"Time: {elapsed:.1f}s", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        return display

    def run(self):
        """Run autonomous simulation until completion or timeout."""
        print("\n" + "=" * 60)
        print("AUTONOMOUS SIMULATION RUN")
        print("=" * 60)
        print(f"Max duration: {self.max_duration} seconds")
        print(f"Balls spawned: {len(self.sim.get_ball_ids())}")
        print(f"Locomotion: {self.chassis.locomotion_mode}")
        print("Starting in 3 seconds...")

        for i in range(3, 0, -1):
            print(f"  {i}...")
            time.sleep(1)

        print("\nSTARTING AUTONOMOUS RUN!\n")

        self.start_time = time.time()
        last_print = time.time()
        tick_count = 0

        try:
            while True:
                elapsed = time.time() - self.start_time
                if elapsed > self.max_duration:
                    print(f"\nTime limit reached ({self.max_duration}s)")
                    break

                # Run one state machine tick (reads frame, decides, acts)
                running = self.state_machine.tick()

                # Step physics to let actions take effect
                for _ in range(self.physics_steps_per_tick):
                    self.sim.step()

                # Optional collision telemetry (robot vs arena)
                if self.sim.check_collision(self.sim.robot_id, self.sim.arena_id):
                    if abs(self.chassis.left_value) > 0.01 or abs(self.chassis.right_value) > 0.01:
                        self.collisions += 1

                # Optional visualization (re-read a frame for display)
                if self.show_visualization:
                    frame = self.camera.read()
                    if frame is not None and frame.size > 0:
                        debug = self.visualize(frame, self.state_machine.state)
                        cv2.imshow('Autonomous Run', debug)
                        cv2.waitKey(1)

                tick_count += 1

                if time.time() - last_print > 5.0:
                    print(f"[{elapsed:.1f}s] State: {self.state_machine.state}, "
                          f"Balls: {self.state_machine.balls_collected}, "
                          f"Ticks: {tick_count}")
                    last_print = time.time()

                if not running:
                    status = self.state_machine.get_status()
                    if status.get('fatal_error'):
                        logger.error("Run ended with error: %s",
                                     status['fatal_error'])
                    else:
                        print("Mission complete!")
                    break

        except KeyboardInterrupt:
            print("\n\nStopped by user")

        finally:
            self.chassis.stop()
            if self.show_visualization:
                cv2.destroyAllWindows()
            self.print_summary()

    def print_summary(self):
        """Print run summary."""
        elapsed = time.time() - self.start_time

        print("\n" + "=" * 60)
        print("RUN SUMMARY")
        print("=" * 60)
        print(f"Duration:          {elapsed:.1f} seconds")
        print(f"Balls Collected:   {self.state_machine.balls_collected}")
        print(f"Collisions:        {self.collisions}")
        print(f"Final State:       {self.state_machine.state}")
        print("=" * 60)

        if self.state_machine.balls_collected >= 10 and self.collisions == 0:
            print("EXCELLENT! Ready for competition!")
        elif self.state_machine.balls_collected >= 5 and self.collisions <= 1:
            print("GOOD! System working well.")
        elif self.state_machine.balls_collected >= 1:
            print("NEEDS TUNING. Basic functionality works.")
        else:
            print("NEEDS DEBUGGING. Check perception and control.")

    def close(self):
        """Cleanup."""
        self.sim.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Phase 3: Full autonomous simulation')
    parser.add_argument('--headless', action='store_true',
                        help='Run without GUI or OpenCV visualization '
                             '(for CI / automated testing)')
    parser.add_argument('--duration', type=int, default=None,
                        help='Max run duration in seconds (default: from config)')
    parser.add_argument('--balls', type=int, default=None,
                        help='Number of balls to spawn (default: from config)')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s')
    print("=" * 60)
    print("PHASE 3: Full Autonomous Simulation")
    print("=" * 60)

    config = load_config()
    config.setdefault('simulation', {})
    if args.headless:
        config['simulation'] = {**config['simulation'], 'renderer': 'tiny'}

    sim_config = config.get('simulation', {}) or {}
    runner = SimulationRunner(
        config,
        gui=sim_config.get('gui', not args.headless) and not args.headless,
        real_time=sim_config.get('real_time', not args.headless) and not args.headless,
        max_duration=args.duration if args.duration is not None
                     else sim_config.get('max_duration_sec', 300),
        num_balls=args.balls if args.balls is not None
                   else sim_config.get('num_balls', 22),
        show_visualization=sim_config.get('show_visualization', True)
                            and not args.headless,
    )

    try:
        runner.run()
    finally:
        runner.close()


if __name__ == "__main__":
    main()
