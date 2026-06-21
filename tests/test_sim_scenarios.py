"""Headless scenario tests for the full state machine in simulation.

These tests run the real StateMachine against the PyBullet simulation with
specific scenarios (single ball, boundary avoidance, obstacle avoidance,
timeout/recovery). All run headless with bounded tick budgets.
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


def _make_state_machine(sim, config, chassis, arm, camera, start_corner=(0.5, 0.5)):
    """Wire up a StateMachine with standard arena bounds and obstacles."""
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


def _run_sm(sm, sim, max_ticks=300, steps_per_tick=12):
    """Run the state machine for up to *max_ticks* ticks. Returns states seen."""
    for _ in range(60):
        sim.step()

    states_seen = set()
    try:
        for _ in range(max_ticks):
            running = sm.tick()
            states_seen.add(sm.state)
            for _ in range(steps_per_tick):
                sim.step()
            if sm.fatal_error or not running:
                break
    finally:
        sim.close()

    return states_seen, sm


# ---------------------------------------------------------------------------
# Scenario 1: Single-ball happy path
# ---------------------------------------------------------------------------

def test_one_ball_no_fatal_error():
    """StateMachine ticks against a single-ball sim without a fatal error."""
    cfg = load_config()
    cfg.setdefault('simulation', {})
    cfg['simulation'] = {**cfg['simulation'], 'renderer': 'tiny',
                         'ball_spawn_seed': 1, 'locomotion_mode': 'velocity'}

    sim = SimulationCore(gui=False, real_time=False, config=cfg)
    sim.initialize()
    sim.load_arena()
    sim.load_robot(start_pos=[0.5, 0.5, 0.15])
    sim.spawn_balls(num_balls=1)
    chassis, arm, camera = create_sim_hardware(sim.robot_id, cfg, sim=sim)

    sm = _make_state_machine(sim, cfg, chassis, arm, camera)
    states_seen, sm = _run_sm(sm, sim, max_ticks=300)

    assert sm.fatal_error is None, f"Fatal error: {sm.fatal_error}"
    assert len(states_seen) >= 1, "State machine never ticked"


# ---------------------------------------------------------------------------
# Scenario 2: Boundary avoidance
# ---------------------------------------------------------------------------

def test_boundary_avoidance_no_fatal_error():
    """Robot placed near a wall should not crash the state machine."""
    cfg = load_config()
    cfg.setdefault('simulation', {})
    cfg['simulation'] = {**cfg['simulation'], 'renderer': 'tiny',
                         'ball_spawn_seed': 1, 'locomotion_mode': 'velocity'}

    sim = SimulationCore(gui=False, real_time=False, config=cfg)
    sim.initialize()
    sim.load_arena()
    sim.load_robot(start_pos=[1.6, 0.5, 0.15])
    sim.spawn_balls(num_balls=2)
    chassis, arm, camera = create_sim_hardware(sim.robot_id, cfg, sim=sim)

    sm = _make_state_machine(sim, cfg, chassis, arm, camera,
                             start_corner=(1.6, 0.5))
    states_seen, sm = _run_sm(sm, sim, max_ticks=200)

    assert sm.fatal_error is None, f"Fatal error near boundary: {sm.fatal_error}"


# ---------------------------------------------------------------------------
# Scenario 3: Obstacle avoidance
# ---------------------------------------------------------------------------

def test_obstacle_present_no_fatal_error():
    """Robot placed near an obstacle should not crash the state machine."""
    cfg = load_config()
    cfg.setdefault('simulation', {})
    cfg['simulation'] = {**cfg['simulation'], 'renderer': 'tiny',
                         'ball_spawn_seed': 1, 'locomotion_mode': 'velocity'}

    sim = SimulationCore(gui=False, real_time=False, config=cfg)
    sim.initialize()
    sim.load_arena()
    # Place robot near the first obstacle at (0.5, 1.275)
    sim.load_robot(start_pos=[0.5, 1.0, 0.15])
    sim.spawn_balls(num_balls=2)
    chassis, arm, camera = create_sim_hardware(sim.robot_id, cfg, sim=sim)

    sm = _make_state_machine(sim, cfg, chassis, arm, camera,
                             start_corner=(0.5, 1.0))
    states_seen, sm = _run_sm(sm, sim, max_ticks=200)

    assert sm.fatal_error is None, f"Fatal error near obstacle: {sm.fatal_error}"


# ---------------------------------------------------------------------------
# Scenario 4: Timeout / recovery
# ---------------------------------------------------------------------------

def test_short_timeout_no_fatal_error():
    """With a very short tick budget, the SM should exit gracefully."""
    cfg = load_config()
    cfg.setdefault('simulation', {})
    cfg['simulation'] = {**cfg['simulation'], 'renderer': 'tiny',
                         'ball_spawn_seed': 1, 'locomotion_mode': 'velocity'}

    sim = SimulationCore(gui=False, real_time=False, config=cfg)
    sim.initialize()
    sim.load_arena()
    sim.load_robot(start_pos=[0.5, 0.5, 0.15])
    sim.spawn_balls(num_balls=3)
    chassis, arm, camera = create_sim_hardware(sim.robot_id, cfg, sim=sim)

    sm = _make_state_machine(sim, cfg, chassis, arm, camera)
    states_seen, sm = _run_sm(sm, sim, max_ticks=10)

    assert sm.fatal_error is None, f"Fatal error on short timeout: {sm.fatal_error}"
    assert len(states_seen) >= 1
