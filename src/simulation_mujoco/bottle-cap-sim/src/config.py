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


# Obstacles placed diagonally near basket, matching PyBullet arena.urdf:
#   Obstacle 1 at (-0.40, +0.40) — 30×20×15 cm crate
#   Obstacle 2 at (+0.40, -0.40) — 40×30×15 cm crate
OBSTACLE_1 = Obstacle(
    name="crate_small",
    width=0.30, length=0.20, height=0.15,
    x=-0.40, y=+0.40,
    rgba=(0.60, 0.40, 0.20, 1.0),   # wooden brown
)
OBSTACLE_2 = Obstacle(
    name="crate_large",
    width=0.40, length=0.30, height=0.15,
    x=+0.40, y=-0.40,
    rgba=(0.60, 0.40, 0.20, 1.0),   # wooden brown
)

# ── Basket (centred in arena) ───────────────────────────────────────────────
BASKET_X: float = 0.0
BASKET_Y: float = 0.0
BASKET_RADIUS: float = 0.15    # m  (30 cm diameter, matching PyBullet)
BASKET_HEIGHT: float = 0.12    # m  (12 cm tall)

# ── Bottle caps ────────────────────────────────────────────────────────────
NUM_CAPS: int = 22
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
ARM_DEPOSIT_LOWER_TICKS: int = 15    # ticks to lower arm for deposit
ARM_DEPOSIT_OPEN_TICKS: int = 10     # ticks to open gripper + release cap
ARM_DEPOSIT_RAISE_TICKS: int = 20    # ticks to raise arm after deposit

# Maximum horizontal distance between gripper XY and cap XY for contact to register.
ATTACH_DIST_XY: float = 0.12         # m

# ── Autonomy controller ─────────────────────────────────────────────────────
ARM_REACH: float = 0.17               # m — stop (robot centre-to-cap) distance
APPROACH_ALIGN_TOL: float = 0.12      # rad — "close enough" heading error
HEADING_KP: float = 2.5              # P-gain for angular correction

LINEAR_SPEED: float = 0.25           # m/s — cruise speed toward cap
MIN_APPROACH_SPEED: float = 0.05     # m/s — min speed when close to cap
FAR_DISTANCE_THRESHOLD: float = 1.0  # m — above this, full cruise speed
CLOSE_DISTANCE_THRESHOLD: float = 0.3  # m — below this, min approach speed
ANGULAR_SPEED: float = 1.20          # rad/s — max angular speed
SEARCH_OMEGA: float = 0.55           # rad/s — slow search rotation

# Basket navigation
BASKET_STOP_DISTANCE: float = 0.30   # m — stop distance from basket centre
BASKET_NAV_SPEED: float = 0.20       # m/s — cruise speed toward basket

# Post-deposit retreat — reverse away from basket before resuming search
RETREAT_TICKS: int = 25              # ticks to reverse (~1s @ 25Hz)
RETREAT_SPEED: float = 0.15          # m/s — reverse speed after deposit

# Stuck detection — mirrors real StuckDetector (2s window, 0.02m displacement)
STUCK_WINDOW_TICKS: int = 50         # ticks to detect stuck (2s @ 25Hz)
STUCK_MIN_DISPLACEMENT: float = 0.02 # m — min movement in window
STUCK_REVERSE_TICKS: int = 20        # ticks to reverse during recovery (~0.8s)
STUCK_TURN_TICKS: int = 25           # ticks to turn during recovery (~1.0s)

# ── Motion safety margins ──────────────────────────────────────────────────
ARENA_SAFETY_MARGIN: float = 0.08    # m extra clearance from arena wall
OBSTACLE_SAFETY_MARGIN: float = 0.08 # m extra clearance from obstacle EDGE
BASKET_SAFETY_MARGIN: float = 0.02   # m — minimal clearance so robot can approach to deposit

# ── Paths ──────────────────────────────────────────────────────────────────
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_SRC_DIR)
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
ARENA_XML_PATH = os.path.join(ASSETS_DIR, "arena.xml")
