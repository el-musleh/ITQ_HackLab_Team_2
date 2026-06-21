"""
Scenario Runner — Controlled simulation use-case demonstrations.

Three scenarios that exercise the real StateMachine against PyBullet with
specific arena configurations:

    1. lift_and_drop  — Ball placed in front of robot; pickup → deposit.
    2. target_ball    — Ball placed ~1 m away; navigate → approach → pickup → deposit.
    3. obstacle_search — Ball placed behind an obstacle; avoid → search → pickup → deposit.

Usage:
    python -m src.simulation.run_scenarios --scenario lift_and_drop
    python -m src.simulation.run_scenarios --scenario all
    python -m src.simulation.run_scenarios --scenario lift_and_drop --headless
"""

import argparse
import logging
import os
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.control.state_machine import StateMachine
from src.control.world_map import WorldMap
from src.perception.ball_detector import BallDetector
from src.perception.basket_detector import BasketDetector
from src.perception.obstacle_detector import ObstacleDetector
from src.simulation import SimulationCore, create_sim_hardware
from src.utils import load_config


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIOS = {
    'lift_and_drop': {
        'description': 'Ball placed in front of robot — pickup and deposit in basket.',
        'robot_start': [0.3, 0.3, 0.15],
        'robot_yaw': 0.785,          # ~45° toward arena center
        'balls': [
            {'x': 0.45, 'y': 0.45, 'color': 'blue'},
        ],
        'max_duration': 120,
        'expected_collisions': 0,
    },
    'target_ball': {
        'description': 'Ball placed ~1.3 m away — navigate, approach, pickup, deposit.',
        'robot_start': [0.2, 0.2, 0.15],
        'robot_yaw': 0.0,
        'balls': [
            {'x': 1.2, 'y': 1.0, 'color': 'red'},
        ],
        'max_duration': 180,
        'expected_collisions': 2,
    },
    'obstacle_search': {
        'description': 'Ball behind obstacle — navigate around, find, pickup, deposit.',
        'robot_start': [0.2, 0.2, 0.15],
        'robot_yaw': 0.0,
        'balls': [
            {'x': 1.4, 'y': 1.2, 'color': 'silver'},
        ],
        'max_duration': 240,
        'expected_collisions': 5,
    },
}


# ---------------------------------------------------------------------------
# ScenarioRunner
# ---------------------------------------------------------------------------

