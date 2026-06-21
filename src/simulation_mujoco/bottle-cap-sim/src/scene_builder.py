"""Build the MuJoCo MJCF XML scene and write it to assets/arena.xml."""

import math
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

from src.config import (
    ARENA_X_MIN, ARENA_X_MAX, ARENA_Y_MIN, ARENA_Y_MAX,
    ROBOT_WIDTH, ROBOT_LENGTH, ROBOT_HEIGHT, ROBOT_START,
    OBSTACLE_1, OBSTACLE_2,
    BASKET_X, BASKET_Y, BASKET_INNER_SIZE, BASKET_WALL_THICKNESS, BASKET_WALL_HEIGHT,
    NUM_CAPS, CAP_DIAMETER_MIN, CAP_DIAMETER_MAX, CAP_THICKNESS,
    CAP_COLORS, CAP_RGBA,
    ASSETS_DIR, ARENA_XML_PATH,
)


# ── Cap placement ──────────────────────────────────────────────────────────

@dataclass
class CapPlacement:
    id: int
    x: float
    y: float
    radius: float
    color: str


def _circle_overlaps_rect(
    cx: float, cy: float, cr: float,
    rx: float, ry: float, half_w: float, half_h: float,
) -> bool:
    dx = max(0.0, abs(cx - rx) - half_w)
    dy = max(0.0, abs(cy - ry) - half_h)
    return dx * dx + dy * dy <= cr * cr


def _place_caps(n: int, seed: int = 42) -> List[CapPlacement]:
    rng = random.Random(seed)
    placed: List[CapPlacement] = []

    wall_margin = 0.06
    x_lo = ARENA_X_MIN + wall_margin
    x_hi = ARENA_X_MAX - wall_margin
    y_lo = ARENA_Y_MIN + wall_margin
    y_hi = ARENA_Y_MAX - wall_margin

    pad = 0.05
    basket_half = (BASKET_INNER_SIZE / 2) + BASKET_WALL_THICKNESS + pad
    exclusions: List[Tuple[float, float, float, float]] = [
        (OBSTACLE_1.x, OBSTACLE_1.y,
         OBSTACLE_1.width / 2 + pad, OBSTACLE_1.length / 2 + pad),
        (OBSTACLE_2.x, OBSTACLE_2.y,
         OBSTACLE_2.width / 2 + pad, OBSTACLE_2.length / 2 + pad),
        (BASKET_X, BASKET_Y, basket_half, basket_half),
        (ROBOT_START[0], ROBOT_START[1],
         ROBOT_WIDTH / 2 + pad, ROBOT_LENGTH / 2 + pad),
    ]

    for cap_id in range(n):
        color = rng.choice(CAP_COLORS)
        radius = rng.uniform(CAP_DIAMETER_MIN / 2, CAP_DIAMETER_MAX / 2)
        placed_this = False
        for _ in range(10000):
            x = rng.uniform(x_lo + radius, x_hi - radius)
            y = rng.uniform(y_lo + radius, y_hi - radius)
            if any(
                _circle_overlaps_rect(x, y, radius, ex, ey, ew, eh)
                for ex, ey, ew, eh in exclusions
            ):
                continue
            if any(
                math.hypot(x - c.x, y - c.y) < radius + c.radius + 0.012
                for c in placed
            ):
                continue
            placed.append(CapPlacement(id=cap_id, x=x, y=y, radius=radius, color=color))
            placed_this = True
            break
        if not placed_this:
            print(f"[WARNING] Could not place cap {cap_id}")

    return placed


# ── XML helpers ────────────────────────────────────────────────────────────

def _fmt(*values: float) -> str:
    return " ".join(f"{v:.4f}" for v in values)


def _rgba(r: float, g: float, b: float, a: float = 1.0) -> str:
    return f"{r} {g} {b} {a}"


