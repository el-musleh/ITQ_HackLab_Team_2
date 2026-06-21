"""Wrist-camera simulation: detect visible bottle caps from robot world pose."""

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

from src.config import WRIST_CAM_FOV_DEG, WRIST_CAM_MAX_RANGE, WRIST_CAM_OFFSET


@dataclass
class CapObservation:
    cap_id: int
    color: str
    distance: float   # m, from robot centre to cap centre
    angle: float      # rad, relative to robot heading (+ = left, − = right)
    world_x: float
    world_y: float


def _normalize(a: float) -> float:
    """Wrap angle to (−π, +π]."""
    while a > math.pi:
        a -= 2.0 * math.pi
    while a <= -math.pi:
        a += 2.0 * math.pi
    return a


def _wrist_world_xy(rx: float, ry: float, theta: float) -> Tuple[float, float]:
    """World-frame (x, y) of the wrist camera given robot centre and heading."""
    ox, oy, _ = WRIST_CAM_OFFSET
    cam_x = rx + ox * math.cos(theta) - oy * math.sin(theta)
    cam_y = ry + ox * math.sin(theta) + oy * math.cos(theta)
    return cam_x, cam_y


def detect_caps(
    robot_x: float,
    robot_y: float,
    robot_theta: float,
    cap_positions: Dict[int, Tuple[float, float, str]],  # id → (x, y, color)
) -> List[CapObservation]:
    """Return caps visible from the wrist camera, sorted nearest-first.

    A cap is visible when it is within the horizontal FOV cone and within the
    maximum detection range.  The angle is measured relative to robot heading
    so the controller can correct its bearing without knowing the camera offset.
    """
    cam_x, cam_y = _wrist_world_xy(robot_x, robot_y, robot_theta)
    half_fov = math.radians(WRIST_CAM_FOV_DEG / 2.0)

    observations: List[CapObservation] = []
    for cap_id, (cx, cy, color) in cap_positions.items():
        # Range check from camera
        cam_dist = math.hypot(cx - cam_x, cy - cam_y)
        if cam_dist < 1e-6 or cam_dist > WRIST_CAM_MAX_RANGE:
            continue

        # Horizontal FOV check
        bearing = math.atan2(cy - cam_y, cx - cam_x)
        angle = _normalize(bearing - robot_theta)
        if abs(angle) > half_fov:
            continue

        # Report distance from robot centre (used by the FSM stop condition)
        robot_dist = math.hypot(cx - robot_x, cy - robot_y)

        observations.append(CapObservation(
            cap_id=cap_id,
            color=color,
            distance=robot_dist,
            angle=angle,
            world_x=cx,
            world_y=cy,
        ))

    observations.sort(key=lambda o: o.distance)
    return observations
