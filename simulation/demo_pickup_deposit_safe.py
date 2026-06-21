"""
Safe Pickup and Deposit Demo with Logging and Stability Checks
"""

import sys
import os
import time
import yaml
import cv2
import numpy as np
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation.sim_core import SimulationCore
from simulation.sim_hardware import create_sim_hardware
from perception.ball_detector import BallDetector
from perception.basket_detector import BasketDetector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('simulation_demo.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_config():
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config.yaml'
    )
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def check_robot_stability(sim, robot_id):
    """Check if robot is upright and stable"""
    state = sim.get_robot_state()
    pos = state['position']
    orn = state['orientation']  # [roll, pitch, yaw]
    
    # Check if robot is on the ground (not flying or fallen through)
    if pos[2] < 0.01 or pos[2] > 0.3:
        logger.error(f"Robot height abnormal: {pos[2]:.3f}m")
        return False, "height"
    
    # Check roll and pitch (should be close to 0)
    roll, pitch, yaw = orn
    max_tilt = 0.5  # ~30 degrees
    
    if abs(roll) > max_tilt:
        logger.error(f"Robot rolled over! Roll: {np.rad2deg(roll):.1f}°")
        return False, "roll"
    
    if abs(pitch) > max_tilt:
        logger.error(f"Robot pitched over! Pitch: {np.rad2deg(pitch):.1f}°")
        return False, "pitch"
    
    return True, "stable"


def safe_arm_move(arm, sim, target_angles, duration=2.0, check_interval=0.1):
    """Move arm with stability checking"""
    logger.info(f"Moving arm to: {target_angles}")
    
    arm.set_joint_angles(target_angles)
    
    start_time = time.time()
    last_check = start_time
    
    while time.time() - start_time < duration:
        sim.step()
        
        # Check stability periodically
        if time.time() - last_check > check_interval:
            stable, reason = check_robot_stability(sim, sim.robot_id)
            if not stable:
                logger.error(f"Robot became unstable during arm movement: {reason}")
                # Emergency: return arm to safe position
                arm.set_joint_angles([0, 0, 0, 0])
                for _ in range(60):
                    sim.step()
                return False
            last_check = time.time()
    
    logger.info("Arm movement complete and stable")
    return True


def find_closest_ball(camera, ball_detector, sim, max_attempts=100):
    """Rotate to find the closest ball"""
    logger.info("Searching for balls...")
    
    best_ball = None
    best_distance = float('inf')
    
    for i in range(max_attempts):
        frame = camera.read()
        if frame is not None and frame.size > 0:
            balls = ball_detector.detect(frame)
            
            if balls:
                for ball in balls:
                    color, (cx, cy), distance, area = ball
                    if distance < best_distance:
                        best_distance = distance
                        best_ball = ball
                
                if best_ball:
                    logger.info(f"Found {best_ball[0]} ball at distance {best_ball[2]:.1f}cm")
                    return best_ball
        
        # Check stability while searching
        if i % 20 == 0:
            stable, reason = check_robot_stability(sim, sim.robot_id)
            if not stable:
                logger.error(f"Robot unstable during search: {reason}")
                return None
        
        sim.step()
    
    logger.warning("No balls found")
    return None


def approach_ball(chassis, camera, ball_detector, sim, target_ball, duration=10.0):
    """Approach the target ball with stability monitoring"""
    logger.info(f"Approaching {target_ball[0]} ball...")
    
    start_time = time.time()
    frame_width = 320
    center_x = frame_width / 2
    
    while time.time() - start_time < duration:
        frame = camera.read()
        
        if frame is not None and frame.size > 0:
            balls = ball_detector.detect(frame)
            
            target_color = target_ball[0]
            current_ball = None
            
            for ball in balls:
                if ball[0] == target_color:
                    current_ball = ball
                    break
            
            if current_ball:
                color, (cx, cy), distance, area = current_ball
                
                error = cx - center_x
                
                # Reduced speeds for stability
                turn_speed = np.clip(error / frame_width * 0.10, -0.10, 0.10)
                
                if abs(error) < 30 and area > 800:
                    logger.info("Ball reached!")
                    chassis.stop()
                    return True
                
                # Slower forward speed for stability
                forward_speed = 0.08
                chassis.set_motors(
                    forward_speed - turn_speed,
                    forward_speed + turn_speed
                )
            else:
                chassis.stop()
                logger.warning("Lost sight of ball")
                return False
        
        # Check stability every 50 steps
        if int((time.time() - start_time) * 240) % 50 == 0:
            stable, reason = check_robot_stability(sim, sim.robot_id)
            if not stable:
                chassis.stop()
                logger.error(f"Robot unstable during approach: {reason}")
                return False
        
        sim.step()
    
    chassis.stop()
    logger.warning("Approach timeout")
    return False