class ScenarioRunner:
    """Runs a single scenario with controlled arena setup and visualization."""

    def __init__(self, config, scenario_name, gui=True, real_time=True,
                 show_visualization=True):
        self.config = config
        self.scenario_name = scenario_name
        self.scenario = SCENARIOS[scenario_name]
        self.show_visualization = show_visualization
        self.max_duration = self.scenario['max_duration']

        sim_config = config.get('simulation', {}) or {}

        # Initialize simulation
        self.sim = SimulationCore(gui=gui, real_time=real_time, config=config)
        self.sim.initialize()
        self.sim.load_arena()

        start_pos = self.scenario['robot_start']
        start_orn = [0, 0, self.scenario['robot_yaw']]
        robot_id = self.sim.load_robot(start_pos=start_pos,
                                       start_orientation=start_orn)

        # Spawn balls at controlled positions
        for ball_spec in self.scenario['balls']:
            self.sim.spawn_ball_at(ball_spec['x'], ball_spec['y'],
                                   color=ball_spec.get('color', 'blue'))

        # Create hardware
        self.chassis, self.arm, self.camera = create_sim_hardware(
            robot_id, config, sim=self.sim
        )

        # Create perception
        self.ball_detector = BallDetector(config)
        self.basket_detector = BasketDetector(config)
        self.obstacle_detector = ObstacleDetector(config)

        # Arena bounds + obstacle positions for world map
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

        # Create state machine
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
            start_corner=(start_pos[0], start_pos[1]),
            logger=logger,
        )

        # Telemetry
        self.start_time = None
        self.collisions = 0
        self.physics_steps_per_tick = int(sim_config.get('steps_per_tick', 12))

    def _visualize(self, frame, state):
        """Create debug overlay on camera frame."""
        display = frame.copy()
        cv2.putText(display, f"Scenario: {self.scenario_name}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(display, f"State: {state}", (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(display, f"Balls: {self.state_machine.balls_collected}",
                    (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(display, f"Deposited: {self.sim.get_deposited_count()}",
                    (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        elapsed = time.time() - self.start_time
        cv2.putText(display, f"Time: {elapsed:.1f}s", (10, 125),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        return display

    def run(self):
        """Run the scenario until completion or timeout."""
        print("\n" + "=" * 60)
        print(f"SCENARIO: {self.scenario_name.upper()}")
        print("=" * 60)
        print(f"  {self.scenario['description']}")
        print(f"  Robot start: {self.scenario['robot_start']}")
        print(f"  Balls: {self.scenario['balls']}")
        print(f"  Max duration: {self.max_duration}s")
        if self.show_visualization:
            print("  Starting in 3 seconds...")
            for i in range(3, 0, -1):
                print(f"  {i}...")
                time.sleep(1)
            print("\nSTARTING SCENARIO!\n")

        # Let robot settle
        for _ in range(120):
            self.sim.step()

        self.start_time = time.time()
        last_print = time.time()
        tick_count = 0
        collision_last = False

        try:
            while True:
                elapsed = time.time() - self.start_time
                if elapsed > self.max_duration:
                    print(f"\nTime limit reached ({self.max_duration}s)")
                    break

                # Run one state machine tick
                running = self.state_machine.tick()

                # Step physics (re-apply chassis velocity each sub-step
                # so friction doesn't kill movement between ticks)
                for _ in range(self.physics_steps_per_tick):
                    self.chassis.step()
                    self.sim.step()

                # Collision telemetry
                if self.sim.check_collision(self.sim.robot_id, self.sim.arena_id):
                    if (abs(self.chassis.left_value) > 0.01 or
                            abs(self.chassis.right_value) > 0.01):
                        if not collision_last:
                            self.collisions += 1
                        collision_last = True
                    else:
                        collision_last = False
                else:
                    collision_last = False

                # Visualization
                if self.show_visualization:
                    frame = self.camera.read()
                    if frame is not None and frame.size > 0:
                        debug = self._visualize(frame, self.state_machine.state)
                        cv2.imshow(f'Scenario: {self.scenario_name}', debug)
                        cv2.waitKey(1)

                tick_count += 1

                if time.time() - last_print > 5.0:
                    print(f"[{elapsed:.1f}s] State: {self.state_machine.state}, "
                          f"Balls: {self.state_machine.balls_collected}, "
                          f"Deposited: {self.sim.get_deposited_count()}, "
                          f"Collisions: {self.collisions}, "
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

        return self._evaluate()

    def _evaluate(self):
        """Check pass/fail criteria and print summary."""
        elapsed = time.time() - self.start_time
        balls_collected = self.state_machine.balls_collected
        deposited = self.sim.get_deposited_count()
        max_allowed_collisions = self.scenario['expected_collisions']

        passed = (balls_collected >= 1 and deposited >= 1
                  and self.collisions <= max_allowed_collisions)

        print("\n" + "=" * 60)
        print(f"SCENARIO RESULT: {self.scenario_name.upper()}")
        print("=" * 60)
        print(f"  Duration:        {elapsed:.1f}s")
        print(f"  Balls Collected: {balls_collected}")
        print(f"  Balls Deposited: {deposited}")
        print(f"  Collisions:      {self.collisions} "
              f"(max allowed: {max_allowed_collisions})")
        print(f"  Final State:     {self.state_machine.state}")
        print(f"  Status:          {'PASS' if passed else 'FAIL'}")
        print("=" * 60)

        return passed

    def close(self):
        """Cleanup simulation."""
        self.sim.close()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_scenario(scenario_name, config, gui=True, real_time=True,
                 show_visualization=True):
    """Run a single scenario and return True if it passed."""
    runner = ScenarioRunner(
        config, scenario_name,
        gui=gui, real_time=real_time,
        show_visualization=show_visualization,
    )
    try:
        return runner.run()
    finally:
        runner.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Run controlled simulation scenarios')
    parser.add_argument(
        '--scenario', type=str, default='all',
        choices=['all'] + list(SCENARIOS.keys()),
        help='Which scenario to run (default: all)')
    parser.add_argument(
        '--headless', action='store_true',
        help='Run without GUI or OpenCV visualization')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s')

    print("=" * 60)
    print("SIMULATION SCENARIO RUNNER")
    print("=" * 60)

    config = load_config()
    config.setdefault('simulation', {})
    if args.headless:
        config['simulation'] = {**config['simulation'],
                                'renderer': 'tiny'}

    sim_config = config.get('simulation', {}) or {}
    gui = sim_config.get('gui', not args.headless) and not args.headless
    real_time = (sim_config.get('real_time', not args.headless)
                 and not args.headless)
    show_viz = (sim_config.get('show_visualization', True)
                and not args.headless)

    if args.scenario == 'all':
        names = list(SCENARIOS.keys())
    else:
        names = [args.scenario]

    results = {}
    for name in names:
        passed = run_scenario(name, config, gui=gui, real_time=real_time,
                              show_visualization=show_viz)
        results[name] = passed

    # Final summary
    print("\n" + "#" * 60)
    print("ALL SCENARIOS SUMMARY")
    print("#" * 60)
    for name, passed in results.items():
        status = 'PASS' if passed else 'FAIL'
        print(f"  {name:20s}  {status}")
    print("#" * 60)

    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
