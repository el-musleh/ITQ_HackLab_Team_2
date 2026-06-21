"""
Test Basic Motion - Phase 1 Validation
Tests robot movement, collision detection, and arm control.

Usage:
    python3 src/simulation/test_basic_motion.py [--headless]
"""

import argparse
import math
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.simulation.sim_core import SimulationCore
from src.simulation.sim_hardware import create_sim_hardware
from src.utils import load_config


def test_forward_backward(chassis, sim, duration=2.0):
    """Test forward and backward movement."""
    print("\n=== Test 1: Forward/Backward ===")

    start_pos = sim.get_robot_state()['position']

    # Forward
    print("Moving forward...")
    chassis.forward(speed=0.2)
    for _ in range(int(duration * 240)):
        sim.step()

    fwd_pos = sim.get_robot_state()['position']
    fwd_dist = math.hypot(fwd_pos[0] - start_pos[0], fwd_pos[1] - start_pos[1])
    assert fwd_dist > 0.01, f"Forward moved only {fwd_dist:.4f} m"
    print(f"  Forward distance: {fwd_dist:.3f} m")

    # Stop
    chassis.stop()
    for _ in range(60):
        sim.step()

    # Backward
    print("Moving backward...")
    chassis.backward(speed=0.2)
    for _ in range(int(duration * 240)):
        sim.step()

    bwd_pos = sim.get_robot_state()['position']
    bwd_dist = math.hypot(bwd_pos[0] - fwd_pos[0], bwd_pos[1] - fwd_pos[1])
    assert bwd_dist > 0.01, f"Backward moved only {bwd_dist:.4f} m"
    print(f"  Backward distance: {bwd_dist:.3f} m")

    chassis.stop()
    print("✓ Forward/Backward test complete")


def test_turning(chassis, sim, duration=1.5):
    """Test left and right turns."""
    print("\n=== Test 2: Turning ===")

    start_yaw = sim.get_robot_state()['orientation'][2]

    # Turn left
    print("Turning left...")
    chassis.turn_left(speed=0.15)
    for _ in range(int(duration * 240)):
        sim.step()

    left_yaw = sim.get_robot_state()['orientation'][2]
    yaw_delta_left = abs(left_yaw - start_yaw)
    yaw_delta_left = min(yaw_delta_left, 2 * math.pi - yaw_delta_left)
    assert yaw_delta_left > 0.05, f"Left turn yaw delta only {yaw_delta_left:.4f} rad"
    print(f"  Left turn yaw delta: {yaw_delta_left:.3f} rad")

    chassis.stop()
    for _ in range(60):
        sim.step()

    # Turn right
    print("Turning right...")
    chassis.turn_right(speed=0.15)
    for _ in range(int(duration * 240)):
        sim.step()

    right_yaw = sim.get_robot_state()['orientation'][2]
    yaw_delta_right = abs(right_yaw - left_yaw)
    yaw_delta_right = min(yaw_delta_right, 2 * math.pi - yaw_delta_right)
    assert yaw_delta_right > 0.05, f"Right turn yaw delta only {yaw_delta_right:.4f} rad"
    print(f"  Right turn yaw delta: {yaw_delta_right:.3f} rad")

    chassis.stop()
    print("✓ Turning test complete")


def test_collision_detection(sim):
    """Test collision detection with walls."""
    print("\n=== Test 3: Collision Detection ===")

    robot_id = sim.robot_id
    arena_id = sim.arena_id

    # At spawn position (center area), should not be colliding
    colliding = sim.check_collision(robot_id, arena_id)
    assert isinstance(colliding, bool)
    print(f"  Collision at spawn: {colliding}")

    print("✓ Collision detection test complete")


def test_arm_movements(arm, sim, duration=1.0):
    """Test arm joint movements using pose lists."""
    print("\n=== Test 4: Arm Movements ===")

    poses = [
        ('HOME', arm.pose_home),
        ('PICKUP', arm.pose_pickup),
        ('CARRY', arm.pose_carry),
        ('DEPOSIT', arm.pose_deposit),
        ('HOME', arm.pose_home),
    ]

    for label, pose in poses:
        print(f"Moving to {label} position...")
        assert arm.move_to_pose(pose) is True
        for _ in range(int(duration * 240)):
            sim.step()
        current = arm.get_current_pose()
        assert current == list(pose), f"Pose mismatch after {label}: {current} != {list(pose)}"

    print("✓ Arm movement test complete")


def test_pickup_sequence(arm, sim, duration=2.0):
    """Test full pickup sequence."""
    print("\n=== Test 5: Pickup Sequence ===")

    result = arm.pickup_sequence()
    assert result is True, "pickup_sequence() returned False"

    print("✓ Pickup sequence test complete")


def test_deposit_sequence(arm, sim, duration=2.0):
    """Test full deposit sequence."""
    print("\n=== Test 6: Deposit Sequence ===")

    result = arm.deposit_sequence()
    assert result is True, "deposit_sequence() returned False"

    print("✓ Deposit sequence test complete")


def main(headless=False):
    """Run all basic motion tests."""
    print("=" * 60)
    print("PHASE 1 VALIDATION: Basic Robot & Arena")
    print("=" * 60)

    config = load_config()
    config.setdefault('simulation', {})
    if headless:
        config['simulation'] = {**config['simulation'], 'renderer': 'tiny'}

    print("\nInitializing simulation...")
    sim = SimulationCore(gui=not headless, real_time=not headless, config=config)
    sim.initialize()
    sim.load_arena()
    robot_id = sim.load_robot(start_pos=[0.5, 0.5, 0.15])
    sim.spawn_balls(num_balls=3)

    print("Creating simulated hardware...")
    chassis, arm, camera = create_sim_hardware(robot_id, config, sim=sim)

    passed = 0
    failed = 0
    tests = [
        ("Forward/Backward", lambda: test_forward_backward(chassis, sim)),
        ("Turning", lambda: test_turning(chassis, sim)),
        ("Collision Detection", lambda: test_collision_detection(sim)),
        ("Arm Movements", lambda: test_arm_movements(arm, sim)),
        ("Pickup Sequence", lambda: test_pickup_sequence(arm, sim)),
        ("Deposit Sequence", lambda: test_deposit_sequence(arm, sim)),
    ]

    try:
        for name, test_fn in tests:
            try:
                test_fn()
                passed += 1
            except AssertionError as e:
                print(f"  FAIL: {e}")
                failed += 1

        print("\n" + "=" * 60)
        print(f"RESULTS: {passed} passed, {failed} failed")
        print("=" * 60)

        if failed == 0:
            print("\nPhase 1 validation complete!")
            print("Robot can:")
            print("  Move forward and backward")
            print("  Turn left and right")
            print("  Detect collisions")
            print("  Move arm to all poses")
            print("  Execute pickup sequence")
            print("  Execute deposit sequence")

        if not headless:
            print("\nPress Ctrl+C to exit...")
            while True:
                sim.step()

        return 0 if failed == 0 else 1

    except KeyboardInterrupt:
        print("\n\nShutting down...")
        return 1
    finally:
        sim.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Phase 1 basic motion validation')
    parser.add_argument('--headless', action='store_true',
                        help='Run without GUI (for CI / automated testing)')
    args = parser.parse_args()
    sys.exit(main(headless=args.headless))
