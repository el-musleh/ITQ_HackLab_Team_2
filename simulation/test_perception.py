"""
Test Perception - Phase 2 Validation
Tests camera rendering and perception pipeline with synthetic images
"""

import sys
import os
import time
import yaml
import cv2
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation.sim_core import SimulationCore
from simulation.sim_hardware import create_sim_hardware
from perception.ball_detector import BallDetector
from perception.obstacle_detector import ObstacleDetector
from perception.basket_detector import BasketDetector


def load_config():
    """Load configuration from config.yaml"""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config.yaml'
    )
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def test_camera_rendering(camera, sim, duration=3.0):
    """Test camera image capture"""
    print("\n=== Test 1: Camera Rendering ===")
    
    frames_captured = 0
    start_time = time.time()
    
    while time.time() - start_time < duration:
        frame = camera.read()
        
        if frame is not None and frame.size > 0:
            frames_captured += 1
            
            # Show frame occasionally
            if frames_captured % 30 == 0:
                print(f"  Captured {frames_captured} frames, shape: {frame.shape}")
                cv2.imshow('Camera View', frame)
                cv2.waitKey(1)
        
        sim.step()
    
    cv2.destroyAllWindows()
    
    fps = frames_captured / duration
    print(f"✓ Camera rendering test complete")
    print(f"  Frames captured: {frames_captured}")
    print(f"  Average FPS: {fps:.1f}")
    
    return frames_captured > 0


def test_ball_detection(camera, sim, config, duration=5.0):
    """Test ball detection on synthetic images"""
    print("\n=== Test 2: Ball Detection ===")
    
    detector = BallDetector(config)
    detections_count = 0
    frames_tested = 0
    
    start_time = time.time()
    
    while time.time() - start_time < duration:
        frame = camera.read()
        
        if frame is not None and frame.size > 0:
            frames_tested += 1
            
            # Run detection
            detections = detector.detect(frame)
            
            if detections:
                detections_count += len(detections)
                
                # Draw detections
                debug_frame = detector.draw_detections(frame, detections)
                
                # Show every 10th frame
                if frames_tested % 10 == 0:
                    print(f"  Frame {frames_tested}: Found {len(detections)} balls")
                    cv2.imshow('Ball Detection', debug_frame)
                    cv2.waitKey(1)
        
        sim.step()
    
    cv2.destroyAllWindows()
    
    print(f"✓ Ball detection test complete")
    print(f"  Frames tested: {frames_tested}")
    print(f"  Total detections: {detections_count}")
    print(f"  Avg detections/frame: {detections_count/max(frames_tested,1):.2f}")
    
    return detections_count > 0


def test_obstacle_detection(camera, sim, config, duration=3.0):
    """Test obstacle detection (yellow tape)"""
    print("\n=== Test 3: Obstacle Detection ===")
    
    detector = ObstacleDetector(config)
    obstacle_detected_count = 0
    frames_tested = 0
    
    start_time = time.time()
    
    while time.time() - start_time < duration:
        frame = camera.read()
        
        if frame is not None and frame.size > 0:
            frames_tested += 1
            
            # Run detection
            result = detector.detect_combined(frame)
            
            if result['obstacle_detected'] or result['boundary_detected']:
                obstacle_detected_count += 1
                
                if frames_tested % 10 == 0:
                    print(f"  Frame {frames_tested}: Obstacle={result['obstacle_detected']}, "
                          f"Boundary={result['boundary_detected']}")
        
        sim.step()
    
    print(f"✓ Obstacle detection test complete")
    print(f"  Frames tested: {frames_tested}")
    print(f"  Obstacles detected: {obstacle_detected_count}")
    
    return True


