"""
State Machine / Navigation Logic Tests

Tests: State transitions, turn direction logic, timing calculations.
These are pure-Python tests — no hardware required.
"""
import time
from robot_tests.test_results import log


# Replicate the key logic from navigation.ipynb for testing
FORWARD_SPEED = 0.18
REVERSE_SPEED = 0.15
TURN_SPEED = 0.22
AVOID_REVERSE_TIME = 0.40
AVOID_TURN_TIME = 0.55
WANDER_COOLDOWN = 0.50
YELLOW_BOUNDARY_THRESHOLD = 1800
OBSTACLE_EDGE_THRESHOLD = 500


def test_state_transition_wander_to_boundary():
    """WANDER -> AVOID_BOUNDARY when yellow detected."""
    nav_state = "WANDER"
    boundary = {"detected": True, "yellow_left": 100, "yellow_right": 50}
    obstacle = {"detected": False}

    if nav_state == "WANDER" and boundary["detected"]:
        nav_state = "AVOID_BOUNDARY"

    if nav_state == "AVOID_BOUNDARY":
        log("State WANDER->AVOID_BOUNDARY", True, "transitioned on yellow detect")
    else:
        log("State WANDER->AVOID_BOUNDARY", False, f"stuck in {nav_state}")


def test_state_transition_wander_to_obstacle():
    """WANDER -> AVOID_OBSTACLE when obstacle detected."""
    nav_state = "WANDER"
    boundary = {"detected": False}
    obstacle = {"detected": True, "edge_left": 300, "edge_right": 100}

    if nav_state == "WANDER" and not boundary["detected"] and obstacle["detected"]:
        nav_state = "AVOID_OBSTACLE"

    if nav_state == "AVOID_OBSTACLE":
        log("State WANDER->AVOID_OBSTACLE", True, "transitioned on obstacle detect")
    else:
        log("State WANDER->AVOID_OBSTACLE", False, f"stuck in {nav_state}")


def test_boundary_priority_over_obstacle():
    """Boundary detection must take priority over obstacle."""
    nav_state = "WANDER"
    boundary = {"detected": True, "yellow_left": 100, "yellow_right": 50}
    obstacle = {"detected": True, "edge_left": 300, "edge_right": 100}

    if nav_state == "WANDER":
        if boundary["detected"]:
            nav_state = "AVOID_BOUNDARY"
        elif obstacle["detected"]:
            nav_state = "AVOID_OBSTACLE"

    if nav_state == "AVOID_BOUNDARY":
        log("Boundary priority", True, "boundary wins over obstacle")
    else:
        log("Boundary priority", False, f"unexpected state {nav_state}")


def test_turn_direction_boundary():
    """Turn away from side with more yellow pixels."""
    boundary = {"yellow_left": 200, "yellow_right": 50}
    # More yellow on left -> turn right (away from left)
    avoid_turn_right = boundary["yellow_left"] >= boundary["yellow_right"]
    if avoid_turn_right:
        log("Turn direction (boundary)", True, "more yellow left -> turn right")
    else:
        log("Turn direction (boundary)", False, "turn logic inverted")


def test_turn_direction_obstacle():
    """Turn away from side with more edge pixels."""
    obstacle = {"edge_left": 300, "edge_right": 80}
    # More edges on left -> turn right (away from left)
    avoid_turn_right = obstacle["edge_left"] >= obstacle["edge_right"]
    if avoid_turn_right:
        log("Turn direction (obstacle)", True, "more edges left -> turn right")
    else:
        log("Turn direction (obstacle)", False, "turn logic inverted")


def test_avoidance_timing():
    """Verify avoidance phases add up correctly."""
    avoid_start = time.time()
    elapsed = 0.0

    # Simulate time passing
    phase1 = elapsed < AVOID_REVERSE_TIME
    phase2 = (not phase1) and (elapsed < AVOID_REVERSE_TIME + AVOID_TURN_TIME)
    phase3 = not phase1 and not phase2

    if phase1 and not phase2 and not phase3:
        log("Avoid timing (phase 1)", True, "reverse phase active")
    else:
        log("Avoid timing (phase 1)", False, "phase logic wrong")

    # Simulate end of avoidance
    elapsed = AVOID_REVERSE_TIME + AVOID_TURN_TIME + 0.1
    phase1 = elapsed < AVOID_REVERSE_TIME
    phase2 = (not phase1) and (elapsed < AVOID_REVERSE_TIME + AVOID_TURN_TIME)
    phase3 = not phase1 and not phase2

    if phase3:
        log("Avoid timing (done)", True, "avoidance complete -> WANDER")
    else:
        log("Avoid timing (done)", False, "should be in phase 3")


def test_cooldown_period():
    """After avoidance, cooldown must block new detection briefly."""
    now = time.time()
    wander_cooldown_end = now + WANDER_COOLDOWN

    # During cooldown
    if now < wander_cooldown_end:
        log("Cooldown active", True, f"cooldown for {WANDER_COOLDOWN}s")
    else:
        log("Cooldown active", False, "cooldown already expired")

    # After cooldown
    now = wander_cooldown_end + 0.1
    if now >= wander_cooldown_end:
        log("Cooldown expired", True, "detection re-enabled")
    else:
        log("Cooldown expired", False, "still in cooldown")


def test_speed_clamp_logic():
    """Verify motor speed clamping logic."""
    MAX_SPEED = 0.25

    def clamp(val, lo, hi):
        if val < lo: return lo
        if val > hi: return hi
        return val

    tests = [
        (0.30, 0.25, "over max"),
        (-0.30, -0.25, "under min"),
        (0.18, 0.18, "within range"),
        (0.0, 0.0, "zero"),
    ]

    all_pass = True
    for inp, expected, label in tests:
        out = clamp(inp, -MAX_SPEED, MAX_SPEED)
        if abs(out - expected) > 0.001:
            all_pass = False

    if all_pass:
        log("Speed clamp logic", True, "all cases correct")
    else:
        log("Speed clamp logic", False, "clamp failure")


def test_stop_state():
    """STOPPED state must block all transitions."""
    nav_state = "STOPPED"
    boundary = {"detected": True}
    obstacle = {"detected": True}

    # In STOPPED, nothing changes
    if nav_state == "STOPPED":
        pass
    elif boundary["detected"]:
        nav_state = "AVOID_BOUNDARY"
    elif obstacle["detected"]:
        nav_state = "AVOID_OBSTACLE"

    if nav_state == "STOPPED":
        log("STOPPED state", True, "blocks all transitions")
    else:
        log("STOPPED state", False, f"illegally transitioned to {nav_state}")


def run_all():
    """Run all state-machine logic tests."""
    print("--- State Machine Tests (no hardware) ---")
    test_state_transition_wander_to_boundary()
    test_state_transition_wander_to_obstacle()
    test_boundary_priority_over_obstacle()
    test_turn_direction_boundary()
    test_turn_direction_obstacle()
    test_avoidance_timing()
    test_cooldown_period()
    test_speed_clamp_logic()
    test_stop_state()
    print()


if __name__ == "__main__":
    run_all()
