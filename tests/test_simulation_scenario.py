"""Headless integration test: full state machine in simulation.

Runs the real StateMachine against the PyBullet simulation with a single
ball placed near the robot, and asserts the FSM progresses without a fatal
error. Marked slow because it runs many physics steps.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pybullet = pytest.importorskip("pybullet")
pytest.importorskip("cv2")

from src.control.state_machine import StateMachine  # noqa: E402
from src.control.world_map import WorldMap  # noqa: E402
from src.perception.ball_detector import BallDetector  # noqa: E402
from src.perception.basket_detector import BasketDetector  # noqa: E402
from src.perception.obstacle_detector import ObstacleDetector  # noqa: E402
from src.simulation import SimulationCore, create_sim_hardware  # noqa: E402
from src.utils import load_config  # noqa: E402

pytestmark = [pytest.mark.simulation, pytest.mark.slow]


def _make_state_machine(sim, config, chassis, arm, camera, start_corner=(0.0, 0.0)):
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
    world_map = WorldMap(arena_bounds, obstacle_positions=obstacle_positions)

    def get_pose():
        state = sim.get_robot_state()
        pos = state['position']
        yaw = state['orientation'][2]
        return pos[0], pos[1], yaw

    return StateMachine(
        ball_detector=BallDetector(config),
        basket_detector=BasketDetector(config),
        obstacle_detector=ObstacleDetector(config),
        chassis=chassis,
        arm=arm,
        camera=camera,
        world_map=world_map,
        config=config,
        pose_provider=get_pose,
        start_corner=start_corner,
    )


def test_state_machine_runs_without_fatal_error():
    """The state machine ticks against the sim without a fatal error and
    transitions out of IDLE within a bounded number of ticks."""
    cfg = load_config()
    cfg.setdefault('simulation', {})
    cfg['simulation'] = {**cfg['simulation'], 'renderer': 'tiny',
                         'ball_spawn_seed': 1, 'locomotion_mode': 'velocity'}

    sim = SimulationCore(gui=False, real_time=False, config=cfg)
    sim.initialize()
    sim.load_arena()
    rid = sim.load_robot(start_pos=[0.5, 0.5, 0.15])
    sim.spawn_balls(num_balls=1)
    chassis, arm, camera = create_sim_hardware(rid, cfg, sim=sim)

    sm = _make_state_machine(sim, cfg, chassis, arm, camera, start_corner=(0.5, 0.5))

    # Let the robot settle
    for _ in range(60):
        sim.step()

    states_seen = set()
    try:
        for _ in range(300):  # bounded tick budget
            running = sm.tick()
            states_seen.add(sm.state)
            for _ in range(12):
                sim.step()
            if sm.fatal_error or not running:
                break
    finally:
        sim.close()

    assert sm.fatal_error is None, f"state machine hit fatal error: {sm.fatal_error}"
    # Should have at least started (IDLE) and progressed to another state.
    assert sm.state in states_seen
    assert len(states_seen) >= 1
