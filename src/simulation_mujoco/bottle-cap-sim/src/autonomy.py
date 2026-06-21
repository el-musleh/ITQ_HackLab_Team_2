"""Finite-state machine: SEARCH → APPROACH → STOPPED → PICKUP → HOLDING.

Pickup phases (LOWER_GRIPPER / CLOSE / RAISE) are driven entirely by the
viewer, which owns the arm joint and cap position.  The controller holds in
FSM.PICKUP and waits for signal_pickup_complete() or signal_pickup_failed().
"""

import math
from enum import Enum
from typing import List, Optional, Tuple

from src.config import (
    ARM_REACH, HEADING_KP,
    LINEAR_SPEED, ANGULAR_SPEED, SEARCH_OMEGA,
    WRIST_CAM_OFFSET,
)
from src.vision import CapObservation


class FSM(Enum):
    SEARCH   = "SEARCH"
    APPROACH = "APPROACH"
    STOPPED  = "STOPPED"   # transitional — starts pickup on next tick
    PICKUP   = "PICKUP"    # arm sequence running in viewer
    HOLDING  = "HOLDING"   # cap attached, following gripper


def _norm(a: float) -> float:
    """Wrap angle to (−π, +π]."""
    while a > math.pi:
        a -= 2.0 * math.pi
    while a <= -math.pi:
        a += 2.0 * math.pi
    return a


_PROXIMITY_STOP: float = WRIST_CAM_OFFSET[0] + ARM_REACH + 0.05  # ≈ 0.457 m
_MAX_APPROACH_TICKS: int = 750   # 30 s @ 25 Hz


class AutonomyController:
    def __init__(self) -> None:
        self.state: FSM = FSM.SEARCH
        self.target_id: Optional[int] = None
        self.target_color: Optional[str] = None

        self.held_cap_id: Optional[int] = None
        self.collected_caps: List[int] = []

        self._log_step: int = 0
        self._stopped_logged: bool = False
        self._last_dist: Optional[float] = None
        self._approach_ticks: int = 0

    # ── Public step ────────────────────────────────────────────────────────

    def step(
        self,
        robot_x: float,
        robot_y: float,
        robot_theta: float,
        visible: List[CapObservation],
    ) -> Tuple[float, float]:
        self._log_step += 1

        if self.state is FSM.SEARCH:
            return self._search(visible)
        if self.state is FSM.APPROACH:
            return self._approach(robot_x, robot_y, robot_theta, visible)
        if self.state is FSM.STOPPED:
            return self._begin_pickup()
        # PICKUP and HOLDING: robot stays still, viewer drives arm + cap
        return 0.0, 0.0

    # ── Viewer signals ─────────────────────────────────────────────────────

    def signal_pickup_complete(self, cap_id: int) -> None:
        """Viewer calls this when the arm has finished lifting the cap."""
        self.collected_caps.append(cap_id)
        self.held_cap_id = cap_id
        print(
            f"[pickup] ✓ SUCCESS"
            f"  cap_id={cap_id}  color={self.target_color}"
            f"  total_collected={len(self.collected_caps)}"
        )
        self.state = FSM.HOLDING

    def signal_pickup_failed(self) -> None:
        """Viewer calls this when the contact distance check fails."""
        print(
            f"[pickup] ✗ FAILED"
            f"  cap_id={self.target_id}  (gripper did not reach cap)"
        )
        self._reset_approach()

    # ── FSM states ─────────────────────────────────────────────────────────

    def _search(self, visible: List[CapObservation]) -> Tuple[float, float]:
        available = [o for o in visible if o.cap_id not in self.collected_caps]
        if not available:
            return 0.0, SEARCH_OMEGA

        target = available[0]
        self.target_id = target.cap_id
        self.target_color = target.color
        self.state = FSM.APPROACH
        self._last_dist = target.distance
        self._approach_ticks = 0
        print(
            f"[FSM] SEARCH → APPROACH"
            f"  cap_id={target.cap_id}  color={target.color}"
            f"  dist={target.distance:.2f} m"
            f"  cam_angle={math.degrees(target.angle):+.1f}°"
        )
        return 0.0, 0.0

    def _approach(
        self,
        rx: float,
        ry: float,
        robot_theta: float,
        visible: List[CapObservation],
    ) -> Tuple[float, float]:
        self._approach_ticks += 1

        if self._approach_ticks > _MAX_APPROACH_TICKS:
            print(
                f"[FSM] APPROACH timeout → SEARCH"
                f"  (cap {self.target_id} unreachable)"
            )
            self._reset_approach()
            return 0.0, SEARCH_OMEGA

        target = next((o for o in visible if o.cap_id == self.target_id), None)

        if target is None:
            if self._last_dist is not None and self._last_dist <= _PROXIMITY_STOP:
                if not self._stopped_logged:
                    self._stopped_logged = True
                    print(
                        f"[FSM] APPROACH → STOPPED"
                        f"  cap_id={self.target_id}  color={self.target_color}"
                        f"  last_dist={self._last_dist:.3f} m  (cap under camera)"
                    )
                self.state = FSM.STOPPED
                return 0.0, 0.0
            else:
                last = f"{self._last_dist:.3f} m" if self._last_dist else "unknown"
                print(f"[FSM] APPROACH → SEARCH  (cap {self.target_id} lost at {last})")
                self._reset_approach()
                return 0.0, SEARCH_OMEGA

        dx = target.world_x - rx
        dy = target.world_y - ry
        dist = math.hypot(dx, dy)
        heading_err = _norm(math.atan2(dy, dx) - robot_theta)
        self._last_dist = dist

        if self._log_step % 50 == 0:
            print(
                f"[vision] cap_id={target.cap_id}  color={target.color}"
                f"  dist={dist:.3f} m  heading_err={math.degrees(heading_err):+.1f}°"
            )

        if dist <= ARM_REACH:
            if not self._stopped_logged:
                self._stopped_logged = True
                print(
                    f"[FSM] APPROACH → STOPPED"
                    f"  cap_id={target.cap_id}  color={target.color}"
                    f"  dist={dist:.3f} m"
                )
            self.state = FSM.STOPPED
            return 0.0, 0.0

        omega = HEADING_KP * heading_err
        omega = max(-ANGULAR_SPEED, min(ANGULAR_SPEED, omega))
        alignment = max(0.0, 1.0 - abs(heading_err) / (math.pi / 4.0))
        return LINEAR_SPEED * alignment, omega

    def _begin_pickup(self) -> Tuple[float, float]:
        if self.target_id is None:
            self._reset_approach()
            return 0.0, SEARCH_OMEGA
        print(
            f"[pickup] Starting"
            f"  cap_id={self.target_id}  color={self.target_color}"
        )
        self.state = FSM.PICKUP
        return 0.0, 0.0

    # ── Helpers ────────────────────────────────────────────────────────────

    def _reset_approach(self) -> None:
        self.state = FSM.SEARCH
        self.target_id = None
        self.target_color = None
        self._last_dist = None
        self._approach_ticks = 0
        self._stopped_logged = False
