# Software Architecture

## Module Structure

```
itq-bottle-cap-collector/
├── main.py                      # Entry point — state machine orchestrator
├── config.yaml                  # Camera thresholds, PID gains, course params
│
├── perception/                  # 🎥 Computer vision module
│   ├── __init__.py
│   ├── camera.py               # Camera capture & calibration
│   ├── detector.py             # Bottle cap detection (HSV blob + YOLO fallback)
│   ├── obstacle_detector.py    # Obstacle / wall detection
│   └── calibrate.py            # On-site color/light calibration tool
│
├── control/                     # 🎮 Movement & navigation module
│   ├── __init__.py
│   ├── state_machine.py        # SEARCH → APPROACH → COLLECT → RETURN
│   ├── pid.py                  # PID controller for approach
│   ├── navigator.py            # Waypoint & path management
│   └── recovery.py             # Stuck-detection & escape behaviors
│
├── hardware/                    # 🔧 Robot interface (JETANK / Jetson Nano)
│   ├── __init__.py
│   ├── chassis.py              # Tracked motor control via SCSCtrl
│   ├── arm.py                  # 4-DOF arm servo control
│   ├── camera.py               # CSI camera on Jetson Nano
│   └── sensors.py              # Ultrasonic / IR sensors
│
├── utils/                       # 🔧 Utilities
│   ├── __init__.py
│   ├── telemetry.py            # Logging: caps seen, collected, collisions, time
│   └── visualizer.py           # Debug overlay for camera feed
│
└── tests/                       # ✅ Validation scripts
    ├── test_camera.py
    ├── test_detection.py
    └── test_pid.py
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
| Recovery | Timeout + reverse tracks | Tracked chassis rotates in place for escape |
| Speed strategy | Conservative | Collisions cost more than slow movement |

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
