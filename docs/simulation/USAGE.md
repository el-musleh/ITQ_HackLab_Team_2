# Simulation Usage Guide

How to use the PyBullet simulation for testing and development.

## Overview

The simulation provides a virtual testing environment that mirrors the real challenge. You can test your algorithms without hardware, then deploy the same code to the Jetson Nano.

## Basic Usage

### Running a Simulation

```bash
# From project root — GUI mode (requires display)
python3 src/simulation/test_basic_motion.py

# Headless mode (no GUI, for CI / automated testing)
python3 src/simulation/test_basic_motion.py --headless

# Perception tests
python3 src/simulation/test_perception.py --headless

# Full autonomous run
python3 src/simulation/run_simulation.py --headless --duration 60 --balls 5
```

### Switching Between Simulation and Hardware

The code uses the same interface for both simulated and real hardware:

**Simulation Mode:**
```python
from src.simulation.sim_core import SimulationCore
from src.simulation.sim_hardware import create_sim_hardware
from src.utils import load_config

# Load config
config = load_config()

# Initialize simulation
sim = SimulationCore(gui=True, real_time=True, config=config)
sim.initialize()
sim.load_arena()
robot_id = sim.load_robot()
sim.spawn_balls()

# Create hardware interfaces (pass sim so arm sequences step physics)
chassis, arm, camera = create_sim_hardware(robot_id, config, sim=sim)

# Use hardware (same API as real hardware)
chassis.forward(speed=0.2)
frame = camera.read()
arm.pickup_sequence()
```

**Hardware Mode:**
```python
from src.hardware.chassis import ChassisController
from src.hardware.arm import ArmController
from src.hardware.camera import CameraController
from src.utils import load_config

# Load config
config = load_config()

# Initialize real hardware
chassis = ChassisController()
arm = ArmController(config)
camera = CameraController()

# Use hardware (same API as simulation)
chassis.forward(speed=0.2)
frame = camera.read()
arm.pickup_sequence()
```

## Control Interface

### Chassis Control

```python
# Basic movements
chassis.forward(speed=0.2)      # Move forward
chassis.backward(speed=0.2)     # Move backward
chassis.turn_left(speed=0.15)   # Turn left
chassis.turn_right(speed=0.15)  # Turn right
chassis.stop()                  # Stop all motors

# Direct motor control
chassis.set_motors(left=0.2, right=0.2)  # Differential drive
```

### Arm Control

```python
# Predefined poses (pass pose lists for hardware compatibility)
arm.move_to_pose(arm.pose_home)      # Home position
arm.move_to_pose(arm.pose_pickup)    # Pickup position
arm.move_to_pose(arm.pose_carry)     # Carry position
arm.move_to_pose(arm.pose_deposit)   # Deposit position

# String names also work in simulation
arm.move_to_pose('home')

# Sequences
arm.pickup_sequence()   # Full pickup: open -> lower -> close -> lift
arm.deposit_sequence()  # Full deposit: position -> open -> home

# Manual control
arm.set_joint_angles([0, -40, -60, 0])  # [base, shoulder, elbow, gripper]
```

### Camera Control

```python
# Capture frame
frame = camera.read()  # Returns BGR image (320x240)

# Pan/tilt (not fully implemented in Phase 1)
camera.set_pan(angle=15)   # Pan angle in degrees
camera.set_tilt(angle=30)  # Tilt angle in degrees
camera.center()            # Center camera
```

## Simulation Control

### Stepping the Simulation

```python
# Manual stepping (for precise control)
for i in range(1000):
    chassis.forward(speed=0.2)
    sim.step()  # Advance physics by 1/240 second

# Real-time mode (automatic stepping)
sim = SimulationCore(gui=True, real_time=True)
# Physics steps automatically match wall-clock time
```

### Getting Robot State

```python
state = sim.get_robot_state()
print(state['position'])     # [x, y, z]
print(state['orientation'])  # [roll, pitch, yaw] in radians
```

### Collision Detection

```python
# Check if robot hit a wall
colliding = sim.check_collision(sim.robot_id, sim.arena_id)
if colliding:
    print("Collision detected!")
    chassis.stop()
```

### Resetting Simulation

