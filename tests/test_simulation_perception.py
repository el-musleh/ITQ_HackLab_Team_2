"""Headless perception checks against known PyBullet scene poses."""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pybullet = pytest.importorskip("pybullet")
pytest.importorskip("cv2")

from src.perception.ball_detector import BallDetector  # noqa: E402
from src.perception.basket_detector import BasketDetector  # noqa: E402
from src.perception.obstacle_detector import ObstacleDetector  # noqa: E402
from src.simulation import SimulationCore, create_sim_hardware  # noqa: E402
from src.utils import load_config  # noqa: E402

pytestmark = pytest.mark.simulation


@pytest.fixture
def sim_camera():
    cfg = load_config()
    cfg.setdefault('simulation', {})
    cfg['simulation'] = {**cfg['simulation'], 'renderer': 'tiny'}
    sim = SimulationCore(gui=False, real_time=False, config=cfg)
    sim.initialize()
    sim.load_arena()
    rid = sim.load_robot(start_pos=[0.5, 0.55, 0.15],
                         start_orientation=[0, 0, 0])
    _, _, camera = create_sim_hardware(rid, cfg, sim=sim)
    yield sim, camera, cfg
    sim.close()


def _step(sim, count=90):
    for _ in range(count):
        sim.step()


def test_ball_detector_sees_known_blue_ball(sim_camera):
    sim, camera, cfg = sim_camera
    sim.spawn_ball_at(0.62, 0.55, color='blue', radius=0.03)
    camera.set_tilt(-45)
    _step(sim)

    detections = BallDetector(cfg).detect(camera.read())

    assert any(det[0] == 'blue' for det in detections)


def test_basket_detector_sees_center_basket(sim_camera):
    sim, camera, cfg = sim_camera
    pybullet.resetBasePositionAndOrientation(
        sim.robot_id,
        [0.45, 0.875, 0.15],
        pybullet.getQuaternionFromEuler([0, 0, 0]),
    )
    camera.look_forward()
    _step(sim)

    basket = BasketDetector(cfg).detect(camera.read())

    assert basket['basket_found'] is True
    assert basket['centroid'] is not None
    assert basket['distance'] is not None


def test_boundary_detector_sees_yellow_wall(sim_camera):
    sim, camera, cfg = sim_camera
    pybullet.resetBasePositionAndOrientation(
        sim.robot_id,
        [0.12, 0.875, 0.15],
        pybullet.getQuaternionFromEuler([0, 0, math.pi]),
    )
    camera.look_forward()
    _step(sim)

    result = ObstacleDetector(cfg).detect_combined(camera.read())

    assert result['boundary_detected'] is True
    assert result['priority'] == 'boundary'


def test_obstacle_detector_sees_crate_edges(sim_camera):
    sim, camera, cfg = sim_camera
    pybullet.resetBasePositionAndOrientation(
        sim.robot_id,
        [0.5, 0.9, 0.15],
        pybullet.getQuaternionFromEuler([0, 0, math.pi / 2]),
    )
    camera.look_forward()
    _step(sim)

    result = ObstacleDetector(cfg).detect_combined(camera.read())

    assert result['obstacle_detected'] is True