# ── Robot arm geometry (visual only, fixed in body frame) ──────────────────
#
# Body frame: +x = forward, +y = left, +z = up.
# Body half-extents: rw=0.095(y), rl=0.085(x), rh=0.125(z).
# All arm geom positions are relative to robot body centre.
#
def _arm_geoms(L, depth: int, rw: float, rl: float, rh: float) -> None:
    """Emit MJCF geom lines for the 4-DOF arm (visual placeholder)."""

    d = depth

    # ── Camera module (front-top, dark housing + blue lens) ────────────────
    L(f'<geom name="cam_housing" type="box" '
      f'size="{_fmt(0.020, 0.028, 0.016)}" '
      f'pos="{_fmt(rl + 0.002, 0, rh * 0.70)}" '
      f'rgba="0.12 0.12 0.12 1"/>', d)
    L(f'<geom name="cam_lens" type="cylinder" '
      f'size="{_fmt(0.009, 0.006)}" '
      f'pos="{_fmt(rl + 0.024, 0, rh * 0.70)}" '
      f'euler="{_fmt(0, 1.5708, 0)}" '
      f'rgba="0.05 0.20 0.55 1"/>', d)

    # ── Arm base servo (cylinder, Z-axis, on top of body near front) ───────
    ab_x, ab_z = 0.020, rh + 0.020   # base centre: top of body + 20 mm
    L(f'<geom name="arm_base" type="cylinder" '
      f'size="{_fmt(0.020, 0.020)}" '
      f'pos="{_fmt(ab_x, 0, ab_z)}" '
      f'mass="0.08" '
      f'rgba="0.25 0.25 0.25 1"/>', d)

    # ── Shoulder riser (vertical box, up from base) ─────────────────────────
    sh_x, sh_z = ab_x, ab_z + 0.020 + 0.030   # top of base cylinder + box half-h
    L(f'<geom name="arm_shoulder" type="box" '
      f'size="{_fmt(0.013, 0.013, 0.030)}" '
      f'pos="{_fmt(sh_x, 0, sh_z)}" '
      f'rgba="0.22 0.22 0.22 1"/>', d)

    # ── Upper arm (horizontal box going forward from shoulder top) ──────────
    ua_x = sh_x + 0.060   # centre of upper-arm segment
    ua_z = sh_z + 0.030   # just above shoulder top, roughly flat
    L(f'<geom name="arm_upper" type="box" '
      f'size="{_fmt(0.060, 0.011, 0.011)}" '
      f'pos="{_fmt(ua_x, 0, ua_z)}" '
      f'rgba="0.30 0.30 0.30 1"/>', d)

    # ── Elbow joint marker (small cylinder, Y-axis) ─────────────────────────
    el_x = ua_x + 0.060   # end of upper arm
    el_z = ua_z
    L(f'<geom name="arm_elbow" type="cylinder" '
      f'size="{_fmt(0.013, 0.013)}" '
      f'pos="{_fmt(el_x, 0, el_z)}" '
      f'euler="{_fmt(1.5708, 0, 0)}" '
      f'rgba="0.25 0.25 0.25 1"/>', d)

    # ── Forearm (horizontal, slightly lower than upper arm) ─────────────────
    fa_x = el_x + 0.042
    fa_z = el_z - 0.012
    L(f'<geom name="arm_forearm" type="box" '
      f'size="{_fmt(0.042, 0.010, 0.010)}" '
      f'pos="{_fmt(fa_x, 0, fa_z)}" '
      f'rgba="0.30 0.30 0.30 1"/>', d)

    # ── Wrist servo (small box) ─────────────────────────────────────────────
    wr_x = fa_x + 0.042 + 0.013
    wr_z = fa_z - 0.006
    L(f'<geom name="arm_wrist" type="box" '
      f'size="{_fmt(0.013, 0.013, 0.013)}" '
      f'pos="{_fmt(wr_x, 0, wr_z)}" '
      f'rgba="0.22 0.22 0.22 1"/>', d)

    # ── Gripper palm ────────────────────────────────────────────────────────
    gp_x = wr_x + 0.013 + 0.012
    gp_z = wr_z
    L(f'<geom name="gripper_palm" type="box" '
      f'size="{_fmt(0.012, 0.022, 0.008)}" '
      f'pos="{_fmt(gp_x, 0, gp_z)}" '
      f'rgba="0.18 0.18 0.18 1"/>', d)

    # ── Gripper fingers (two, slightly open) ───────────────────────────────
    fi_x = gp_x + 0.012 + 0.014
    fi_z = gp_z - 0.004
    for side, fy in [("l", 0.016), ("r", -0.016)]:
        L(f'<geom name="gripper_{side}" type="box" '
          f'size="{_fmt(0.014, 0.007, 0.006)}" '
          f'pos="{_fmt(fi_x, fy, fi_z)}" '
          f'rgba="0.20 0.20 0.20 1"/>', d)


