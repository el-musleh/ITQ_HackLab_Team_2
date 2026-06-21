"""Headless smoke tests for the PyBullet SimulationCore.

These tests run with ``p.DIRECT`` (no GUI) so they can execute in CI without
a display. They skip gracefully if ``pybullet`` is not installed.
"""

import os
import sys

import pytest

# Ensure project root is importable when run from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pybullet = pytest.importorskip("pybullet")

from src.simulation import SimulationCore  # noqa: E402
from src.utils import load_config  # noqa: E402

pytestmark = pytest.mark.simulation


@pytest.fixture
def sim():
    """Yield a headless SimulationCore with arena + robot + a few balls."""
    cfg = load_config()
    cfg.setdefault('simulation', {})
    cfg['simulation'] = {**cfg['simulation'], 'renderer': 'tiny',
                         'ball_spawn_seed': 123}
    s = SimulationCore(gui=False, real_time=False, config=cfg)
    s.initialize()
    s.load_arena()
    s.load_robot(start_pos=[0.5, 0.5, 0.15])
    s.spawn_balls(num_balls=3)
    yield s
    s.close()


def test_initialization(sim):
    """Simulation initializes with a valid physics client."""
    assert sim.physics_client is not None
    assert sim.robot_id is not None
    assert sim.arena_id is not None


def test_joint_discovery(sim):
    """Joint discovery finds the arm + claw roles and the four wheels."""
    jm = sim.get_joint_map()
    for role in ('base', 'shoulder', 'elbow', 'wrist'):
        assert role in jm, f"missing role {role}"
        assert jm[role] is not None
    wheels = sim.get_wheel_joint_indices()
    assert len(wheels) == 4


def test_spawn_balls(sim):
    """spawn_balls creates the requested number of balls."""
    assert len(sim.get_ball_ids()) == 3


def test_step_and_state(sim):
    """Stepping physics returns a valid robot state."""
    for _ in range(10):
        sim.step()
    state = sim.get_robot_state()
    assert state is not None
    assert len(state['position']) == 3
    assert len(state['orientation']) == 3


def test_reset_restores_start_pose(sim):
    """reset() returns the robot to the start pose used in load_robot."""
    # Move the robot a bit
    from src.simulation.sim_hardware import ChassisController
    chassis = ChassisController(sim.robot_id, sim=sim,
                                locomotion_mode='velocity')
    chassis.forward(0.2)
    for _ in range(60):
        sim.step()
    moved = sim.get_robot_state()['position']
    assert abs(moved[0] - 0.5) > 1e-4 or abs(moved[1] - 0.5) > 1e-4

    sim.reset()
    pos = sim.get_robot_state()['position']
    assert pos[0] == pytest.approx(0.5, abs=1e-6)
    assert pos[1] == pytest.approx(0.5, abs=1e-6)


def test_double_close_is_safe(sim):
    """close() can be called multiple times without error."""
    sim.close()
    sim.close()  # should not raise


def test_check_collision(sim):
    """check_collision returns a bool."""
    result = sim.check_collision(sim.robot_id, sim.arena_id)
    assert isinstance(result, bool)


def test_camera_view(sim):
    """get_camera_view returns an RGB image of the requested size."""
    img = sim.get_camera_view(width=64, height=48)
    assert img is not None
    assert img.shape == (48, 64, 3)


def test_grasp_attach_detach(sim):
    """attach_ball_to_gripper + detach_ball manage the constraint."""
    ball_id = sim.get_ball_ids()[0]
    cid = sim.attach_ball_to_gripper(ball_id)
    assert cid is not None
    assert sim.attached_ball_id == ball_id
    sim.detach_ball()
    assert sim.attached_ball_id is None
    assert sim._grasp_constraint_id is None