def pickup_ball(arm, chassis, sim):
    """
    Execute pickup sequence with hook claw:
    1. Open claw
    2. Lower arm close to ground
    3. Close claw to grip ball
    4. Lift ball from ground
    """
    logger.info("Executing pickup sequence with hook claw...")
    
    chassis.stop()
    
    # Wait for robot to settle
    logger.info("Waiting for robot to settle...")
    for _ in range(60):
        sim.step()
    
    # Check initial stability
    stable, reason = check_robot_stability(sim, sim.robot_id)
    if not stable:
        logger.error(f"Robot unstable before pickup: {reason}")
        return False
    
    # Step 1: Open claw
    logger.info("Step 1: Opening claw...")
    arm.open_claw()
    for _ in range(30):
        sim.step()
    
    # Step 2: Lower arm close to ground (wrist angled down)
    logger.info("Step 2: Lowering arm to ground...")
    if not safe_arm_move(arm, sim, [0, -35, -55, -25], duration=1.5):
        return False
    
    # Step 3: Close claw to grip ball
    logger.info("Step 3: Closing claw to grip ball...")
    arm.close_claw()
    for _ in range(60):
        sim.step()
    
    # Step 4: Lift ball from ground
    logger.info("Step 4: Lifting ball...")
    if not safe_arm_move(arm, sim, [0, 15, 25, 50], duration=1.5):
        return False
    
    logger.info("✓ Pickup complete! Ball secured in claw.")
    return True


def find_basket(chassis, camera, basket_detector, sim, max_duration=20.0):
    """Rotate 360° to find the basket with stability checks"""
    logger.info("Searching for basket (360° rotation)...")
    
    start_time = time.time()
    rotation_speed = 0.08
    last_log_time = start_time
    
    while time.time() - start_time < max_duration:
        # Continuously command rotation (must be inside loop)
        chassis.turn_left(speed=rotation_speed)
        
        frame = camera.read()
        
        if frame is not None and frame.size > 0:
            basket = basket_detector.detect(frame)
            
            if basket and basket.get('detected', False):
                chassis.stop()
                elapsed = time.time() - start_time
                logger.info(f"✓ Found basket after {elapsed:.1f}s rotation")
                return basket
        
        # Log progress every 2 seconds
        current_time = time.time()
        if current_time - last_log_time >= 2.0:
            elapsed = current_time - start_time
            logger.info(f"Still searching... {elapsed:.0f}s elapsed")
            last_log_time = current_time
        
        # Check stability periodically
        if int((time.time() - start_time) * 240) % 100 == 0:
            stable, reason = check_robot_stability(sim, sim.robot_id)
            if not stable:
                chassis.stop()
                logger.error(f"Robot unstable during basket search: {reason}")
                return None
        
        sim.step()
    
    chassis.stop()
    logger.warning(f"Basket not found after {max_duration:.0f}s search")
    return None


def approach_basket(chassis, camera, basket_detector, sim, duration=10.0):
    """Approach the basket with stability monitoring"""
    logger.info("Approaching basket...")
    
    start_time = time.time()
    frame_width = 320
    center_x = frame_width / 2
    
    while time.time() - start_time < duration:
        frame = camera.read()
        
        if frame is not None and frame.size > 0:
            basket = basket_detector.detect(frame)
            
            if basket and basket.get('detected', False):
                bx = basket.get('center_x', center_x)
                error = bx - center_x
                turn_speed = np.clip(error / frame_width * 0.08, -0.08, 0.08)
                
                distance = basket.get('distance_px', 1000)
                if abs(error) < 40 and distance < 150:
                    logger.info("Basket reached!")
                    chassis.stop()
                    return True
                
                # Very slow approach for stability
                forward_speed = 0.06
                chassis.set_motors(
                    forward_speed - turn_speed,
                    forward_speed + turn_speed
                )
            else:
                chassis.stop()
                logger.warning("Lost sight of basket")
                return False
        
        # Check stability
        if int((time.time() - start_time) * 240) % 50 == 0:
            stable, reason = check_robot_stability(sim, sim.robot_id)
            if not stable:
                chassis.stop()
                logger.error(f"Robot unstable during basket approach: {reason}")
                return False
        
        sim.step()
    
    chassis.stop()
    logger.warning("Basket approach timeout")
    return False


