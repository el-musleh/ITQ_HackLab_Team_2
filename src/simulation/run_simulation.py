"""
Full Autonomous Simulation - Phase 3
Runs complete state machine with perception and navigation
"""

import sys
import os
import time
import yaml
import cv2
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.simulation.sim_core import SimulationCore
from src.simulation.sim_hardware import create_sim_hardware
from src.perception.ball_detector import BallDetector
from src.perception.obstacle_detector import ObstacleDetector
from src.perception.basket_detector import BasketDetector
from src.control.state_machine import StateMachine
from src.control.navigator import Navigator


def load_config():
    """Load configuration from config.yaml"""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config.yaml'
    )
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


class SimulationRunner:
    """Manages full autonomous simulation run"""
    
    def __init__(self, config, gui=True, real_time=True, max_duration=300):
        """
        Initialize simulation runner
        
        Args:
            config: Configuration dictionary
            gui: Show PyBullet GUI
            real_time: Run at real-time speed
            max_duration: Maximum run duration in seconds (default 5 minutes)
        """
        self.config = config
        self.max_duration = max_duration
        
        # Initialize simulation
        self.sim = SimulationCore(gui=gui, real_time=real_time)
        self.sim.initialize()
        self.sim.load_arena()
        robot_id = self.sim.load_robot(start_pos=[0, -0.6, 0.05])
        self.sim.spawn_balls(num_balls=22)
        
        # Create hardware
        self.chassis, self.arm, self.camera = create_sim_hardware(robot_id, config)
        
        # Create perception modules
        self.ball_detector = BallDetector(config)
        self.obstacle_detector = ObstacleDetector(config)
        self.basket_detector = BasketDetector(config)
        
        # Create control modules
        self.state_machine = StateMachine(config)
        self.navigator = Navigator(self.chassis, config)
        
        # Telemetry
        self.start_time = None
        self.balls_collected = 0
        self.collisions = 0
        self.frames_processed = 0
        
    def run_perception(self, frame):
        """
        Run all perception modules
        
        Returns:
            Dictionary with detection results
        """
        return {
            'balls': self.ball_detector.detect(frame),
            'obstacles': self.obstacle_detector.detect_combined(frame),
            'basket': self.basket_detector.detect(frame),
            'frame': frame
        }
    
    def execute_action(self, action):
        """Execute action from state machine"""
        action_type = action.get('type', 'stop')
        
        if action_type == 'move':
            # Direct motor control
            left = action.get('left', 0)
            right = action.get('right', 0)
            self.chassis.set_motors(left, right)
            
        elif action_type == 'rotate':
            # Rotate in place
            speed = action.get('speed', 0.1)
            direction = action.get('direction', 'left')
            if direction == 'left':
                self.chassis.turn_left(speed)
            else:
                self.chassis.turn_right(speed)
                
        elif action_type == 'approach':
            # Use navigator to approach target
            target = action.get('target')
            if target:
                nav_action = self.navigator.approach_target(target)
                self.chassis.set_motors(nav_action['left'], nav_action['right'])
                
        elif action_type == 'pickup':
            # Execute pickup sequence
            self.chassis.stop()
            self.arm.pickup_sequence()
            self.balls_collected += 1
            
        elif action_type == 'deposit':
            # Execute deposit sequence
            self.chassis.stop()
            self.arm.deposit_sequence()
            
        elif action_type == 'avoid':
            # Avoidance maneuver
            direction = action.get('direction', 'reverse')
            if direction == 'reverse':
                self.chassis.backward(speed=0.15)
            elif direction == 'left':
                self.chassis.turn_left(speed=0.15)
            elif direction == 'right':
                self.chassis.turn_right(speed=0.15)
                
        else:  # stop
            self.chassis.stop()
    
    def visualize(self, perception_data, state):
        """Create debug visualization"""
        frame = perception_data['frame'].copy()
        
        # Draw ball detections
        balls = perception_data['balls']
        if balls:
            frame = self.ball_detector.draw_detections(frame, balls)
        
        # Draw basket
        basket = perception_data['basket']
        if basket['detected']:
            cv2.circle(frame, 
                      (int(basket['center_x']), int(basket['center_y'])), 
                      5, (128, 128, 128), -1)
        
        # Draw state info
        cv2.putText(frame, f"State: {state}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Balls: {self.balls_collected}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        elapsed = time.time() - self.start_time
        cv2.putText(frame, f"Time: {elapsed:.1f}s", (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Draw obstacle warnings
        obstacles = perception_data['obstacles']
        if obstacles['obstacle_detected']:
            cv2.putText(frame, "OBSTACLE!", (10, 120),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        if obstacles['boundary_detected']:
            cv2.putText(frame, "BOUNDARY!", (10, 150),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        return frame
    
    def run(self, show_visualization=True):
        """
        Run autonomous simulation
        
        Args:
            show_visualization: Show camera feed with detections
        """
        print("\n" + "=" * 60)
        print("AUTONOMOUS SIMULATION RUN")
        print("=" * 60)
        print(f"Max duration: {self.max_duration} seconds")
        print("Starting in 3 seconds...")
        
        # Countdown
        for i in range(3, 0, -1):
            print(f"  {i}...")
            time.sleep(1)
        
        print("\n🚀 STARTING AUTONOMOUS RUN!\n")
        
        self.start_time = time.time()
        last_print = time.time()
        
        try:
            while True:
                # Check time limit
                elapsed = time.time() - self.start_time
                if elapsed > self.max_duration:
                    print(f"\n⏱ Time limit reached ({self.max_duration}s)")
                    break
                
                # Capture frame
                frame = self.camera.read()
                
                if frame is None or frame.size == 0:
                    self.sim.step()
                    continue
                
                self.frames_processed += 1
                
                # Run perception
                perception_data = self.run_perception(frame)
                
                # Get robot state
                robot_state = self.sim.get_robot_state()
                
                # Update state machine
                state_data = {
                    'balls': perception_data['balls'],
                    'obstacles': perception_data['obstacles'],
                    'basket': perception_data['basket'],
                    'position': robot_state['position'],
                    'orientation': robot_state['orientation']
                }
                
                action = self.state_machine.update(state_data)
                
                # Execute action
                self.execute_action(action)
                
                # Check collisions
                if self.sim.check_collision(self.sim.robot_id, self.sim.arena_id):
                    # Only count as collision if moving
                    if abs(self.chassis.left_speed) > 0.01 or abs(self.chassis.right_speed) > 0.01:
                        self.collisions += 1
                
                # Visualization
                if show_visualization:
                    debug_frame = self.visualize(perception_data, self.state_machine.current_state)
                    cv2.imshow('Autonomous Run', debug_frame)
                    cv2.waitKey(1)
                
                # Print status every 5 seconds
                if time.time() - last_print > 5.0:
                    print(f"[{elapsed:.1f}s] State: {self.state_machine.current_state}, "
                          f"Balls: {self.balls_collected}, Frames: {self.frames_processed}")
                    last_print = time.time()
                
                # Step simulation
                self.sim.step()
                
        except KeyboardInterrupt:
            print("\n\n⏹ Stopped by user")
        
        finally:
            self.chassis.stop()
            cv2.destroyAllWindows()
            self.print_summary()
    
    def print_summary(self):
        """Print run summary"""
        elapsed = time.time() - self.start_time
        
        print("\n" + "=" * 60)
        print("RUN SUMMARY")
        print("=" * 60)
        print(f"Duration:          {elapsed:.1f} seconds")
        print(f"Balls Collected:   {self.balls_collected}")
        print(f"Collisions:        {self.collisions}")
        print(f"Frames Processed:  {self.frames_processed}")
        print(f"Avg FPS:           {self.frames_processed/elapsed:.1f}")
        print(f"Final State:       {self.state_machine.current_state}")
        print("=" * 60)
        
        # Performance rating
        if self.balls_collected >= 10 and self.collisions == 0:
            print("🏆 EXCELLENT! Ready for competition!")
        elif self.balls_collected >= 5 and self.collisions <= 1:
            print("✓ GOOD! System working well.")
        elif self.balls_collected >= 1:
            print("⚠ NEEDS TUNING. Basic functionality works.")
        else:
            print("❌ NEEDS DEBUGGING. Check perception and control.")
    
    def close(self):
        """Cleanup"""
        self.sim.close()


def main():
    """Main entry point"""
    print("=" * 60)
    print("PHASE 3: Full Autonomous Simulation")
    print("=" * 60)
    
    # Load config
    config = load_config()
    
    # Create runner
    runner = SimulationRunner(
        config,
        gui=True,
        real_time=True,
        max_duration=300  # 5 minutes
    )
    
    # Run simulation
    try:
        runner.run(show_visualization=True)
    finally:
        runner.close()


if __name__ == "__main__":
    main()
