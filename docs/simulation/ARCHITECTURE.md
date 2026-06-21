# Simulation Architecture

Technical design and implementation details of the PyBullet simulation environment.

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                   User Code                             │
│  (State Machine, PID, Perception, Navigation)           │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ Same API
                  │
        ┌─────────┴──────────┐
        │                    │
┌───────▼────────┐  ┌────────▼────────┐
│   Real HW      │  │   Simulation    │
│  (Jetson)      │  │   (PyBullet)    │
├────────────────┤  ├─────────────────┤
│ chassis.py     │  │ sim_hardware.py │
│ arm.py         │  │ - SimChassis    │
│ camera.py      │  │ - SimArm        │
│                │  │ - SimCamera     │
└────────────────┘  └─────────────────┘
                           │
                    ┌──────▼──────┐
                    │  sim_core.py│
                    │  (PyBullet) │
                    └─────────────┘
```

## Core Components

### 1. SimulationCore (`sim_core.py`)

**Purpose**: Manages PyBullet physics engine and simulation state.

**Key Methods:**
- `initialize()`: Start PyBullet (GUI or headless)
- `load_arena()`: Load URDF models for arena
- `load_robot()`: Load robot URDF
- `spawn_balls()`: Create ball objects
- `step()`: Advance physics by 1/240 second
- `reset()`: Return to initial state
- `get_robot_state()`: Get position/orientation
- `check_collision()`: Detect collisions

**Physics Configuration:**
- Timestep: 1/240 second (240 Hz)
- Gravity: -9.81 m/s²
- Solver: PyBullet default (sequential impulse)

### 2. Simulated Hardware (`sim_hardware.py`)

**Purpose**: Provide drop-in replacements for real hardware modules.

#### SimChassis

Mimics `hardware.chassis.Chassis`:

```python
class SimChassis:
    def set_motors(left, right):
        # Convert to linear/angular velocity
        linear_vel = (left + right) / 2
        angular_vel = (right - left) / wheel_base
        
        # Apply to robot base
        p.resetBaseVelocity(robot_id, ...)
```

**Implementation:**
- Differential drive model
- Wheel base: 0.16 m
- Velocity-based control (not force-based)
- Speed clamping to match real hardware

#### SimArm

Mimics `hardware.arm.Arm`:

```python
class SimArm:
    def set_joint_angles(angles):
        # Convert degrees to radians
        # Apply position control to joints
        p.setJointMotorControl2(...)
```

**Implementation:**
- 4 revolute joints (base, shoulder, elbow, gripper)
- Position control with max force
- Predefined poses from config.yaml
- Sequences: pickup, deposit

#### SimCamera

Mimics `hardware.camera.Camera`:

```python
class SimCamera:
    def read():
        # Compute view matrix from robot pose
        # Render image with PyBullet
        # Convert RGB to BGR (OpenCV format)
        return bgr_image
```

**Implementation:**
- 320×240 resolution
- 160° FOV (wide-angle)
- Camera mounted on robot chassis
- Returns OpenCV-compatible BGR images

### 3. URDF Models

#### Robot Model (`jetank.urdf`)

**Structure:**
```
base_link (chassis)
├── camera_link (fixed joint)
├── arm_base (revolute, yaw)
│   └── arm_shoulder (revolute, pitch)
│       └── arm_elbow (revolute, pitch)
│           └── gripper (revolute, open/close)
```

**Dimensions:**
- Chassis: 26×20×10 cm
- Camera height: 12 cm above chassis
- Arm reach: ~18 cm forward

**Inertial Properties:**
- Total mass: ~1.5 kg
- Realistic inertia tensors
- Joint limits from spec

#### Arena Model (`arena.urdf`)

**Components:**
1. Ground plane (180×175 cm)
2. Boundary walls (yellow, 10 cm high)
3. Obstacle 1 (30×20×15 cm crate + yellow tape)
4. Obstacle 2 (40×30×15 cm crate + yellow tape)
5. Basket (gray cylinder, 30 cm diameter)

**Fixed Objects:**
- All obstacles and walls use `useFixedBase=True`
- Zero mass (infinite mass in PyBullet)

## Data Flow

### Simulation Loop

```python
# Initialize
sim = SimulationCore(gui=True)
sim.initialize()
sim.load_arena()
robot_id = sim.load_robot()
chassis, arm, camera = create_sim_hardware(robot_id, config)

