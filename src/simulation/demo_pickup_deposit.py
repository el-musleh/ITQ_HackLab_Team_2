"""
Complete Pickup and Deposit Demo
Demonstrates full workflow: find ball → approach → pickup → find basket → deposit
"""

import sys
import os
import time
import yaml
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.simulation.sim_core import SimulationCore
from src.simulation.sim_hardware import create_sim_hardware
from src.perception.ball_detector import BallDetector
from src.perception.basket_detector import BasketDetector
from src.utils import load_config


def find_closest_ball(camera, ball_detector, sim, max_attempts=100):
    """Rotate to find the closest ball"""
    print("\n🔍 Searching for balls...")
    
    best_ball = None
    best_distance = float('inf')
    
    for i in range(max_attempts):
        frame = camera.read()
        if frame is not None and frame.size > 0:
            balls = ball_detector.detect(frame)
            
            if balls:
                # Find closest ball
                for ball in balls:
                    color, (cx, cy), distance, area = ball
                    if distance < best_distance:
                        best_distance = distance
                        best_ball = ball
                
                if best_ball:
                    print(f"✓ Found {best_ball[0]} ball at distance {best_ball[2]:.1f}cm")
                    return best_ball
        
        sim.step()
    
    return None


def approach_ball(chassis, camera, ball_detector, sim, target_ball, duration=10.0):
    """Approach the target ball using visual servoing"""
    print(f"\n🚗 Approaching {target_ball[0]} ball...")
    
    start_time = time.time()
    frame_width = 320
    center_x = frame_width / 2
    
    while time.time() - start_time < duration:
        frame = camera.read()
        
        if frame is not None and frame.size > 0:
            balls = ball_detector.detect(frame)
            
            # Find our target ball (same color)
            target_color = target_ball[0]
            current_ball = None
            
            for ball in balls:
                if ball[0] == target_color:
                    current_ball = ball
                    break
            
            if current_ball:
                color, (cx, cy), distance, area = current_ball
                
                # Calculate error from center
                error = cx - center_x
                
                # Simple proportional control
                turn_speed = error / frame_width * 0.15
                
                # If ball is centered and close, stop
                if abs(error) < 30 and area > 800:
                    print("✓ Ball reached!")
                    chassis.stop()
                    return True
                
                # Move forward with slight turning
                forward_speed = 0.12
                chassis.set_motors(
                    forward_speed - turn_speed,
                    forward_speed + turn_speed
                )
            else:
                # Lost the ball, stop
                chassis.stop()
                print("⚠ Lost sight of ball")
                return False
        
        sim.step()
    
    chassis.stop()
    print("⏱ Approach timeout")
    return False


def pickup_ball(arm, chassis, sim, hold_time=3.0):
    """Execute pickup sequence"""
    print("\n🤖 Executing pickup sequence...")
    
    chassis.stop()
    
    # Move to pickup position
    print("  Lowering arm...")
    arm.set_joint_angles([0, -45, -70, -30])  # Reach down
    
    # Wait for arm to move
    for _ in range(120):  # 0.5 seconds
        sim.step()
    
    # Close gripper (simulated by moving wrist)
    print("  Closing gripper...")
    arm.set_joint_angles([0, -45, -70, 0])
    
    for _ in range(60):
        sim.step()
    
    # Lift to carry position
    print("  Lifting ball...")
    arm.set_joint_angles([0, 20, 40, 90])  # Carry position
    
    for _ in range(120):
        sim.step()
    
    print("✓ Pickup complete!")
    return True


def find_basket(chassis, camera, basket_detector, sim, max_duration=15.0):
    """Rotate to find the basket"""
    print("\n🔍 Searching for basket...")
    
    start_time = time.time()
    chassis.turn_left(speed=0.1)
    
    while time.time() - start_time < max_duration:
        frame = camera.read()
        
        if frame is not None and frame.size > 0:
            basket = basket_detector.detect(frame)
            
            if basket and basket.get('detected', False):
                chassis.stop()
                print(f"✓ Found basket at angle {basket.get('angle', 0):.1f}°")
                return basket
        
        sim.step()
    
    chassis.stop()
    print("⚠ Basket not found")
    return None


def approach_basket(chassis, camera, basket_detector, sim, duration=10.0):
    """Approach the basket"""
    print("\n🚗 Approaching basket...")
    
    start_time = time.time()
    frame_width = 320
    center_x = frame_width / 2
    
    while time.time() - start_time < duration:
        frame = camera.read()
        
        if frame is not None and frame.size > 0:
            basket = basket_detector.detect(frame)
            
            if basket and basket.get('detected', False):
                bx = basket.get('center_x', center_x)
                
                # Calculate error
                error = bx - center_x
                turn_speed = error / frame_width * 0.12
                
                # Check if close enough
                distance = basket.get('distance_px', 1000)
                if abs(error) < 40 and distance < 150:
                    print("✓ Basket reached!")
                    chassis.stop()
                    return True
                
                # Move forward with turning
                forward_speed = 0.10
                chassis.set_motors(
                    forward_speed - turn_speed,
                    forward_speed + turn_speed
                )
            else:
                chassis.stop()
                print("⚠ Lost sight of basket")
                return False
        
        sim.step()
    
    chassis.stop()
    print("⏱ Approach timeout")
    return False


