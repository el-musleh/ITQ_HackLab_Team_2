# Hardware Reference — JETANK

## Robot Specs

| Component | Spec |
|-----------|------|
| **Platform** | NVIDIA Jetson Nano Developer Kit |
| **Chassis** | Tracked, high-torque DC geared motors |
| **Arm** | 4-DOF servo-driven robot arm |
| **Camera** | CSI camera (Jetson onboard) |
| **Programming** | WiFi + Jupyter Notebook |
| **Servo Bus** | SCSCtrl protocol |
| **Serial Port** | `/dev/ttyTHS1` at 1,000,000 baud |

## Servo IDs (JETANK Default)

| ID | Function | Notes |
|----|----------|-------|
| 1 | Camera pan (horizontal) | Pan/tilt head |
| 5 | Camera tilt (vertical) | Pan/tilt head |
| 2 | Arm base | First joint |
| 3 | Arm shoulder | Second joint |
| 4 | Arm elbow | Third joint |
| 6 | Gripper | Claw open/close |

> **Safe angles must be documented on-site.** Test each servo individually before full motion.

## Key Libraries

| Library | Purpose | Source |
|---------|---------|--------|
| `jetbot` | Camera interface | Pre-installed on Jetson |
| `SCSCtrl` | Servo motor control | `/workspace/JETANK/SCSCtrl/` |
| `cv2` (OpenCV) | Computer vision | `pip install opencv-python` |
| `TTLServo` | High-level servo API | From `SCSCtrl` package |

## Official Examples Location (on Jetson)

```
/workspace/JETANK/
├── JETANK_1_servos/              # Individual servo control
├── JETANK_2_ctrl/                # Chassis motor control
├── JETANK_3_motionDetect/        # Motion detection
├── JETANK_4_colorRecognition/    # HSV color calibration
├── JETANK_5_colorTracking/       # **Most relevant — cap detection**
└── JETANK_6_gamepadCtrl/         # Manual remote control
```

**`JETANK_5_colorTracking`** is the starting point for bottle cap detection.
