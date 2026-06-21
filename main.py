#!/usr/bin/env python3
"""Entry point for ITQ Bottle Cap Collector.

Run on the NVIDIA Jetson Nano via Jupyter or command line.
"""

import os
import sys
import time
import yaml

from perception.ball_detector import BallDetector
from perception.basket_detector import BasketDetector
from perception.obstacle_detector import ObstacleDetector
from hardware.chassis import ChassisController
from hardware.arm import ArmController
from hardware.camera import CameraController
from control.state_machine import StateMachine
from control.world_map import WorldMap
from control.odometry import DifferentialDriveOdometry


def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    print("=" * 50)
    print("ITQ Bottle Cap Collector — Team 2")
    print("=" * 50)

    config = load_config()
    arena = config.get('arena', {})
    arena_bounds = {
        'x_min': 0.0,
        'x_max': arena.get('width_cm', 175) / 100.0,
        'y_min': 0.0,
        'y_max': arena.get('height_cm', 180) / 100.0,
    }

    try:
        from jetbot import Robot
        robot = Robot()
    except Exception as e:
        print(f"Failed to initialize jetbot.Robot: {e}")
        sys.exit(1)

    chassis = ChassisController(robot, max_speed=config.get('motors', {}).get('max_speed', 0.25))
    arm = ArmController(config)
    camera = CameraController(config)

    ball_detector = BallDetector(config)
    basket_detector = BasketDetector(config)
    obstacle_detector = ObstacleDetector(config)

    world_map = WorldMap(arena_bounds)
    odometry = DifferentialDriveOdometry(
        robot,
        wheel_base=0.19,
        max_speed=config.get('motors', {}).get('max_speed', 0.25)
    )

    state_machine = StateMachine(
        ball_detector=ball_detector,
        basket_detector=basket_detector,
        obstacle_detector=obstacle_detector,
        chassis=chassis,
        arm=arm,
        camera=camera,
        world_map=world_map,
        config=config,
        pose_provider=odometry.update,
        start_corner=(0.0, 0.0),
    )

    print("Hardware initialized. Starting state machine...")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            running = state_machine.tick()
            if not running:
                status = state_machine.get_status()
                if status['fatal_error']:
                    print(f"\nFATAL ERROR: {status['fatal_error']}")
                else:
                    print("\nMission complete.")
                break
            time.sleep(0.05)  # 20 Hz control loop
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        chassis.stop()
        arm.home()
        camera.release()
        sys.exit(0)


if __name__ == "__main__":
    main()
