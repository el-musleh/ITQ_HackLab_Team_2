"""Passive MuJoCo viewer loop: vision, autonomy, robot control, and arm pickup."""

import math
import time
from typing import Dict, Optional, Tuple

import mujoco
import mujoco.viewer

from src.autonomy import AutonomyController, FSM
from src.config import (
    ARM_LIFT_RANGE, ARM_LOWER_TICKS, ARM_RAISE_TICKS, ARM_CLOSE_TICKS,
    ATTACH_DIST_XY, CAP_THICKNESS, ROBOT_HEIGHT, GRIPPER_HEIGHT_BODY,
)
from src.robot_control import (
    RobotState, clamp_velocity, get_robot_addrs, gripper_world_xyz, write_robot,
)
from src.vision import detect_caps

_CONTROL_HZ: int = 25
_CAP_FLOOR_Z: float = CAP_THICKNESS / 2.0   # z of cap centre lying on floor


# ── Cap MuJoCo helpers ─────────────────────────────────────────────────────

def _get_cap_addrs(
    model: mujoco.MjModel,
    cap_body_ids: Dict[int, int],
) -> Tuple[Dict[int, int], Dict[int, int]]:
    qpos, qvel = {}, {}
    for cid, bid in cap_body_ids.items():
        jnt = int(model.body_jntadr[bid])
        if jnt >= 0:
            qpos[cid] = int(model.jnt_qposadr[jnt])
            qvel[cid] = int(model.jnt_dofadr[jnt])
    return qpos, qvel


def _write_cap_xyz(
    data: mujoco.MjData,
    qpos_addr: int,
    qvel_addr: int,
    x: float,
    y: float,
    z: float,
) -> None:
    data.qpos[qpos_addr: qpos_addr + 7] = [x, y, z, 1.0, 0.0, 0.0, 0.0]
    data.qvel[qvel_addr: qvel_addr + 6] = 0.0


# ── Main simulation loop ───────────────────────────────────────────────────

