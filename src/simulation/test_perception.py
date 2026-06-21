"""
Test Perception - Phase 2 Validation
Tests camera rendering and perception pipeline with synthetic images.

Usage:
    python3 src/simulation/test_perception.py [--headless]
"""

import argparse
import sys
import os
import time
import cv2
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.simulation.sim_core import SimulationCore
from src.simulation.sim_hardware import create_sim_hardware
from src.perception.ball_detector import BallDetector
from src.perception.obstacle_detector import ObstacleDetector
from src.perception.basket_detector import BasketDetector
from src.utils import load_config


def test_camera_rendering(camera, sim, duration=3.0, show_viz=True):
    """Test camera image capture."""
    print("\n=== Test 1: Camera Rendering ===")
    
    frames_captured = 0
    start_time = time.time()
    
    while time.time() - start_time < duration:
        frame = camera.read()
        
        if frame is not None and frame.size > 0:
            frames_captured += 1
            
            if show_viz and frames_captured % 30 == 0:
                print(f"  Captured {frames_captured} frames, shape: {frame.shape}")
                cv2.imshow('Camera View', frame)
                cv2.waitKey(1)
        
        sim.step()
    
    if show_viz:
        cv2.destroyAllWindows()
    
    fps = frames_captured / duration
    print(f"Camera rendering test complete")
    print(f"  Frames captured: {frames_captured}")
    print(f"  Average FPS: {fps:.1f}")
    
    assert frames_captured > 0, "No frames captured"
    w, h = camera.get_frame_size()
    assert frame is not None and frame.shape == (h, w, 3), f"Frame shape {frame.shape} != ({h}, {w}, 3)"
    return True


def test_ball_detection(camera, sim, config, duration=5.0, show_viz=True):
    """Test ball detection on synthetic images."""
    print("\n=== Test 2: Ball Detection ===")
    
    detector = BallDetector(config)
    detections_count = 0
    frames_tested = 0
    
    start_time = time.time()
    
    while time.time() - start_time < duration:
        frame = camera.read()
        
        if frame is not None and frame.size > 0:
            frames_tested += 1
            
            detections = detector.detect(frame)
            
            if detections:
                detections_count += len(detections)
                
                if show_viz and frames_tested % 10 == 0:
                    debug_frame = detector.draw_detections(frame, detections)
                    print(f"  Frame {frames_tested}: Found {len(detections)} balls")
                    cv2.imshow('Ball Detection', debug_frame)
                    cv2.waitKey(1)
        
        sim.step()
    
    if show_viz:
        cv2.destroyAllWindows()
    
    print(f"Ball detection test complete")
    print(f"  Frames tested: {frames_tested}")
    print(f"  Total detections: {detections_count}")
    
    assert frames_tested > 0, "No frames tested"
    assert isinstance(detections, list), "detect() should return a list"
    return detections_count > 0


def test_obstacle_detection(camera, sim, config, duration=3.0, show_viz=True):
    """Test obstacle detection (yellow tape)."""
    print("\n=== Test 3: Obstacle Detection ===")
    
    detector = ObstacleDetector(config)
    obstacle_detected_count = 0
    frames_tested = 0
    
    start_time = time.time()
    
    while time.time() - start_time < duration:
        frame = camera.read()
        
        if frame is not None and frame.size > 0:
            frames_tested += 1
            
            result = detector.detect_combined(frame)
            
            assert isinstance(result, dict), "detect_combined() should return a dict"
            assert 'obstacle_detected' in result, "Missing 'obstacle_detected' key"
            assert 'boundary_detected' in result, "Missing 'boundary_detected' key"
            
            if result['obstacle_detected'] or result['boundary_detected']:
                obstacle_detected_count += 1
                
                if frames_tested % 10 == 0:
                    print(f"  Frame {frames_tested}: Obstacle={result['obstacle_detected']}, "
                          f"Boundary={result['boundary_detected']}")
        
        sim.step()
    
    print(f"Obstacle detection test complete")
    print(f"  Frames tested: {frames_tested}")
    print(f"  Obstacles detected: {obstacle_detected_count}")
    
    assert frames_tested > 0, "No frames tested"
    return True