# Main loop
while running:
    # 1. Sense
    frame = camera.read()
    state = sim.get_robot_state()
    
    # 2. Perceive
    detections = detector.detect(frame)
    
    # 3. Decide
    action = state_machine.update(detections)
    
    # 4. Act
    chassis.set_motors(action['left'], action['right'])
    
    # 5. Step physics
    sim.step()
```

### Camera Rendering Pipeline

```
Robot Pose → View Matrix → Projection Matrix → Render → RGB → BGR
     ↓            ↓              ↓               ↓       ↓      ↓
  [x,y,z]    Camera pos    FOV, aspect    PyBullet  Numpy  OpenCV
  [r,p,y]    Target pos    Near, far      getCameraImage
```

**Performance:**
- Rendering: ~5-10 ms per frame (GPU)
- Physics step: ~1-2 ms (CPU)
- Total: ~60-100 FPS achievable

## Hardware Abstraction Layer

### Interface Contract

All hardware modules must implement:

**Chassis:**
```python
def set_motors(left: float, right: float) -> None
def forward(speed: float) -> None
def backward(speed: float) -> None
def turn_left(speed: float) -> None
def turn_right(speed: float) -> None
def stop() -> None
```

**Arm:**
```python
def set_joint_angles(angles: List[float]) -> None
def move_to_pose(pose_name: str) -> None
def pickup_sequence() -> None
def deposit_sequence() -> None
```

**Camera:**
```python
def read() -> np.ndarray  # BGR image
def set_pan(angle: float) -> None
def set_tilt(angle: float) -> None
```

### Factory Pattern

```python
from src.utils import load_config
config = load_config()

# Simulation branch
from src.simulation import SimulationCore, create_sim_hardware
sim = SimulationCore(gui=False, config=config)
sim.initialize()
sim.load_arena()
robot_id = sim.load_robot()
sim.spawn_balls()
# Pass sim= so arm sequences step physics and grasp balls
chassis, arm, camera = create_sim_hardware(robot_id, config, sim=sim)

# Real hardware branch
# from src.hardware.chassis import ChassisController
# from src.hardware.arm import ArmController
# from src.hardware.camera import CameraController
# chassis = ChassisController()
# arm = ArmController(config)
# camera = CameraController()
```

`load_config()` lives in `src/utils` and is the single source of truth for
reading `config.yaml` (previously duplicated across 7 files).

## Physics Simulation

### Locomotion Modes

The chassis supports two locomotion modes, selected via `config.yaml`:
`simulation.locomotion_mode` (default `velocity`).

#### `velocity` mode (default, stable)

Sets the robot base velocity directly. Fast, deterministic, and decoupled
from wheel friction — the same behavior the original simulation shipped
with.

```python
# Input: left_speed, right_speed (normalized -1 to 1)
linear_vel = (left + right) / 2
angular_vel = (right - left) / wheel_base

# Convert to world frame
vel_x = linear_vel * cos(yaw) * scale
vel_y = linear_vel * sin(yaw) * scale

# Apply to robot
p.resetBaseVelocity(
    robot_id,
    linearVelocity=[vel_x, vel_y, 0],
    angularVelocity=[0, 0, angular_vel * scale]
)
```

**Scale Factor**: 2.0 (tuned to match real robot speed)

#### `wheels` mode (realistic)

Drives the four wheel joints via `p.VELOCITY_CONTROL`, so motion emerges
from friction and contact rather than being teleported. Wheel joints and
sides are discovered from the URDF at runtime (`wheel_fl_joint`,
`wheel_rr_joint`, etc.). A `wheel_direction_sign` (-1.0 by default)
compensates for the jetank.urdf wheel axis orientation so `forward()` still
moves the robot forward.

```python
left_ang  = (left_speed  * speed_scale) / wheel_radius * wheel_direction_sign
right_ang = (right_speed * speed_scale) / wheel_radius * wheel_direction_sign
for idx in wheel_left:  p.setJointMotorControl2(robot, idx, p.VELOCITY_CONTROL,
                                                targetVelocity=left_ang,  force=max_force)
for idx in wheel_right: p.setJointMotorControl2(robot, idx, p.VELOCITY_CONTROL,
                                                targetVelocity=right_ang, force=max_force)