def deposit_ball(arm, chassis, sim):
    """
    Execute deposit sequence:
    1. Move to basket center
    2. Raise arm over basket
    3. Open claw to drop ball
    4. Return to home
    """
    logger.info("Depositing ball into basket...")
    
    chassis.stop()
    
    # Wait for settling
    logger.info("Waiting for robot to settle...")
    for _ in range(60):
        sim.step()
    
    # Check stability
    stable, reason = check_robot_stability(sim, sim.robot_id)
    if not stable:
        logger.error(f"Robot unstable before deposit: {reason}")
        return False
    
    # Step 1: Raise arm over basket
    logger.info("Step 1: Raising arm over basket...")
    if not safe_arm_move(arm, sim, [0, 35, 35, 35], duration=1.5):
        return False
    
    # Step 2: Open claw to drop ball
    logger.info("Step 2: Opening claw to drop ball...")
    arm.open_claw()
    for _ in range(60):
        sim.step()
    
    # Step 3: Return to home position
    logger.info("Step 3: Returning to home...")
    if not safe_arm_move(arm, sim, [0, 0, 0, 0], duration=2.0):
        return False
    
    logger.info("✓ Deposit complete! Ball dropped in basket.")
    return True


def main():
    logger.info("="*60)
    logger.info("SAFE PICKUP & DEPOSIT DEMONSTRATION")
    logger.info("="*60)
    
    # Load config
    config = load_config()
    
    # Initialize simulation
    logger.info("Initializing simulation...")
    sim = SimulationCore(gui=True, real_time=True)
    sim.initialize()
    sim.load_arena()
    
    # Start robot at top-right corner (0, 0) - 0.15m height for 25cm tall chassis
    robot_id = sim.load_robot(start_pos=[0, 0, 0.15])
    sim.spawn_balls(num_balls=22)
    
    # Create hardware
    chassis, arm, camera = create_sim_hardware(robot_id, config)
    
    # Create perception
    ball_detector = BallDetector(config)
    basket_detector = BasketDetector(config)
    
    logger.info("Initialization complete")
    
    # Let robot settle
    logger.info("Letting robot settle...")
    for _ in range(120):
        sim.step()
    
    # Initial stability check
    stable, reason = check_robot_stability(sim, robot_id)
    if not stable:
        logger.error(f"Robot unstable at start: {reason}")
        sim.close()
        return
    
    logger.info("Robot stable, starting demo...")
    
    try:
        # State 1: Find ball
        logger.info("\n" + "="*60)
        logger.info("STATE: SEARCHING FOR BALL")
        logger.info("="*60)
        
        chassis.turn_left(speed=0.08)
        target_ball = find_closest_ball(camera, ball_detector, sim, max_attempts=200)
        chassis.stop()
        
        if not target_ball:
            logger.error("No balls found!")
            return
        
        # State 2: Approach ball
        logger.info("\n" + "="*60)
        logger.info(f"STATE: APPROACHING {target_ball[0].upper()} BALL")
        logger.info("="*60)
        
        success = approach_ball(chassis, camera, ball_detector, sim, target_ball)
        
        if not success:
            logger.error("Failed to approach ball!")
            return
        
        # State 3: Pickup
        logger.info("\n" + "="*60)
        logger.info("STATE: PICKING UP BALL")
        logger.info("="*60)
        
        success = pickup_ball(arm, chassis, sim)
        
        if not success:
            logger.error("Failed to pickup ball!")
            return
        
        # State 4: Find basket
        logger.info("\n" + "="*60)
        logger.info("STATE: SEARCHING FOR BASKET")
        logger.info("="*60)
        
        basket = find_basket(chassis, camera, basket_detector, sim)
        
        if not basket:
            logger.error("Basket not found!")
            return
        
        # State 5: Approach basket
        logger.info("\n" + "="*60)
        logger.info("STATE: APPROACHING BASKET")
        logger.info("="*60)
        
        success = approach_basket(chassis, camera, basket_detector, sim)
        
        if not success:
            logger.error("Failed to approach basket!")
            return
        
        # State 6: Deposit
        logger.info("\n" + "="*60)
        logger.info("STATE: DEPOSITING BALL")
        logger.info("="*60)
        
        success = deposit_ball(arm, chassis, sim)
        
        if not success:
            logger.error("Failed to deposit ball!")
            return
        
        # Success!
        logger.info("\n" + "="*60)
        logger.info("🎉 MISSION COMPLETE! 🎉")
        logger.info("="*60)
        logger.info("Ball successfully picked up and deposited in basket!")
        logger.info("Press Ctrl+C to exit...")
        
        # Keep simulation running
        while True:
            stable, reason = check_robot_stability(sim, robot_id)
            if not stable:
                logger.error(f"Robot became unstable: {reason}")
                break
            sim.step()
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        logger.info("Demo stopped by user")
    except Exception as e:
        logger.error(f"Error during demo: {e}", exc_info=True)
    finally:
        chassis.stop()
        cv2.destroyAllWindows()
        sim.close()
        logger.info("Demo ended")


if __name__ == "__main__":
    main()
