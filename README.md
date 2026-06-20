# 🤖 ITQ — Autonomous Bottle Cap Collector

[![Hackathon](https://img.shields.io/badge/Event-AI%20%26%20Robotics%20Hackathon%20Berlin-blue)](https://hacklabs.beehiiv.com/)
[![Status](https://img.shields.io/badge/Status-In%20Progress-yellow)](.)
[![Team](https://img.shields.io/badge/Team-Team%202-green)](.)
[![Robot](https://img.shields.io/badge/Robot-Waveshare%20JETANK-orange)](https://github.com/waveshare/JETANK)

> **Mission:** Build an autonomous robot that navigates a parkour course, avoids obstacles, and collects as many bottle caps as possible — all within 5 minutes.
>
> **Hardware:** [Waveshare JETANK](https://github.com/waveshare/JETANK) — tracked robot with 4-DOF arm on NVIDIA Jetson Nano

---

## 🏆 Challenge

| | |
|---|---|
| **Track** | ITQ — Autonomous Detection and Collection of Bottle Caps with Computer Vision |
| **Prize** | 200€ cash |
| **Time Limit** | 5 minutes per run |
| **Scoring** | Caps collected (primary) + completion time + safety penalty |
| **Win Condition** | Most caps with **zero collisions** |

**Strategy:** Safe and steady beats fast and reckless. Every collision costs you.

---

## 🚀 Quick Start

All code runs on the **NVIDIA Jetson Nano** via **WiFi + Jupyter Notebook**.

```bash
# On your laptop: SSH into Jetson
ssh jetson@<jetson-ip>

# Start Jupyter on the Jetson
jupyter notebook --ip=0.0.0.0 --port=8888

# Open browser on laptop
# http://<jetson-ip>:8888

# In Jupyter: clone and run
git clone <repo-url>
cd itq-bottle-cap-collector
# Open notebooks/01_calibrate.ipynb and follow steps
```

---

## 📁 Project Structure

```
.
├── README.md                    # This file
├── requirements.txt             # Python dependencies
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
│   ├── pid.py                  # PID controller for line following
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

---

## 🧠 Architecture

```
Camera Feed
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

---

## 🛠️ Setup

### Hardware: Waveshare JETANK
| Component | Spec |
|-----------|------|
| **Platform** | NVIDIA Jetson Nano Developer Kit |
| **Chassis** | Tracked, high-torque DC geared motors |
| **Arm** | 4-DOF servo-driven robot arm |
| **Camera** | CSI camera (Jetson onboard) |
| **Programming** | WiFi + Jupyter Notebook |
| **Servo Bus** | SCSCtrl protocol |

> [JETANK GitHub Repo](https://github.com/waveshare/JETANK) — official examples for servo control, color tracking, motion detection, and gamepad control.

### Prerequisites (on Jetson Nano)
- JetPack 4.x+ installed
- Python 3.6+ (comes with Jetson)
- WiFi connected
- Git

### Dependencies (install on Jetson)
```bash
# Core (Jetson-optimized)
pip install opencv-python numpy matplotlib

# JETANK servo control
pip install pyserial
# Or use included SCSCtrl: https://github.com/waveshare/JETANK/tree/master/SCSCtrl

# Detection (optional — color blob may be enough)
pip install ultralytics

# Jetson inference (if using TensorRT / trt_pose)
pip install jetson-inference
```

### Hardware Checklist
- [ ] Jetson Nano booted and WiFi connected
- [ ] JETANK chassis assembled and tracked motors test-driven
- [ ] 4-DOF arm servos responding to SCSCtrl commands
- [ ] CSI camera capturing frames in OpenCV
- [ ] Ultrasonic / IR sensors reading distances
- [ ] Bottle cap "collection" mapped to arm motion (grab + lift + drop)
- [ ] Battery pack charged (spare recommended)
- [ ] Laptop can reach Jetson at `http://<jetson-ip>:8888`

---

## 👥 Team & Responsibilities

| Name | Role | Module | Status |
|------|------|--------|--------|
| **Yashveer Sookun** | Vision Lead | `perception/` | 🔴 Not started |
| **Salawu Wareeth** | Pipeline / Logging | `utils/telemetry.py` | 🔴 Not started |
| **Mohammed Abubakr Khan** | Integration / QA | `tests/` | 🔴 Not started |
| **Joaquín Morillo Soto** | Hardware / Mechanics | `hardware/` | 🔴 Not started |
| **Mohammad El Musleh** | Control Lead | `control/` + Jetson setup | 🔴 Not started |
| **Myron Sydorov** | Navigation / Recovery | `control/recovery.py` | 🔴 Not started |

**Workflow:** Each person owns their module. Open a PR when ready. Pair-review before merging.

---

## ✅ TODO / Progress

### Phase 1: Perception (Hour 0–2)
- [ ] Camera calibration script (`perception/calibrate.py`)
- [ ] HSV-based bottle cap detector
- [ ] Multi-frame validation filter
- [ ] Obstacle detection (reuse cap pipeline or dedicated sensor)

### Phase 2: Control (Hour 2–4)
- [ ] State machine implementation (`control/state_machine.py`)
- [ ] PID controller for line following (`control/pid.py`)
- [ ] Recovery behavior (stuck detection + escape)
- [ ] Integrate perception → control bridge

### Phase 3: Integration (Hour 4–6)
- [ ] End-to-end test on practice course
- [ ] Telemetry logging (caps, time, collisions)
- [ ] Tune detection thresholds on real lighting
- [ ] Tune PID gains for smooth movement

### Phase 4: Polish (Hour 6–8)
- [ ] Manual override / joystick fallback
- [ ] Backup demo video recorded
- [ ] Final stress test (battery, lighting, WiFi)
- [ ] **Submit**

---

## 🎯 MVP Definition

Before building anything fancy, the robot must:

1. Drive forward without crashing
2. See a bottle cap with the camera
3. Stop near the cap
4. Trigger a collection action

**Rule:** Nothing else gets built until MVP works. Optimization is a luxury; functionality is the requirement.

---

## ⚠️ Risk Register

| Risk | P | I | Mitigation |
|------|---|---|------------|
| False cap detection | M | H | HSV primary + YOLO backup; multi-frame validation |
| Stuck in corner | M | H | Timeout recovery: reverse tracks + rotate 45° |
| Collision | L | **C** | Conservative speed in APPROACH; ultrasonic / IR stop-distance |
| Battery failure | L | H | Fresh battery per run; voltage telemetry |
| Bad lighting | M | M | On-site calibration; wide HSV thresholds |
| Hardware failure | L | H | Recorded demo video as fallback |

---

## 📚 Resources

- [JETANK GitHub](https://github.com/waveshare/JETANK) — servo control, color tracking, motion detection examples
- [JETANK Color Tracking Example](https://github.com/waveshare/JETANK/tree/master/JETANK_5_colorTracking) — highly relevant to cap detection
- [OpenCV Docs](https://docs.opencv.org)
- [YOLOv8 Quickstart](https://docs.ultralytics.com/quickstart/)
- [NVIDIA Jetson Nano Docs](https://developer.nvidia.com/embedded/jetson-nano-developer-kit)

---

## 📝 Git Workflow

```bash
# Start your module
git checkout -b feature/perception-detector

# Commit often
git add perception/detector.py
git commit -m "feat: add HSV bottle cap detector"

# Push and open PR
git push origin feature/perception-detector
# Tag Mohammad or Myron for review
```

---

*Event:* AI & Robotics Hackathon Berlin — Team 2 — ITQ Track  
*Last updated:* June 20, 2026 (Project kickoff)