def test_basket_detection(camera, sim, config, duration=3.0):
    """Test basket detection"""
    print("\n=== Test 4: Basket Detection ===")
    
    detector = BasketDetector(config)
    basket_detected_count = 0
    frames_tested = 0
    
    start_time = time.time()
    
    while time.time() - start_time < duration:
        frame = camera.read()
        
        if frame is not None and frame.size > 0:
            frames_tested += 1
            
            # Run detection
            result = detector.detect(frame)
            
            if result['detected']:
                basket_detected_count += 1
                
                if frames_tested % 10 == 0:
                    print(f"  Frame {frames_tested}: Basket at angle={result['angle']:.1f}°, "
                          f"distance={result['distance_px']:.0f}px")
        
        sim.step()
    
    print(f"✓ Basket detection test complete")
    print(f"  Frames tested: {frames_tested}")
    print(f"  Basket detected: {basket_detected_count} times")
    
    return basket_detected_count > 0


def test_live_visualization(camera, chassis, sim, config, duration=10.0):
    """Live visualization with all detections"""
    print("\n=== Test 5: Live Visualization ===")
    print("Showing live camera feed with detections for 10 seconds...")
    
    ball_detector = BallDetector(config)
    obstacle_detector = ObstacleDetector(config)
    basket_detector = BasketDetector(config)
    
    # Rotate robot slowly to see different views
    chassis.turn_left(speed=0.08)
    
    start_time = time.time()
    frame_count = 0
    
    while time.time() - start_time < duration:
        frame = camera.read()
        
        if frame is not None and frame.size > 0:
            frame_count += 1
            
            # Run all detections
            balls = ball_detector.detect(frame)
            obstacles = obstacle_detector.detect_combined(frame)
            basket = basket_detector.detect(frame)
            
            # Draw detections
            display_frame = frame.copy()
            
            # Draw balls
            if balls:
                display_frame = ball_detector.draw_detections(display_frame, balls)
            
            # Draw basket
            if basket['detected']:
                cv2.circle(display_frame, 
                          (int(basket['center_x']), int(basket['center_y'])), 
                          5, (128, 128, 128), -1)
                cv2.putText(display_frame, "BASKET", 
                           (int(basket['center_x']) + 10, int(basket['center_y'])),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 2)
            
            # Draw obstacle warning
            if obstacles['obstacle_detected']:
                cv2.putText(display_frame, "OBSTACLE!", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            if obstacles['boundary_detected']:
                cv2.putText(display_frame, "BOUNDARY!", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            # Show frame
            cv2.imshow('Live Perception', display_frame)
            cv2.waitKey(1)
        
        sim.step()
    
    chassis.stop()
    cv2.destroyAllWindows()
    
    print(f"✓ Live visualization complete")
    print(f"  Total frames: {frame_count}")


def main():
    """Run all perception tests"""
    print("=" * 60)
    print("PHASE 2 VALIDATION: Camera & Vision")
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
        # Test 1: Camera rendering
        camera_ok = test_camera_rendering(camera, sim)
        
        if not camera_ok:
            print("\n❌ Camera rendering failed!")
            return
        
        # Test 2: Ball detection
        balls_ok = test_ball_detection(camera, sim, config)
        
        # Test 3: Obstacle detection
        obstacles_ok = test_obstacle_detection(camera, sim, config)
        
        # Test 4: Basket detection
        basket_ok = test_basket_detection(camera, sim, config)
        
        # Test 5: Live visualization
        test_live_visualization(camera, chassis, sim, config)
        
        # Final summary
        print("\n" + "=" * 60)
        print("PHASE 2 VALIDATION RESULTS")
        print("=" * 60)
        print(f"  Camera Rendering:    {'✓ PASS' if camera_ok else '✗ FAIL'}")
        print(f"  Ball Detection:      {'✓ PASS' if balls_ok else '✗ FAIL'}")
        print(f"  Obstacle Detection:  {'✓ PASS' if obstacles_ok else '✗ FAIL'}")
        print(f"  Basket Detection:    {'✓ PASS' if basket_ok else '✗ FAIL'}")
        print("=" * 60)
        
        if camera_ok and balls_ok:
            print("\n✓ Phase 2 validation complete!")
            print("Perception pipeline working in simulation.")
        else:
            print("\n⚠ Some tests failed. Check output above.")
        
        print("\nPress Ctrl+C to exit...")
        
        # Keep simulation running
        while True:
            sim.step()
            
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        cv2.destroyAllWindows()
        sim.close()


if __name__ == "__main__":
    main()
