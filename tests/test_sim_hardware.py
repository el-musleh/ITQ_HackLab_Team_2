"""Headless tests for the simulated hardware interfaces.

Verifies the drop-in hardware API (ChassisController, ArmController,
CameraController) against the PyBullet simulation. Skips gracefully if
``pybullet`` or ``cv2`` are not installed.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pybullet = pytest.importorskip("pybullet")
pytest.importorskip("cv2")

from src.simulation import SimulationCore, create_sim_hardware  # noqa: E402
from src.utils import load_config  # noqa: E402

pytestmark = pytest.mark.simulation


@pytest.fixture
def hw():
    """Yield (sim, chassis, arm, camera) wired together headlessly."""
    cfg = load_config()
    cfg.setdefault('simulation', {})
    cfg['simulation'] = {**cfg['simulation'], 'renderer': 'tiny',
                         'ball_spawn_seed': 7, 'locomotion_mode': 'velocity'}
    sim = SimulationCore(gui=False, real_time=False, config=cfg)
    sim.initialize()
    sim.load_arena()
    rid = sim.load_robot(start_pos=[0.5, 0.5, 0.15])
    sim.spawn_balls(num_balls=2)
    chassis, arm, camera = create_sim_hardware(rid, cfg, sim=sim)
    yield sim, chassis, arm, camera
    sim.close()


def test_chassis_stop_and_values(hw):
    sim, chassis, _, _ = hw
    chassis.stop()
    assert chassis.get_motor_values() == (0.0, 0.0)


def test_chassis_forward_clamps(hw):
    sim, chassis, _, _ = hw
    chassis.forward(5.0)  # above max_speed -> clamped
    left, right = chassis.get_motor_values()
    assert left == pytest.approx(chassis.max_speed)
    assert right == pytest.approx(chassis.max_speed)


def test_chassis_turn_left(hw):
    sim, chassis, _, _ = hw
    chassis.turn_left(0.1)
    left, right = chassis.get_motor_values()
    assert left < 0
    assert right > 0


def test_chassis_velocity_mode_moves_robot(hw):
    sim, chassis, _, _ = hw
    start = sim.get_robot_state()['position']
    chassis.forward(0.2)
    for _ in range(120):
        sim.step()
    end = sim.get_robot_state()['position']
    # Robot should have moved off the start position.
    assert (end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2 > 1e-6


def test_arm_move_to_pose_list(hw):
    sim, _, arm, _ = hw
    assert arm.move_to_pose([0, -40, -60, 0]) is True
    for _ in range(60):
        sim.step()
    assert arm.get_current_pose() == [0, -40, -60, 0]


def test_arm_move_to_pose_string(hw):
    """move_to_pose accepts pose name strings (fixes test_basic_motion.py)."""
    sim, _, arm, _ = hw
    for name in ('home', 'pickup', 'carry', 'deposit'):
        assert arm.move_to_pose(name) is True
        for _ in range(30):
            sim.step()


def test_arm_move_to_pose_unknown_string_returns_false(hw):
    """Unknown pose names log an error and return False (don't raise)."""
    sim, _, arm, _ = hw
    assert arm.move_to_pose('nonexistent_pose') is False


def test_arm_gripper_open_close(hw):
    sim, _, arm, _ = hw
    assert arm.gripper_open() is True
    assert arm.gripper_close() is True


def test_arm_pickup_and_deposit_sequences(hw):
    """pickup_sequence and deposit_sequence execute and return True."""
    sim, _, arm, _ = hw
    assert arm.pickup_sequence() is True
    assert arm.deposit_sequence() is True


def test_gripper_close_attaches_nearby_ball(hw):
    """Closing the gripper attaches a ball in the pickup zone."""
    sim, _, arm, _ = hw
    ball_id = sim.spawn_ball_at(0.66, 0.5, color='blue')
    arm.move_to_pose(arm.pose_pickup)
    for _ in range(60):
        sim.step()

    assert arm.gripper_close() is True
    for _ in range(30):
        sim.step()

    assert sim.attached_ball_id == ball_id


def test_gripper_open_marks_deposit_near_basket(hw):
    """A held ball released near the basket is counted as deposited."""
    sim, _, arm, _ = hw
    ball_id = sim.spawn_ball_at(0.66, 0.5, color='blue')
    arm.move_to_pose(arm.pose_pickup)
    for _ in range(60):
        sim.step()
    arm.gripper_close()
    for _ in range(30):
        sim.step()
    assert sim.attached_ball_id == ball_id

    pybullet.resetBasePositionAndOrientation(
        sim.robot_id, [0.9, 0.875, 0.15], [0, 0, 0, 1]
    )
    for _ in range(30):
        sim.step()
    assert arm.gripper_open() is True

    assert sim.attached_ball_id is None
    assert sim.get_deposited_count() == 1


def test_camera_read_shape(hw):
    sim, _, _, camera = hw
    frame = camera.read()
    assert frame is not None
    # get_frame_size() returns (width, height); image shape is (height, width, 3)
    w, h = camera.get_frame_size()
    assert frame.shape == (h, w, 3)


def test_camera_pan_tilt(hw):
    sim, _, _, camera = hw
    assert camera.set_pan(30) is True
    assert camera.get_pan() == 30
    assert camera.set_tilt(-20) is True
    # pan/tilt are clamped
    camera.set_pan(200)
    assert camera.get_pan() == 90
    camera.set_tilt(-200)
    assert camera.tilt_angle == -60


def test_camera_fov_from_config(hw):
    sim, _, _, camera = hw
    # config.yaml simulation.camera_fov defaults to 160
    assert camera.fov == 160


# ---------------------------------------------------------------------------
# Phase 2.3 — Additional chassis tests
# ---------------------------------------------------------------------------

def test_chassis_turn_changes_yaw(hw):
    """Turning in place changes the robot's yaw."""
    sim, chassis, _, _ = hw
    start_yaw = sim.get_robot_state()['orientation'][2]
    chassis.turn_left(0.15)
    for _ in range(120):
        sim.step()
    end_yaw = sim.get_robot_state()['orientation'][2]
    delta = abs(end_yaw - start_yaw)
    delta = min(delta, 2 * 3.14159 - delta)
    assert delta > 0.05, f"Yaw delta {delta:.4f} rad too small"


def test_collision_at_boundary(hw):
    """Moving the robot to a wall triggers collision detection."""
    import pybullet
    sim, _, _, _ = hw
    # Teleport robot near the far wall (x_max ~1.75 m)
    pybullet.resetBasePositionAndOrientation(
        sim.robot_id, [1.70, 0.5, 0.15], [0, 0, 0, 1]
    )
    for _ in range(30):
        sim.step()
    assert sim.check_collision(sim.robot_id, sim.arena_id) is True


# ---------------------------------------------------------------------------
# Phase 4.2 — Stricter pickup/deposit tests
# ---------------------------------------------------------------------------

def test_pickup_far_ball_not_attached(hw):
    """pickup_sequence does not attach a ball that is far away."""
    import pybullet
    sim, _, arm, _ = hw
    # Spawn a ball far from the robot (robot is at 0.5, 0.5)
    sim.spawn_ball_at(1.5, 1.5, color='blue')
    # Ensure no ball was spawned at the pickup zone
    arm.move_to_pose(arm.pose_pickup)
    for _ in range(60):
        sim.step()
    arm.gripper_close()
    for _ in range(30):
        sim.step()
    # The far ball should not be attached
    if sim.attached_ball_id is not None:
        attached_pos = pybullet.getBasePositionAndOrientation(
            sim.attached_ball_id)[0]
        dist = ((attached_pos[0] - 0.5) ** 2 +
                (attached_pos[1] - 0.5) ** 2) ** 0.5
        assert dist < 0.3, f"Ball attached from {dist:.2f} m away"


def test_deposit_far_from_basket_not_counted(hw):
    """Opening gripper far from basket does not count as deposit."""
    import pybullet
    sim, _, arm, _ = hw
    # Spawn a ball near the robot and grasp it
    ball_id = sim.spawn_ball_at(0.66, 0.5, color='blue')
    arm.move_to_pose(arm.pose_pickup)
    for _ in range(60):
        sim.step()
    arm.gripper_close()
    for _ in range(30):
        sim.step()
    assert sim.attached_ball_id == ball_id

    # Move robot away from basket (basket is at ~0.9, 0.875)
    pybullet.resetBasePositionAndOrientation(
        sim.robot_id, [0.2, 0.2, 0.15], [0, 0, 0, 1]
    )
    for _ in range(30):
        sim.step()
    deposited_before = sim.get_deposited_count()
    arm.gripper_open()
    for _ in range(30):
        sim.step()
    assert sim.attached_ball_id is None
    assert sim.get_deposited_count() == deposited_before, \
        "Deposit counted despite being far from basket"