def deposit_ball(arm, chassis, sim):
    """Execute deposit sequence"""
    print("\n🤖 Depositing ball...")
    
    chassis.stop()
    
    # Move to deposit position
    print("  Raising arm...")
    arm.set_joint_angles([0, 50, 50, 45])  # Reach up
    
    for _ in range(120):
        sim.step()
    
    # Open gripper
    print("  Opening gripper...")
    arm.set_joint_angles([0, 50, 50, -30])
    
    for _ in range(60):
        sim.step()
    
    # Return to home
    print("  Returning to home...")
    arm.set_joint_angles([0, 0, 0, 0])
    
    for _ in range(120):
        sim.step()
    
    print("✓ Deposit complete!")
    return True


def visualize_state(frame, state_text, ball_detector, basket_detector, balls, basket):
    """Create visualization with current state"""
    if frame is None or frame.size == 0:
        return None
    
    display = frame.copy()
    
    # Draw balls
    if balls:
        display = ball_detector.draw_detections(display, balls)
    
    # Draw basket
    if basket and basket.get('detected', False):
        bx = int(basket.get('center_x', 0))
        by = int(basket.get('center_y', 0))
        cv2.circle(display, (bx, by), 8, (128, 128, 128), -1)
        cv2.putText(display, "BASKET", (bx + 15, by),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 2)
    
    # Draw state
    cv2.putText(display, state_text, (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    return display


def main():
    print("=" * 60)
    print("COMPLETE PICKUP & DEPOSIT DEMONSTRATION")
    print("=" * 60)
    print("\nThis demo will:")
    print("  1. Search for a ball")
    print("  2. Approach the ball")
    print("  3. Pick up the ball")
    print("  4. Search for the basket")
    print("  5. Approach the basket")
    print("  6. Deposit the ball")
    print("\nStarting in 3 seconds...")
    
    time.sleep(3)
    
    # Load config
    config = load_config()
    
    # Initialize simulation
    print("\n📦 Initializing simulation...")
    sim = SimulationCore(gui=True, real_time=True)
    sim.initialize()
    sim.load_arena()
    robot_id = sim.load_robot(start_pos=[0, -0.6, 0.05])
    sim.spawn_balls(num_balls=22)
    
    # Create hardware
    chassis, arm, camera = create_sim_hardware(robot_id, config)
    
    # Create perception
    ball_detector = BallDetector(config)
    basket_detector = BasketDetector(config)
    
    print("✓ Initialization complete\n")
    
    try:
        # State 1: Find ball
        state = "SEARCHING FOR BALL"
        print(f"\n{'='*60}")
        print(f"STATE: {state}")
        print('='*60)
        
        chassis.turn_left(speed=0.1)
        target_ball = find_closest_ball(camera, ball_detector, sim, max_attempts=200)
        chassis.stop()
        
        if not target_ball:
            print("\n❌ No balls found!")
            return
        
        # State 2: Approach ball
        state = f"APPROACHING {target_ball[0].upper()} BALL"
        print(f"\n{'='*60}")
        print(f"STATE: {state}")
        print('='*60)
        
        success = approach_ball(chassis, camera, ball_detector, sim, target_ball)
        
        if not success:
            print("\n❌ Failed to approach ball!")
            return
        
        # State 3: Pickup
        state = "PICKING UP BALL"
        print(f"\n{'='*60}")
        print(f"STATE: {state}")
        print('='*60)
        
        pickup_ball(arm, chassis, sim)
        
        # State 4: Find basket
        state = "SEARCHING FOR BASKET"
        print(f"\n{'='*60}")
        print(f"STATE: {state}")
        print('='*60)
        
        basket = find_basket(chassis, camera, basket_detector, sim)
        
        if not basket:
            print("\n❌ Basket not found!")
            return
        
        # State 5: Approach basket
        state = "APPROACHING BASKET"
        print(f"\n{'='*60}")
        print(f"STATE: {state}")
        print('='*60)
        
        success = approach_basket(chassis, camera, basket_detector, sim)
        
        if not success:
            print("\n❌ Failed to approach basket!")
            return
        
        # State 6: Deposit
        state = "DEPOSITING BALL"
        print(f"\n{'='*60}")
        print(f"STATE: {state}")
        print('='*60)
        
        deposit_ball(arm, chassis, sim)
        
        # Success!
        print("\n" + "=" * 60)
        print("🎉 MISSION COMPLETE! 🎉")
        print("=" * 60)
        print("\n✓ Ball successfully picked up and deposited in basket!")
        print("\nPress Ctrl+C to exit...")
        
        # Keep simulation running
        while True:
            frame = camera.read()
            if frame is not None and frame.size > 0:
                cv2.imshow('Demo Complete', frame)
                cv2.waitKey(1)
            sim.step()
            
    except KeyboardInterrupt:
        print("\n\nDemo stopped by user")
    finally:
        chassis.stop()
        cv2.destroyAllWindows()
        sim.close()


if __name__ == "__main__":
    main()
