# Software Architecture

## Module Structure

```
itq-bottle-cap-collector/
├── src/
│   ├── main.py                  # Entry point — state machine orchestrator
│   ├── config.yaml              # (stays in root — shown here for reference)
│   │
│   ├── perception/              # 🎥 Computer vision module
│   │   ├── __init__.py
│   │   ├── camera.py            # Camera capture & calibration
│   │   ├── detector.py          # Bottle cap detection (HSV blob + YOLO fallback)
│   │   ├── obstacle_detector.py # Obstacle / wall detection
│   │   └── calibrate.py         # On-site color/light calibration tool
│   │
│   ├── control/                 # 🎮 Movement & navigation module
│   │   ├── __init__.py
│   │   ├── state_machine.py     # IDLE → WANDERING → COLLECT → DEPOSIT → END
│   │   ├── world_map.py         # Ball registry, blind-spot grid, coverage tracking
│   │   ├── pid.py               # PID controller for approach
│   │   ├── navigator.py         # Waypoint & path management
│   │   ├── odometry.py          # Pose estimation + landmark correction
│   │   └── safety_monitor.py    # Proactive stuck / dark-frame / arm-collision detection
│   │
│   ├── hardware/                # 🔧 Robot interface (JETANK / Jetson Nano)
│   │   ├── __init__.py
│   │   ├── chassis.py           # Tracked motor control via SCSCtrl
│   │   ├── arm.py               # 4-DOF arm servo control
│   │   ├── camera.py            # CSI camera on Jetson Nano
│   │   └── sensors.py           # Ultrasonic / IR sensors
│   │
│   └── utils/                   # 🔧 Utilities
│       ├── __init__.py
│       ├── telemetry.py         # Logging: caps seen, collected, collisions, time
│       └── visualizer.py        # Debug overlay for camera feed
│
└── tests/                       # ✅ Validation scripts
    ├── test_state_machine.py
    ├── test_world_map.py
    ├── test_odometry.py
    ├── test_sim_core.py
    └── test_sim_hardware.py
```

## Data Flow

```
Camera Feed (CSI)
     │
     ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Perception │────▶│   Control   │────▶│  Hardware   │
│  (OpenCV)   │     │(State Mach) │     │  (Motors)   │
└─────────────┘     └─────────────┘     └─────────────┘
      │                    │                    │
      ▼                    ▼                    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Cap Det.   │     │   PID Nav   │     │  Collector │
│  Obstacle   │     │  Recovery   │     │  Sensors   │
└─────────────┘     └─────────────┘     └─────────────┘
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Detection | HSV color blob primary | Fast, no training needed, works on Jetson Nano CPU |
| Detection backup | YOLO (Ultralytics) | If colors vary or lighting is unpredictable |
| Approach control | PID controller | Smooth approach, less oscillation than bang-bang |
| Collection | Arm servo choreography | Grab + lift + stow; exact angles tuned on-site |
| Recovery | SafetyMonitor + reason-based | Stuck, dark-frame, arm-collision detectors with tailored recovery |
| Speed strategy | Distance-based ramping | Fast when far, gradual deceleration near target; trapezoidal servo profile for arm |
| Ball memory | WorldMap with color + confidence | Tracks ball positions, merges duplicates, marks collected/unreachable |
| Blind-spot grid | Adaptive refinement (10 cm + half-res near obstacles) | Catches narrow gaps without excessive cell count |
| Odometry drift | Landmark correction (weighted alpha blend) | Reduces dead-reckoning error using basket as known landmark |

## Config File Structure

```yaml
# Camera settings
camera:
  width: 320
  height: 240
  fps: 30
  source: 0

# Color detection (HSV) — TUNE ON-SITE!
color:
  lower_hsv: [24, 100, 100]
  upper_hsv: [44, 255, 255]

# State machine tuning
state_machine:
  approach_distance_px: 50
  search_rotate_speed: 30
  approach_speed: 40
  recovery_timeout_sec: 5

# Motor limits (distance-based speed ramping)
motors:
  max_speed: 0.25
  approach_speed: 0.15
  search_speed: 0.10
  min_approach_speed: 0.05       # Crawl speed when very close to ball
  far_distance_threshold: 50.0   # cm — full speed above this distance
  close_distance_threshold: 15.0 # cm — min speed below this distance

# Safety monitor (proactive collision / stuck / dark-frame detection)
safety:
  stuck_window_s: 2.0
  stuck_min_displacement: 0.02
  stuck_motor_threshold: 0.05
  dark_threshold: 25
  dark_frame_count: 3
  arm_timeout_multiplier: 1.5
  arm_visual_check: true

# PID controller
pid:
  kp: 3.0
  ki: 0.0
  kd: 0.5

# Servo IDs
servos:
  pan: 1
  tilt: 5
  arm_base: 2
  arm_shoulder: 3
  arm_elbow: 4
  gripper: 6

# Serial port
serial:
  port: /dev/ttyTHS1
  baudrate: 1000000
```
