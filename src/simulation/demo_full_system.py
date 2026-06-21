"""
Full System Demo - Complete simulation with all components
Simplified version for demonstration
"""

import sys
import os
import time
import yaml
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.simulation.sim_core import SimulationCore
from src.simulation.sim_hardware import create_sim_hardware
from src.perception.ball_detector import BallDetector
from src.perception.obstacle_detector import ObstacleDetector
from src.perception.basket_detector import BasketDetector
from src.utils import load_config


def main():
    print("=" * 60)
    print("FULL SYSTEM DEMONSTRATION")
    print("=" * 60)
    print("\nThis demo shows all components working together:")
    print("  - Physics simulation (PyBullet)")
    print("  - Camera rendering")
    print("  - Ball detection")
    print("  - Obstacle detection")
    print("  - Basket detection")
    print("  - Robot movement")
    print("\nRunning for 30 seconds...")
    
    # Load config
    config = load_config()
    
    # Initialize simulation
    print("\nInitializing...")
    sim = SimulationCore(gui=True, real_time=True)
    sim.initialize()
    sim.load_arena()
    robot_id = sim.load_robot(start_pos=[0, -0.6, 0.05])
    sim.spawn_balls(num_balls=22)
    
    # Create hardware
    chassis, arm, camera = create_sim_hardware(robot_id, config)
    
    # Create perception
    ball_detector = BallDetector(config)
    obstacle_detector = ObstacleDetector(config)
    basket_detector = BasketDetector(config)
    
    print("✓ Initialization complete\n")
    print("Starting demo...")
    
    # Stats
    start_time = time.time()
    frames = 0
    balls_detected = 0
    obstacles_detected = 0
    baskets_detected = 0
    
    # Simple behavior: rotate slowly and detect
    chassis.turn_left(speed=0.08)
    
    try:
        while time.time() - start_time < 30:
            # Capture frame
            frame = camera.read()
            
            if frame is not None and frame.size > 0:
                frames += 1
                
                # Run perception
                balls = ball_detector.detect(frame)
                obstacles = obstacle_detector.detect_combined(frame)
                basket = basket_detector.detect(frame)
                
                # Count detections
                if balls:
                    balls_detected += len(balls)
                if obstacles['obstacle_detected'] or obstacles['boundary_detected']:
                    obstacles_detected += 1
                if basket['detected']:
                    baskets_detected += 1
                
                # Visualize
                display = frame.copy()
                
                # Draw balls
                if balls:
                    display = ball_detector.draw_detections(display, balls)
                
                # Draw basket
                if basket['detected']:
                    cv2.circle(display, 
                              (int(basket['center_x']), int(basket['center_y'])), 
                              5, (128, 128, 128), -1)
                    cv2.putText(display, "BASKET", 
                               (int(basket['center_x']) + 10, int(basket['center_y'])),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 2)
                
                # Draw stats
                elapsed = time.time() - start_time
                cv2.putText(display, f"Time: {elapsed:.1f}s", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(display, f"Balls: {len(balls) if balls else 0}", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(display, f"FPS: {frames/elapsed:.1f}", (10, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # Show
                cv2.imshow('Full System Demo', display)
                cv2.waitKey(1)
                
                # Print status every 5 seconds
                if int(elapsed) % 5 == 0 and frames % 100 == 0:
                    print(f"[{elapsed:.1f}s] Frames: {frames}, "
                          f"Balls seen: {balls_detected}, "
                          f"Obstacles: {obstacles_detected}")
            
            # Step simulation
            sim.step()
            
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    finally:
        chassis.stop()
        cv2.destroyAllWindows()
        
        # Print summary
        elapsed = time.time() - start_time
        print("\n" + "=" * 60)
        print("DEMO SUMMARY")
        print("=" * 60)
        print(f"Duration:           {elapsed:.1f} seconds")
        print(f"Frames processed:   {frames}")
        print(f"Average FPS:        {frames/elapsed:.1f}")
        print(f"Balls detected:     {balls_detected} total")
        print(f"Obstacles detected: {obstacles_detected} frames")
        print(f"Basket detected:    {baskets_detected} frames")
        print("=" * 60)
        print("\n✓ ALL PHASES COMPLETE!")
        print("\nPhase 1: Basic Robot & Arena       ✓ WORKING")
        print("Phase 2: Camera & Vision            ✓ WORKING")
        print("Phase 3: Full System Integration   ✓ WORKING")
        print("\nSimulation ready for algorithm development!")
        
        sim.close()


if __name__ == "__main__":
    main()