# ── Main XML builder ───────────────────────────────────────────────────────

def _build_xml(caps: List[CapPlacement]) -> str:
    lines: List[str] = []
    I = "  "

    def L(text: str, depth: int = 0) -> None:
        lines.append(I * depth + text)

    L('<mujoco model="bottle_cap_arena">')
    L('<compiler angle="radian" autolimits="true"/>', 1)
    L('<option timestep="0.004" gravity="0 0 -9.81"/>', 1)
    L('')
    L('<statistic center="0 0 0.25" extent="1.9"/>', 1)
    L('')
    L('<visual>', 1)
    L('<headlight diffuse="0.8 0.8 0.8" ambient="0.40 0.40 0.40" specular="0 0 0"/>', 2)
    L('<rgba haze="0.10 0.12 0.12 1"/>', 2)
    L('<global azimuth="145" elevation="-38"/>', 2)
    L('</visual>', 1)
    L('')
    L('<asset>', 1)
    L('<texture name="floor_tex" type="2d" builtin="checker" '
      'rgb1="0.92 0.92 0.92" rgb2="0.84 0.84 0.84" width="512" height="512"/>', 2)
    L('<material name="floor_mat" texture="floor_tex" texrepeat="8 8" reflectance="0.04"/>', 2)
    L('</asset>', 1)
    L('')
    L('<worldbody>', 1)
    L('')

    # ── Floor ──────────────────────────────────────────────────────────────
    L('<!-- Floor -->', 2)
    L('<geom name="floor" type="plane" size="3 3 0.1" material="floor_mat"/>', 2)
    L('')

    # ── Yellow boundary tape (flat strips on floor surface) ────────────────
    L('<!-- Yellow floor tape (arena boundary) -->', 2)
    tw = 0.020   # tape half-width  (40 mm wide strip)
    th = 0.0015  # tape half-height (3 mm thin — lies flat on floor)
    ax = ARENA_X_MAX   # 0.875
    ay = ARENA_Y_MAX   # 0.900
    yellow = 'rgba="1.0 0.92 0.0 1"'

    # N/S strips span the full arena width plus one tape-width at each corner
    L(f'<geom name="tape_n" type="box" '
      f'size="{_fmt(ax + tw, tw, th)}" pos="{_fmt(0.0,  ay, th)}" {yellow}/>', 2)
    L(f'<geom name="tape_s" type="box" '
      f'size="{_fmt(ax + tw, tw, th)}" pos="{_fmt(0.0, -ay, th)}" {yellow}/>', 2)
    # E/W strips span the full arena height plus one tape-width at each corner
    L(f'<geom name="tape_e" type="box" '
      f'size="{_fmt(tw, ay + tw, th)}" pos="{_fmt( ax, 0.0, th)}" {yellow}/>', 2)
    L(f'<geom name="tape_w" type="box" '
      f'size="{_fmt(tw, ay + tw, th)}" pos="{_fmt(-ax, 0.0, th)}" {yellow}/>', 2)
    L('')

    # ── Crate obstacles (blue = small, green = large) ─────────────────────
    L('<!-- Crate obstacles -->', 2)
    for obs in [OBSTACLE_1, OBSTACLE_2]:
        hw, hl, hh = obs.width / 2, obs.length / 2, obs.height / 2
        r, g, b, a = obs.rgba
        L(f'<geom name="{obs.name}" type="box" '
          f'size="{_fmt(hw, hl, hh)}" '
          f'pos="{_fmt(obs.x, obs.y, hh)}" '
          f'rgba="{_rgba(r, g, b, a)}"/>', 2)
    L('')

    # ── Gray collection basket (centred in arena) ──────────────────────────
    L('<!-- Gray collection basket (centre of arena) -->', 2)
    bx, by = BASKET_X, BASKET_Y
    bi  = BASKET_INNER_SIZE / 2          # inner half-size  0.10
    hwt = BASKET_WALL_THICKNESS / 2      # wall half-thickness 0.01
    hwh = BASKET_WALL_HEIGHT / 2         # wall half-height 0.04
    fl_h = hwt                           # floor panel half-height = 0.01
    wall_z = fl_h * 2 + hwh             # wall centre z = 0.06

    gray = 'rgba="0.48 0.48 0.48 1"'

    L(f'<geom name="basket_floor" type="box" '
      f'size="{_fmt(bi + hwt, bi + hwt, fl_h)}" '
      f'pos="{_fmt(bx, by, fl_h)}" {gray}/>', 2)
    L(f'<geom name="basket_wall_n" type="box" '
      f'size="{_fmt(bi + hwt, hwt, hwh)}" '
      f'pos="{_fmt(bx, by + bi + hwt, wall_z)}" {gray}/>', 2)
    L(f'<geom name="basket_wall_s" type="box" '
      f'size="{_fmt(bi + hwt, hwt, hwh)}" '
      f'pos="{_fmt(bx, by - bi - hwt, wall_z)}" {gray}/>', 2)
    L(f'<geom name="basket_wall_e" type="box" '
      f'size="{_fmt(hwt, bi, hwh)}" '
      f'pos="{_fmt(bx + bi + hwt, by, wall_z)}" {gray}/>', 2)
    L(f'<geom name="basket_wall_w" type="box" '
      f'size="{_fmt(hwt, bi, hwh)}" '
      f'pos="{_fmt(bx - bi - hwt, by, wall_z)}" {gray}/>', 2)
    L('')

    # ── JETANK robot (visual digital twin) ────────────────────────────────
    L('<!-- JETANK robot digital twin (visual placeholder) -->', 2)
    rx, ry = ROBOT_START
    rw = ROBOT_WIDTH / 2    # 0.095
    rl = ROBOT_LENGTH / 2   # 0.085
    rh = ROBOT_HEIGHT / 2   # 0.125

    L(f'<body name="robot" pos="{_fmt(rx, ry, rh)}">', 2)
    L('<freejoint name="robot_free"/>', 3)

    # Main chassis (dark body)
    L(f'<geom name="chassis" type="box" size="{_fmt(rw - 0.016, rl, rh)}" '
      f'rgba="0.16 0.16 0.16 1" mass="1.8"/>', 3)

    # Left track assembly (slightly wider and taller than chassis)
    L(f'<geom name="track_l" type="box" '
      f'size="{_fmt(rl + 0.004, 0.015, rh + 0.006)}" '
      f'pos="{_fmt(0, +(rw - 0.007), 0)}" '
      f'rgba="0.07 0.07 0.07 1" mass="0.25"/>', 3)
    # Track tread detail strips (left)
    for seg_x in [-0.055, -0.020, 0.015, 0.050]:
        L(f'<geom name="tread_l_{abs(int(seg_x*1000))}" type="box" '
          f'size="{_fmt(0.010, 0.016, 0.004)}" '
          f'pos="{_fmt(seg_x, +(rw + 0.008), -(rh + 0.004))}" '
          f'rgba="0.13 0.13 0.13 1"/>', 3)

    # Right track assembly
    L(f'<geom name="track_r" type="box" '
      f'size="{_fmt(rl + 0.004, 0.015, rh + 0.006)}" '
      f'pos="{_fmt(0, -(rw - 0.007), 0)}" '
      f'rgba="0.07 0.07 0.07 1" mass="0.25"/>', 3)
    # Track tread detail strips (right)
    for seg_x in [-0.055, -0.020, 0.015, 0.050]:
        L(f'<geom name="tread_r_{abs(int(seg_x*1000))}" type="box" '
          f'size="{_fmt(0.010, 0.016, 0.004)}" '
          f'pos="{_fmt(seg_x, -(rw + 0.008), -(rh + 0.004))}" '
          f'rgba="0.13 0.13 0.13 1"/>', 3)

    # Wheel hubs (front and rear, both sides)
    for fx, flabel in [(rl, "f"), (-rl, "r")]:
        for hy, slabel in [(+(rw - 0.004), "l"), (-(rw - 0.004), "r")]:
            L(f'<geom name="hub_{flabel}{slabel}" type="cylinder" '
              f'size="{_fmt(rh * 0.70, 0.017)}" '
              f'pos="{_fmt(fx, hy, 0)}" '
              f'euler="{_fmt(1.5708, 0, 0)}" '
              f'rgba="0.20 0.20 0.20 1"/>', 3)

    # Top deck panel (slightly lighter than body)
    L(f'<geom name="top_deck" type="box" '
      f'size="{_fmt(rw - 0.020, rl - 0.010, 0.006)}" '
      f'pos="{_fmt(0, 0, rh + 0.006)}" '
      f'rgba="0.22 0.22 0.22 1"/>', 3)

    # Arm assembly — child body with Z-slider so the arm can lower for pickup.
    # pos="0 0 0" keeps the origin coincident with the robot body centre.
    # arm_lift range: 0 (neutral) to -0.20 m (fully lowered).
    L('<body name="arm_assembly" pos="0 0 0">', 3)
    L('<joint name="arm_lift" type="slide" axis="0 0 1" range="-0.20 0"/>', 4)
    _arm_geoms(L, 4, rw, rl, rh)
    L(f'<camera name="wrist_cam" '
      f'pos="{_fmt(0.237, 0.0, 0.207)}" '
      f'xyaxes="0 -1 0 0 0 1" fovy="80"/>', 4)
    L('</body>', 3)

    L('</body>', 2)
    L('')

    # ── Bottle caps ────────────────────────────────────────────────────────
    L('<!-- Bottle caps -->', 2)
    ch = CAP_THICKNESS / 2
    for cap in caps:
        r, g, b, a = CAP_RGBA[cap.color]
        L(f'<body name="cap_{cap.id}" pos="{_fmt(cap.x, cap.y, ch)}">', 2)
        L('<freejoint/>', 3)
        L(f'<geom type="cylinder" size="{_fmt(cap.radius, ch)}" '
          f'rgba="{r} {g} {b} {a}" mass="0.005"/>', 3)
        L('</body>', 2)

    L('')
    L('</worldbody>', 1)
    L('</mujoco>')

    return '\n'.join(lines)


# ── Public API ─────────────────────────────────────────────────────────────

def build_scene(seed: int = 42) -> Tuple[str, Dict[int, str]]:
    """Generate arena XML, save it, return (xml_string, {cap_id: color})."""
    os.makedirs(ASSETS_DIR, exist_ok=True)
    caps = _place_caps(NUM_CAPS, seed=seed)
    xml = _build_xml(caps)
    with open(ARENA_XML_PATH, "w", encoding="utf-8") as fh:
        fh.write(xml)
    cap_colors: Dict[int, str] = {c.id: c.color for c in caps}
    print(f"[scene] {len(caps)}/{NUM_CAPS} caps placed  →  {ARENA_XML_PATH}")
    return xml, cap_colors