def run_sim(xml_string: str, cap_colors: Dict[int, str]) -> None:
    model = mujoco.MjModel.from_xml_string(xml_string)
    data  = mujoco.MjData(model)

    # Robot joint addresses
    qpos_addr, qvel_addr = get_robot_addrs(model)

    # Arm-lift joint addresses
    arm_jnt_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "arm_lift")
    if arm_jnt_id == -1:
        raise RuntimeError("Joint 'arm_lift' not found in XML — check scene_builder.py")
    arm_lift_qpos_addr = int(model.jnt_qposadr[arm_jnt_id])
    arm_lift_qvel_addr = int(model.jnt_dofadr[arm_jnt_id])

    # Cap body + joint addresses
    cap_body_ids: Dict[int, int] = {}
    for cid in cap_colors:
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f"cap_{cid}")
        if bid == -1:
            print(f"[viewer] WARNING: body 'cap_{cid}' not found")
        else:
            cap_body_ids[cid] = bid
    cap_qpos, cap_qvel = _get_cap_addrs(model, cap_body_ids)

    robot = RobotState.default()
    write_robot(data, qpos_addr, qvel_addr, robot)
    mujoco.mj_forward(model, data)

    autonomy = AutonomyController()

    dt         = float(model.opt.timestep)
    ctrl_every = max(1, int(1.0 / (_CONTROL_HZ * dt)))
    step       = 0
    v, omega   = 0.0, 0.0

    # ── Inline pickup state machine ───────────────────────────────────────
    # Phases: "idle" → "lowering" → "closing" → "raising" → "holding"
    _pickup_phase: str      = "idle"
    _pickup_tick:  int      = 0
    _arm_z:        float    = 0.0       # current arm_lift joint value (0 = up)
    _active_cap:   Optional[int] = None
    _contact_cap_x: float   = 0.0      # cap world x at moment of contact
    _contact_cap_y: float   = 0.0
    _attach_x_off:  float   = 0.0      # cap_xy − gripper_xy (saved for RAISE)
    _attach_y_off:  float   = 0.0
    _cap_z:         float   = _CAP_FLOOR_Z  # current cap z during closing

    def _write_arm(az: float) -> None:
        data.qpos[arm_lift_qpos_addr] = az
        data.qvel[arm_lift_qvel_addr] = 0.0

    # gripper z at a given arm_lift value
    def _gripper_z(az: float) -> float:
        return ROBOT_HEIGHT / 2.0 + GRIPPER_HEIGHT_BODY + az

    print(
        f"[sim] timestep={dt * 1000:.1f} ms  "
        f"control={_CONTROL_HZ} Hz (every {ctrl_every} steps)\n"
        f"[sim] robot starts at ({robot.x:.2f}, {robot.y:.2f})  "
        f"θ={robot.theta:.2f} rad\n"
        f"[sim] {len(cap_body_ids)} caps tracked\n"
        f"[viewer] Opening MuJoCo viewer — close the window to exit."
    )

    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            t0 = time.perf_counter()

            # ── Autonomy tick ────────────────────────────────────────────
            if step % ctrl_every == 0:
                cap_positions: Dict[int, Tuple[float, float, str]] = {}
                for cid, bid in cap_body_ids.items():
                    if cid not in autonomy.collected_caps:
                        cap_positions[cid] = (
                            float(data.xpos[bid][0]),
                            float(data.xpos[bid][1]),
                            cap_colors[cid],
                        )
                visible = detect_caps(robot.x, robot.y, robot.theta, cap_positions)
                v, omega = autonomy.step(robot.x, robot.y, robot.theta, visible)

                # Trigger arm lowering as soon as autonomy enters PICKUP
                if (autonomy.state is FSM.PICKUP
                        and _pickup_phase == "idle"
                        and autonomy.target_id is not None):
                    _active_cap   = autonomy.target_id
                    _pickup_phase = "lowering"
                    _pickup_tick  = 0
                    _arm_z        = 0.0
                    print(f"[arm] LOWERING  cap_id={_active_cap}")

            # ── Robot motion ─────────────────────────────────────────────
            v_safe, omega_safe = clamp_velocity(robot, v, omega)
            robot.step(v_safe, omega_safe, dt)
            write_robot(data, qpos_addr, qvel_addr, robot)

            # ── Arm pickup tick ──────────────────────────────────────────
            if _pickup_phase == "lowering":
                _pickup_tick += 1
                frac   = min(1.0, _pickup_tick / ARM_LOWER_TICKS)
                _arm_z = ARM_LIFT_RANGE * frac
                _write_arm(_arm_z)

                if _pickup_tick >= ARM_LOWER_TICKS:
                    # Contact check: horizontal gripper → cap distance
                    gx, gy, _ = gripper_world_xyz(robot, _arm_z)
                    cx = float(data.xpos[cap_body_ids[_active_cap]][0])
                    cy = float(data.xpos[cap_body_ids[_active_cap]][1])
                    dist_xy = math.hypot(gx - cx, gy - cy)
                    print(
                        f"[arm] contact check  gripper=({gx:.3f},{gy:.3f})"
                        f"  cap=({cx:.3f},{cy:.3f})"
                        f"  dist_xy={dist_xy:.3f} m"
                        f"  threshold={ATTACH_DIST_XY:.3f} m"
                    )
                    if dist_xy <= ATTACH_DIST_XY:
                        _contact_cap_x = cx
                        _contact_cap_y = cy
                        _cap_z         = _CAP_FLOOR_Z
                        _pickup_phase  = "closing"
                        _pickup_tick   = 0
                        print(f"[arm] CLOSING  (contact OK)")
                    else:
                        print(f"[arm] contact FAILED — returning arm to top")
                        _pickup_phase = "returning_failed"
                        _pickup_tick  = 0
                        autonomy.signal_pickup_failed()

            elif _pickup_phase == "closing":
                _pickup_tick += 1
                frac   = min(1.0, _pickup_tick / ARM_CLOSE_TICKS)
                gz_now = _gripper_z(_arm_z)   # arm_z still = ARM_LIFT_RANGE
                _cap_z = _CAP_FLOOR_Z + (gz_now - _CAP_FLOOR_Z) * frac
                _write_arm(_arm_z)             # hold arm position

                if _active_cap in cap_qpos:
                    _write_cap_xyz(
                        data, cap_qpos[_active_cap], cap_qvel[_active_cap],
                        _contact_cap_x, _contact_cap_y, _cap_z,
                    )

                if _pickup_tick >= ARM_CLOSE_TICKS:
                    gx, gy, _ = gripper_world_xyz(robot, _arm_z)
                    _attach_x_off = _contact_cap_x - gx
                    _attach_y_off = _contact_cap_y - gy
                    _pickup_phase = "raising"
                    _pickup_tick  = 0
                    print(
                        f"[arm] RAISING"
                        f"  attach_off=({_attach_x_off:+.3f},{_attach_y_off:+.3f})"
                    )

            elif _pickup_phase == "raising":
                _pickup_tick += 1
                frac   = min(1.0, _pickup_tick / ARM_RAISE_TICKS)
                _arm_z = ARM_LIFT_RANGE * (1.0 - frac)
                _write_arm(_arm_z)

                if _active_cap in cap_qpos:
                    gx, gy, _ = gripper_world_xyz(robot, _arm_z)
                    cap_z = _gripper_z(_arm_z)
                    _write_cap_xyz(
                        data, cap_qpos[_active_cap], cap_qvel[_active_cap],
                        gx + _attach_x_off, gy + _attach_y_off, cap_z,
                    )

                if _pickup_tick >= ARM_RAISE_TICKS:
                    _arm_z        = 0.0
                    _write_arm(0.0)
                    _pickup_phase = "holding"
                    _pickup_tick  = 0
                    autonomy.signal_pickup_complete(_active_cap)
                    print(f"[arm] HOLDING  cap_id={_active_cap}")

            elif _pickup_phase == "holding":
                # Cap follows gripper (robot is stationary, but keep in sync)
                _write_arm(0.0)
                if _active_cap in cap_qpos:
                    gx, gy, gz = gripper_world_xyz(robot, 0.0)
                    _write_cap_xyz(
                        data, cap_qpos[_active_cap], cap_qvel[_active_cap],
                        gx + _attach_x_off, gy + _attach_y_off, gz,
                    )

            elif _pickup_phase == "returning_failed":
                # Smoothly raise arm back to 0 after a failed contact check
                _pickup_tick += 1
                frac   = min(1.0, _pickup_tick / ARM_RAISE_TICKS)
                _arm_z = ARM_LIFT_RANGE * (1.0 - frac)
                _write_arm(_arm_z)
                if _pickup_tick >= ARM_RAISE_TICKS:
                    _arm_z        = 0.0
                    _write_arm(0.0)
                    _pickup_phase = "idle"
                    _active_cap   = None

            # ── Physics step + render ─────────────────────────────────────
            mujoco.mj_step(model, data)
            viewer.sync()
            step += 1

            elapsed = time.perf_counter() - t0
            if elapsed < dt:
                time.sleep(dt - elapsed)
