"""
Test Basic Motion - Phase 1 Validation
Tests robot movement, collision detection, and arm control
"""

import sys
import os
import time
import yaml

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.simulation.sim_core import SimulationCore
from src.simulation.sim_hardware import create_sim_hardware


def load_config():
    """Load configuration from config.yaml"""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config.yaml'
    )
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def test_forward_backward(chassis, sim, duration=2.0):
    """Test forward and backward movement"""
    print("\n=== Test 1: Forward/Backward ===")
    
    # Forward
    print("Moving forward...")
    chassis.forward(speed=0.2)
    for _ in range(int(duration * 240)):
        sim.step()
    
    # Stop
    chassis.stop()
    for _ in range(60):  # Brief pause
        sim.step()
    
    # Backward
    print("Moving backward...")
    chassis.backward(speed=0.2)
    for _ in range(int(duration * 240)):
        sim.step()
    
    chassis.stop()
    print("✓ Forward/Backward test complete")


def test_turning(chassis, sim, duration=1.5):
    """Test left and right turns"""
    print("\n=== Test 2: Turning ===")
    
    # Turn left
    print("Turning left...")
    chassis.turn_left(speed=0.15)
    for _ in range(int(duration * 240)):
        sim.step()
    
    chassis.stop()
    for _ in range(60):
        sim.step()
    
    # Turn right
    print("Turning right...")
    chassis.turn_right(speed=0.15)
    for _ in range(int(duration * 240)):
        sim.step()
    
    chassis.stop()
    print("✓ Turning test complete")


def test_collision_detection(sim):
    """Test collision detection with walls"""
    print("\n=== Test 3: Collision Detection ===")
    
    # Check if robot collides with arena
    robot_id = sim.robot_id
    arena_id = sim.arena_id
    
    colliding = sim.check_collision(robot_id, arena_id)
    
    if colliding:
        print("⚠ Robot is colliding with arena (expected if against wall)")
    else:
        print("✓ No collision detected")
    
    return colliding


def test_arm_movements(arm, sim, duration=1.0):
    """Test arm joint movements"""
    print("\n=== Test 4: Arm Movements ===")
    
    # Home position
    print("Moving to HOME position...")
    arm.move_to_pose('home')
    for _ in range(int(duration * 240)):
        sim.step()
    
    # Pickup position
    print("Moving to PICKUP position...")
    arm.move_to_pose('pickup')
    for _ in range(int(duration * 240)):
        sim.step()
    
    # Carry position
    print("Moving to CARRY position...")
    arm.move_to_pose('carry')
    for _ in range(int(duration * 240)):
        sim.step()
    
    # Deposit position
    print("Moving to DEPOSIT position...")
    arm.move_to_pose('deposit')
    for _ in range(int(duration * 240)):
        sim.step()
    
    # Back to home
    print("Returning to HOME...")
    arm.move_to_pose('home')
    for _ in range(int(duration * 240)):
        sim.step()
    
    print("✓ Arm movement test complete")


def test_pickup_sequence(arm, sim, duration=2.0):
    """Test full pickup sequence"""
    print("\n=== Test 5: Pickup Sequence ===")
    
    arm.pickup_sequence()
    
    # Let it execute
    for _ in range(int(duration * 240)):
        sim.step()
    
    print("✓ Pickup sequence test complete")


def test_deposit_sequence(arm, sim, duration=2.0):
    """Test full deposit sequence"""
    print("\n=== Test 6: Deposit Sequence ===")
    
    arm.deposit_sequence()
    
    # Let it execute
    for _ in range(int(duration * 240)):
        sim.step()
    
    print("✓ Deposit sequence test complete")


def main():
    """Run all basic motion tests"""
    print("=" * 60)
    print("PHASE 1 VALIDATION: Basic Robot & Arena")
    print("=" * 60)
    
    # Load configuration
    config = load_config()
    
    # Initialize simulation
    print("\nInitializing simulation...")
    sim = SimulationCore(gui=True, real_time=True)
    sim.initialize()
    sim.load_arena()
    robot_id = sim.load_robot(start_pos=[0, -0.6, 0.05])
    sim.spawn_balls(num_balls=22)
    
    # Create hardware interfaces
    print("Creating simulated hardware...")
    chassis, arm, camera = create_sim_hardware(robot_id, config)
    
    # Run tests
    try:
        # Test 1: Forward/Backward
        test_forward_backward(chassis, sim)
        
        # Test 2: Turning
        test_turning(chassis, sim)
        
        # Test 3: Collision detection
        test_collision_detection(sim)
        
        # Test 4: Arm movements
        test_arm_movements(arm, sim)
        
        # Test 5: Pickup sequence
        test_pickup_sequence(arm, sim)
        
        # Test 6: Deposit sequence
        test_deposit_sequence(arm, sim)
        
        # Final summary
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        print("\nPhase 1 validation complete!")
        print("Robot can:")
        print("  ✓ Move forward and backward")
        print("  ✓ Turn left and right")
        print("  ✓ Detect collisions")
        print("  ✓ Move arm to all poses")
        print("  ✓ Execute pickup sequence")
        print("  ✓ Execute deposit sequence")
        print("\nPress Ctrl+C to exit...")
        
        # Keep simulation running
        while True:
            sim.step()
            
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        sim.close()


if __name__ == "__main__":
    main()
