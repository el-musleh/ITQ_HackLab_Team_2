"""RobotState, kinematic integration, and motion safety for the JETANK."""

import math
from dataclasses import dataclass
from typing import Tuple

import mujoco
import numpy as np

from src.config import (
    ARENA_X_MAX, ARENA_Y_MAX, ARENA_SAFETY_MARGIN,
    OBSTACLE_1, OBSTACLE_2, OBSTACLE_SAFETY_MARGIN,
    BASKET_X, BASKET_Y, BASKET_RADIUS,
    BASKET_SAFETY_MARGIN,
    ROBOT_WIDTH, ROBOT_LENGTH, ROBOT_HEIGHT,
    ROBOT_START, ROBOT_START_THETA,
    GRIPPER_FORWARD, GRIPPER_HEIGHT_BODY,
)

# Bounding radius of the robot footprint (used in safety checks)
_ROBOT_R: float = math.hypot(ROBOT_WIDTH, ROBOT_LENGTH) / 2.0  # ≈ 0.127 m


# ── State ──────────────────────────────────────────────────────────────────

@dataclass
class RobotState:
    x: float
    y: float
    theta: float   # heading in radians (0 = +world X, π/2 = +world Y)

    def step(self, v: float, omega: float, dt: float) -> None:
        """Kinematic Euler integration (tracked differential drive in 2-D)."""
        self.theta += omega * dt
        self.x += v * math.cos(self.theta) * dt
        self.y += v * math.sin(self.theta) * dt

    def to_qpos7(self) -> np.ndarray:
        """Pack into 7-element freejoint qpos: [x, y, z, qw, qx, qy, qz]."""
        half = self.theta / 2.0
        return np.array(
            [self.x, self.y, ROBOT_HEIGHT / 2.0,
             math.cos(half), 0.0, 0.0, math.sin(half)],
            dtype=np.float64,
        )

    @staticmethod
    def default() -> "RobotState":
        return RobotState(x=ROBOT_START[0], y=ROBOT_START[1],
                          theta=ROBOT_START_THETA)


# ── MuJoCo helpers ─────────────────────────────────────────────────────────

def get_robot_addrs(model: mujoco.MjModel) -> Tuple[int, int]:
    """Return (qpos_addr, qvel_addr) for the robot freejoint."""
    body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "robot")
    jnt_id = int(model.body_jntadr[body_id])
    return int(model.jnt_qposadr[jnt_id]), int(model.jnt_dofadr[jnt_id])


def gripper_world_xyz(
    state: "RobotState",
    arm_z: float = 0.0,
) -> Tuple[float, float, float]:
    """World-frame (x, y, z) of the gripper palm.

    arm_z: current arm_lift joint value (0 = neutral, negative = lowered).
    """
    wx = state.x + GRIPPER_FORWARD * math.cos(state.theta)
    wy = state.y + GRIPPER_FORWARD * math.sin(state.theta)
    wz = ROBOT_HEIGHT / 2.0 + GRIPPER_HEIGHT_BODY + arm_z
    return wx, wy, wz


def write_robot(
    data: mujoco.MjData,
    qpos_addr: int,
    qvel_addr: int,
    state: RobotState,
) -> None:
    """Write kinematic robot pose into MuJoCo data and zero all DOF velocities."""
    data.qpos[qpos_addr: qpos_addr + 7] = state.to_qpos7()
    data.qvel[qvel_addr: qvel_addr + 6] = 0.0


# ── Safety ─────────────────────────────────────────────────────────────────

def clamp_velocity(
    state: RobotState,
    v: float,
    omega: float,
    lookahead_dt: float = 0.06,
) -> Tuple[float, float]:
    """Zero linear speed only when motion would worsen a safety-margin violation.

    A hazard blocks forward motion only if the next position is *deeper* inside
    the hazard zone than the current position.  This lets the robot escape a zone
    it already started inside (e.g., near the arena corner at spawn).
    Angular speed is never clamped so the robot can always rotate away.
    """
    if v == 0.0:
        return v, omega

    nx = state.x + v * math.cos(state.theta) * lookahead_dt
    ny = state.y + v * math.sin(state.theta) * lookahead_dt

    # ── Arena boundary ─────────────────────────────────────────────────────
    # Use actual half-width/length so the robot can hug walls without stalling.
    wall_x = ARENA_X_MAX - ROBOT_WIDTH  / 2.0 - ARENA_SAFETY_MARGIN
    wall_y = ARENA_Y_MAX - ROBOT_LENGTH / 2.0 - ARENA_SAFETY_MARGIN
    if abs(nx) > wall_x and abs(nx) > abs(state.x):
        return 0.0, omega
    if abs(ny) > wall_y and abs(ny) > abs(state.y):
        return 0.0, omega

    # ── Crate obstacles ────────────────────────────────────────────────────
    # Rectangle–rectangle collision with axis-aligned footprints.
    # Only block when the next step enters (or deepens into) the zone.
    for obs in (OBSTACLE_1, OBSTACLE_2):
        hw = obs.width  / 2.0 + ROBOT_WIDTH  / 2.0 + OBSTACLE_SAFETY_MARGIN
        hl = obs.length / 2.0 + ROBOT_LENGTH / 2.0 + OBSTACLE_SAFETY_MARGIN
        in_next = abs(nx - obs.x) < hw and abs(ny - obs.y) < hl
        if not in_next:
            continue
        in_curr = abs(state.x - obs.x) < hw and abs(state.y - obs.y) < hl
        d_next = math.hypot(nx - obs.x, ny - obs.y)
        d_curr = math.hypot(state.x - obs.x, state.y - obs.y)
        if not in_curr or d_next < d_curr:
            return 0.0, omega

    # ── Basket (circular) ──────────────────────────────────────────────────
    basket_r = BASKET_RADIUS + ROBOT_WIDTH / 2.0 + BASKET_SAFETY_MARGIN
    dist_next = math.hypot(nx - BASKET_X, ny - BASKET_Y)
    if dist_next < basket_r:
        dist_curr = math.hypot(state.x - BASKET_X, state.y - BASKET_Y)
        if dist_next < dist_curr:
            return 0.0, omega

    return v, omega
