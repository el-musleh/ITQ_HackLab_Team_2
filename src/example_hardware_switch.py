#!/usr/bin/env python3
"""
Example: Hardware API Compatibility Demo

This script demonstrates how to switch between simulation and hardware
with a SINGLE line change. The rest of the code is IDENTICAL!
"""

import time
import yaml

# ============================================================
# SWITCH BETWEEN SIMULATION AND HARDWARE HERE!
# ============================================================
USE_SIMULATION = True  # Change to False for real hardware
# ============================================================

# Load configuration (same for both!)
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Import based on mode
if USE_SIMULATION:
    print("🤖 Running in SIMULATION mode")
    from simulation import ChassisController, ArmController, CameraController
    from simulation.sim_core import SimulationCore
    
    # Simulation-specific setup
    sim = SimulationCore(gui=True, real_time=True)
    sim.initialize()
    sim.load_arena()
    robot_id = sim.load_robot()
    
    # Create hardware instances
    chassis = ChassisController(robot_id, max_speed=0.25)
    arm = ArmController(robot_id, config)
    camera = CameraController(config, robot_id=robot_id)
    
else:
    print("🦾 Running on REAL HARDWARE")
    from hardware.chassis import ChassisController
    from hardware.arm import ArmController
    from hardware.camera import CameraController
    from jetbot import Robot
    
    # Hardware-specific setup
    robot = Robot()
    
    # Create hardware instances
    chassis = ChassisController(robot, max_speed=0.25)
    arm = ArmController(config)
    camera = CameraController(config)
    camera.initialize()


# ============================================================
# REST OF CODE IS IDENTICAL FOR BOTH!
# ============================================================

def demo_movement():
    """Demo basic movement - works on both sim and hardware!"""
    print("\n--- Movement Demo ---")
    
    print("Moving forward...")
    chassis.forward(speed=0.15)
    time.sleep(2.0)
    chassis.stop()
    
    print("Turning left...")
    chassis.turn_left(speed=0.10)
    time.sleep(1.0)
    chassis.stop()
    
    print("Moving backward...")
    chassis.backward(speed=0.15)
    time.sleep(2.0)
    chassis.stop()
    
    print("✓ Movement demo complete!")


def demo_arm():
    """Demo arm control - works on both sim and hardware!"""
    print("\n--- Arm Demo ---")
    
    print("Moving to home position...")
    arm.home()
    time.sleep(1.0)
    
    print("Opening gripper...")
    arm.gripper_open()
    time.sleep(0.5)
    
    print("Moving to pickup position...")
    arm.move_to_pose(arm.pose_pickup, speed=arm.slow_speed)
    time.sleep(1.5)
    
    print("Closing gripper...")
    arm.gripper_close()
    time.sleep(0.5)
    
    print("Moving to carry position...")
    arm.move_to_pose(arm.pose_carry, speed=arm.default_speed)
    time.sleep(1.0)
    
    print("Returning to home...")
    arm.home()
    time.sleep(1.0)
    
    print("✓ Arm demo complete!")


def demo_camera():
    """Demo camera - works on both sim and hardware!"""
    print("\n--- Camera Demo ---")
    
    print("Centering camera...")
    camera.center()
    
    print("Reading frame...")
    frame = camera.read()
    
    if frame is not None:
        print(f"✓ Frame captured: {frame.shape}")
        print(f"  Size: {camera.get_frame_size()}")
    else:
        print("✗ Failed to capture frame")
    
    print("Looking down...")
    camera.look_down()
    
    print("Looking forward...")
    camera.look_forward()
    
    print("✓ Camera demo complete!")


def main():
    """Run all demos"""
    print("="*60)
    print("HARDWARE API COMPATIBILITY DEMO")
    print("="*60)
    
    try:
        # Run demos
        demo_movement()
        demo_arm()
        demo_camera()
        
        print("\n" + "="*60)
        print("✓ ALL DEMOS COMPLETE!")
        print("="*60)
        
        # Show motor values
        left, right = chassis.get_motor_values()
        print(f"\nFinal motor values: left={left:.2f}, right={right:.2f}")
        
        # Show arm pose
        pose = arm.get_current_pose()
        print(f"Final arm pose: {pose}")
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    
    finally:
        # Cleanup
        print("\nCleaning up...")
        chassis.stop()
        arm.home()
        
        if USE_SIMULATION:
            print("Closing simulation...")
            sim.close()
        else:
            print("Releasing camera...")
            camera.release()
        
        print("✓ Cleanup complete!")


if __name__ == '__main__':
    main()