def test_basket_detection(camera, sim, config, duration=3.0, show_viz=True):
    """Test basket detection."""
    print("\n=== Test 4: Basket Detection ===")
    
    detector = BasketDetector(config)
    basket_detected_count = 0
    frames_tested = 0
    
    start_time = time.time()
    
    while time.time() - start_time < duration:
        frame = camera.read()
        
        if frame is not None and frame.size > 0:
            frames_tested += 1
            
            result = detector.detect(frame)
            
            assert isinstance(result, dict), "detect() should return a dict"
            assert 'detected' in result, "Missing 'detected' key"
            
            if result['detected']:
                basket_detected_count += 1
                
                if frames_tested % 10 == 0:
                    print(f"  Frame {frames_tested}: Basket at angle={result.get('angle', 0):.1f}, "
                          f"distance={result.get('distance_px', 0):.0f}px")
        
        sim.step()
    
    print(f"Basket detection test complete")
    print(f"  Frames tested: {frames_tested}")
    print(f"  Basket detected: {basket_detected_count} times")
    
    assert frames_tested > 0, "No frames tested"
    return basket_detected_count > 0


def test_live_visualization(camera, chassis, sim, config, duration=10.0, show_viz=True):
    """Live visualization with all detections."""
    print("\n=== Test 5: Live Visualization ===")
    if not show_viz:
        print("  (skipped in headless mode)")
        return True
    
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
            
            balls = ball_detector.detect(frame)
            obstacles = obstacle_detector.detect_combined(frame)
            basket = basket_detector.detect(frame)
            
            display_frame = frame.copy()
            
            if balls:
                display_frame = ball_detector.draw_detections(display_frame, balls)
            
            if basket['detected']:
                cv2.circle(display_frame, 
                          (int(basket['center_x']), int(basket['center_y'])), 
                          5, (128, 128, 128), -1)
                cv2.putText(display_frame, "BASKET", 
                           (int(basket['center_x']) + 10, int(basket['center_y'])),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 2)
            
            if obstacles['obstacle_detected']:
                cv2.putText(display_frame, "OBSTACLE!", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            if obstacles['boundary_detected']:
                cv2.putText(display_frame, "BOUNDARY!", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            cv2.imshow('Live Perception', display_frame)
            cv2.waitKey(1)
        
        sim.step()
    
    chassis.stop()
    cv2.destroyAllWindows()
    
    print(f"Live visualization complete")
    print(f"  Total frames: {frame_count}")
    return True


def main(headless=False):
    """Run all perception tests."""
    print("=" * 60)
    print("PHASE 2 VALIDATION: Camera & Vision")
    print("=" * 60)
    
    config = load_config()
    config.setdefault('simulation', {})
    if headless:
        config['simulation'] = {**config['simulation'], 'renderer': 'tiny'}
    
    show_viz = not headless
    
    print("\nInitializing simulation...")
    sim = SimulationCore(gui=not headless, real_time=not headless, config=config)
    sim.initialize()
    sim.load_arena()
    robot_id = sim.load_robot(start_pos=[0.5, 0.5, 0.15])
    sim.spawn_balls(num_balls=5)
    
    print("Creating simulated hardware...")
    chassis, arm, camera = create_sim_hardware(robot_id, config, sim=sim)
    
    passed = 0
    failed = 0
    tests = [
        ("Camera Rendering", lambda: test_camera_rendering(camera, sim, show_viz=show_viz)),
        ("Ball Detection", lambda: test_ball_detection(camera, sim, config, show_viz=show_viz)),
        ("Obstacle Detection", lambda: test_obstacle_detection(camera, sim, config, show_viz=show_viz)),
        ("Basket Detection", lambda: test_basket_detection(camera, sim, config, show_viz=show_viz)),
        ("Live Visualization", lambda: test_live_visualization(camera, chassis, sim, config, show_viz=show_viz)),
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
            print("\nPhase 2 validation complete!")
            print("Perception pipeline working in simulation.")
        
        if not headless:
            print("\nPress Ctrl+C to exit...")
            while True:
                sim.step()
        
        return 0 if failed == 0 else 1
    
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        return 1
    finally:
        if not headless:
            cv2.destroyAllWindows()
        sim.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Phase 2 perception validation')
    parser.add_argument('--headless', action='store_true',
                        help='Run without GUI (for CI / automated testing)')
    args = parser.parse_args()
    sys.exit(main(headless=args.headless))