```

### Joint Discovery

Joint indices are discovered from the URDF at runtime by matching joint
names to logical roles, instead of being hardcoded:

```python
_JOINT_NAME_ROLES = {
    'arm_base_joint': 'base',
    'arm_shoulder_joint': 'shoulder',
    'arm_elbow_joint': 'elbow',
    'arm_wrist_joint': 'wrist',
    'claw_joint': 'claw',
}
```

`SimulationCore.get_joint_map()` returns the resolved `{role: index}` map
and `get_wheel_joint_indices()` returns the wheel joints. `ArmController`
and `ChassisController` accept these maps and fall back to hardcoded
defaults for backwards compatibility.

### Ball Grasping

`SimulationCore.attach_ball_to_gripper(ball_id)` creates a `JOINT_FIXED`
constraint between the gripper link and a ball, so pickup is physical
rather than cosmetic. `detach_ball()` removes it (called automatically by
`deposit_sequence`). The arm's grasp helper first tries contact detection,
then falls back to proximity (nearest ball within 0.08 m of the gripper
link) so grasping works without precise gripper-geometry tuning.

### Collision Detection

PyBullet automatically handles:
- Continuous collision detection
- Contact point generation
- Friction and restitution

**Query:**
```python
contacts = p.getContactPoints(bodyA, bodyB)
colliding = len(contacts) > 0
```

### Joint Control

**Position Control:**
```python
p.setJointMotorControl2(
    robot_id,
    joint_index,
    p.POSITION_CONTROL,
    targetPosition=angle_rad,
    force=max_force
)
```

**PD Controller:**
- PyBullet uses internal PD controller
- Default gains work well for arm joints
- Can be tuned with `positionGain` and `velocityGain`

## Coordinate Systems

### World Frame
- Origin: Center of arena floor
- X: Forward (north)
- Y: Left (west)
- Z: Up

### Robot Frame
- Origin: Center of chassis
- X: Forward
- Y: Left
- Z: Up

### Camera Frame
- Origin: Camera optical center
- X: Right
- Y: Down
- Z: Forward (optical axis)

## Performance Characteristics

### Timing

| Operation | Time (ms) | Frequency |
|-----------|-----------|-----------|
| Physics step | 1-2 | 240 Hz |
| Camera render | 5-10 | 30 Hz |
| Ball detection | 10-20 | 15 Hz |
| State machine | <1 | 30 Hz |

### Memory Usage

- PyBullet engine: ~50 MB
- Robot model: ~1 MB
- Arena model: ~2 MB
- Camera buffer: ~0.3 MB (320×240×3)
- Total: ~60-80 MB

### Scalability

- Single robot: 240 Hz real-time
- Multiple robots: 120 Hz (2 robots), 60 Hz (4 robots)
- Headless mode: 10-100× faster than real-time

## Sim-to-Real Transfer

### What Transfers Well

✅ **Control logic**: State machine, PID gains
✅ **Navigation**: Path planning, obstacle avoidance
✅ **Arm sequences**: Pickup/deposit motions
✅ **Perception logic**: Detection algorithms

### What Requires Tuning

⚠️ **HSV ranges**: Lighting differs in simulation
⚠️ **Motor speeds**: Friction/slip differs
⚠️ **Gripper force**: Contact physics approximate
⚠️ **Timing**: Real hardware has latency

### Recommended Workflow

1. **Develop in simulation**: Test logic, debug algorithms
2. **Validate structure**: Ensure code runs without errors
3. **Deploy to hardware**: Use same code with real hardware
4. **Fine-tune parameters**: Adjust HSV, speeds, PID gains
5. **Iterate**: Fix issues found on hardware

## Extension Points

### Adding New Sensors

```python
class SimLidar:
    def __init__(self, robot_id):
        self.robot_id = robot_id
    
    def scan(self):
        # Use p.rayTest() for range sensing
        pass
```

### Custom Arena Layouts

Edit `arena.urdf` or create new URDF files:
```xml
<link name="custom_obstacle">
  <visual>...</visual>
  <collision>...</collision>
</link>
```

### Data Collection

```python
# Record trajectories
trajectory = []
for i in range(1000):
    state = sim.get_robot_state()
    frame = camera.read()
    trajectory.append({
        'time': i / 240.0,
        'position': state['position'],
        'image': frame
    })
    sim.step()

# Save for analysis
import pickle
pickle.dump(trajectory, open('trajectory.pkl', 'wb'))
```

## References

- [PyBullet Quickstart](https://docs.google.com/document/d/10sXEhzFRSnvFcl3XxNGhnD4N2SedqwdAvK3dsihxVUA/edit)
- [URDF Specification](http://wiki.ros.org/urdf/XML)
- [Differential Drive Kinematics](https://www.cs.columbia.edu/~allen/F17/NOTES/icckinematics.pdf)
