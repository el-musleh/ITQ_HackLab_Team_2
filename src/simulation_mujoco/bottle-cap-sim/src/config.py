"""Simulation constants — all distances in metres."""

import math
import os
from dataclasses import dataclass
from typing import Tuple

# ── Arena ──────────────────────────────────────────────────────────────────
ARENA_WIDTH: float = 1.75   # m  (x-axis)
ARENA_HEIGHT: float = 1.80  # m  (y-axis)

ARENA_X_MIN: float = -ARENA_WIDTH / 2   # -0.875
ARENA_X_MAX: float =  ARENA_WIDTH / 2   # +0.875
ARENA_Y_MIN: float = -ARENA_HEIGHT / 2  # -0.900
ARENA_Y_MAX: float =  ARENA_HEIGHT / 2  # +0.900

# ── Timing ─────────────────────────────────────────────────────────────────
TIME_LIMIT: float = 300.0  # seconds

# ── Robot (JETANK placeholder) ─────────────────────────────────────────────
ROBOT_WIDTH: float = 0.19   # m  (including tracks)
ROBOT_LENGTH: float = 0.17  # m
ROBOT_HEIGHT: float = 0.25  # m
ROBOT_START: Tuple[float, float] = (-0.65, -0.65)  # centre (x, y)
ROBOT_START_THETA: float = math.pi / 4              # rad — face arena centre

# ── Obstacles ──────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Obstacle:
    name: str
    width: float    # m  (x-dimension)
    length: float   # m  (y-dimension)
    height: float   # m  (z-dimension)
    x: float        # centre x
    y: float        # centre y
    rgba: Tuple[float, float, float, float]


# Basket is at (0, 0); obstacles placed symmetrically left/right with equal
# gap (0.10 m) from the basket outer edge to the near obstacle edge.
_BASKET_OUTER_HALF: float = 0.12   # BASKET_INNER_SIZE/2 + BASKET_WALL_THICKNESS
_GAP: float = 0.10

OBSTACLE_1 = Obstacle(
    name="crate_small",
    width=0.20, length=0.30, height=0.25,
    # left of basket: centre_x = -(basket_edge + gap + half_width)
    x=-(_BASKET_OUTER_HALF + _GAP + 0.10), y=0.0,
    rgba=(0.15, 0.35, 0.85, 1.0),   # blue
)
OBSTACLE_2 = Obstacle(
    name="crate_large",
    width=0.30, length=0.40, height=0.30,
    # right of basket: centre_x = +(basket_edge + gap + half_width)
    x=+(_BASKET_OUTER_HALF + _GAP + 0.15), y=0.0,
    rgba=(0.15, 0.70, 0.25, 1.0),   # green
)

# ── Basket (centred in arena) ───────────────────────────────────────────────
BASKET_X: float = 0.0
BASKET_Y: float = 0.0
BASKET_INNER_SIZE: float = 0.20   # square inner side length (m)
BASKET_WALL_THICKNESS: float = 0.02  # m  (full thickness)
BASKET_WALL_HEIGHT: float = 0.08     # m  (full wall height)

# ── Bottle caps ────────────────────────────────────────────────────────────
NUM_CAPS: int = 5
CAP_DIAMETER_MIN: float = 0.030  # m
CAP_DIAMETER_MAX: float = 0.040  # m
CAP_THICKNESS: float = 0.008     # m  (height of cylinder)

CAP_COLORS: list[str] = ["blue", "red", "silver"]
CAP_RGBA: dict[str, Tuple[float, float, float, float]] = {
    "blue":   (0.10, 0.30, 0.90, 1.0),
    "red":    (0.90, 0.10, 0.10, 1.0),
    "silver": (0.78, 0.78, 0.78, 1.0),
}

# ── Wrist camera (position in robot body frame, derived from arm geometry) ──
# Body frame: +x = forward, +y = left, +z = up.  Origin = body centre.
WRIST_CAM_OFFSET: Tuple[float, float, float] = (0.237, 0.0, 0.207)
WRIST_CAM_FOV_DEG: float = 160.0      # total horizontal FOV (CSI IMX219)
WRIST_CAM_MAX_RANGE: float = 2.5      # m — no meaningful limit inside arena

# ── Gripper geometry (robot body frame, origin = body centre) ──────────────
GRIPPER_FORWARD: float = 0.262       # m forward from body centre (palm)
GRIPPER_HEIGHT_BODY: float = 0.207   # m above body centre

# ── Arm lift joint ──────────────────────────────────────────────────────────
# The arm_assembly child body slides on a Z joint so the arm visually lowers.
ARM_LIFT_RANGE: float = -0.20        # m — how far the arm descends (negative = down)
ARM_LOWER_TICKS: int  = 20           # control ticks to reach bottom  (~0.8 s @ 25 Hz)
ARM_RAISE_TICKS: int  = 20           # control ticks to return to top
ARM_CLOSE_TICKS: int  = 15           # ticks for gripper close + cap attach interpolation

# Maximum horizontal distance between gripper XY and cap XY for contact to register.
ATTACH_DIST_XY: float = 0.12         # m

# ── Autonomy controller ─────────────────────────────────────────────────────
ARM_REACH: float = 0.17               # m — stop (robot centre-to-cap) distance
APPROACH_ALIGN_TOL: float = 0.12      # rad — "close enough" heading error
HEADING_KP: float = 2.5              # P-gain for angular correction

LINEAR_SPEED: float = 0.25           # m/s — cruise speed toward cap
ANGULAR_SPEED: float = 1.20          # rad/s — max angular speed
SEARCH_OMEGA: float = 0.55           # rad/s — slow search rotation

# ── Motion safety margins ──────────────────────────────────────────────────
ARENA_SAFETY_MARGIN: float = 0.08    # m extra clearance from arena wall
OBSTACLE_SAFETY_MARGIN: float = 0.08 # m extra clearance from obstacle EDGE
BASKET_SAFETY_MARGIN: float = 0.10   # m extra clearance from basket outer edge

# ── Paths ──────────────────────────────────────────────────────────────────
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_SRC_DIR)
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
ARENA_XML_PATH = os.path.join(ASSETS_DIR, "arena.xml")