```python
# Reset to initial state
sim.reset()
# - Robot returns to start position
# - Balls respawn
# - Joint positions reset
```

## Testing Workflows

### Workflow 1: Test Single Component

```python
# Test just the chassis
sim = SimulationCore(gui=True, real_time=True)
sim.initialize()
sim.load_arena()
robot_id = sim.load_robot()

chassis, _, _ = create_sim_hardware(robot_id, config)

# Test forward movement
chassis.forward(speed=0.2)
for _ in range(480):  # 2 seconds
    sim.step()

chassis.stop()
```

### Workflow 2: Test Perception Pipeline

```python
# Test ball detection (Phase 2)
from src.perception.ball_detector import BallDetector

detector = BallDetector(config)

for i in range(100):
    frame = camera.read()
    detections = detector.detect(frame)
    
    if detections:
        print(f"Found {len(detections)} balls")
    
    sim.step()
```

### Workflow 3: Test State Machine

```python
# Test full autonomous loop (Phase 3)
from src.control.state_machine import StateMachine

state_machine = StateMachine(config)

for i in range(10000):  # Run for ~40 seconds
    # Capture sensor data
    frame = camera.read()
    robot_state = sim.get_robot_state()
    
    # Run perception
    perception_data = {
        'frame': frame,
        'position': robot_state['position']
    }
    
    # Update state machine
    action = state_machine.update(perception_data)
    
    # Execute action
    if action['type'] == 'move':
        chassis.set_motors(action['left'], action['right'])
    elif action['type'] == 'pickup':
        arm.pickup_sequence()
    
    sim.step()
```

## GUI Controls

When running with `gui=True`, the PyBullet window provides:

- **Mouse**: Rotate view (left-click drag)
- **Mouse wheel**: Zoom in/out
- **Ctrl + Mouse**: Pan view
- **R**: Reset camera view
- **G**: Toggle grid
- **W**: Toggle wireframe

## Performance Tips

### Faster Simulation

```python
# Disable real-time for maximum speed
sim = SimulationCore(gui=False, real_time=False)

# Run 10x faster than real-time
for _ in range(2400):  # 10 seconds of simulation
    sim.step()
```

### Headless Mode

```python
# No GUI for automated testing
sim = SimulationCore(gui=False, real_time=False)

# Run 100 trials quickly
for trial in range(100):
    sim.reset()
    # ... run test ...
    sim.close()
```

## Debugging

### Visual Debugging

```python
import cv2

# Show camera view
frame = camera.read()
cv2.imshow('Camera', frame)
cv2.waitKey(1)

# Draw detections
from src.perception.ball_detector import BallDetector
detector = BallDetector(config)

detections = detector.detect(frame)
debug_frame = detector.draw_detections(frame, detections)
cv2.imshow('Detections', debug_frame)
```

### Print State

```python
# Monitor robot state
state = sim.get_robot_state()
print(f"Position: {state['position']}")
print(f"Orientation: {state['orientation']}")

# Check motor speeds
print(f"Motors: L={chassis.left_speed}, R={chassis.right_speed}")
```

## Example Scripts

### Complete Test Example

```python
#!/usr/bin/env python3
"""Test navigation to basket"""

import sys
import yaml
from src.simulation.sim_core import SimulationCore
from src.simulation.sim_hardware import create_sim_hardware

# Load config
config = yaml.safe_load(open('config.yaml'))

# Initialize
sim = SimulationCore(gui=True, real_time=True)
sim.initialize()
sim.load_arena()
robot_id = sim.load_robot()
sim.spawn_balls()

chassis, arm, camera = create_sim_hardware(robot_id, config)

# Navigate forward for 3 seconds
print("Moving forward...")
chassis.forward(speed=0.15)
for _ in range(720):
    sim.step()

# Stop
chassis.stop()
print("Done!")

# Keep window open
input("Press Enter to exit...")
sim.close()
```

## Next Steps

- **Phase 1**: Basic robot motion — tests in progress
- **Phase 2**: Camera rendering and perception testing — tests in progress
- **Phase 3**: Full state machine and autonomous loop — tests in progress

See [ARCHITECTURE.md](ARCHITECTURE.md) for implementation details.
