# ITQ Bottle Cap Collector — Challenge Specification

**Track:** Autonomous Detection and Collection of Bottle Caps with Computer Vision  
**Team:** Team 2  
**Robot:** Waveshare JETANK AI Kit (NVIDIA Jetson Nano)

---

## 📋 Challenge Overview

Build an autonomous robot system to navigate a 175×180 cm arena, detect and collect colored balls (bottle caps), avoid obstacles marked with yellow tape, and deposit collected balls into a stationary gray basket—all within 5 minutes.

### Scoring
1. **Primary:** Number of balls collected and deposited in basket
2. **Secondary:** Completion time (faster = better)
3. **Penalty:** Collisions with obstacles or boundary crossing

---

## 🏟️ Arena Specification

### Dimensions
- **Size:** 175 cm × 180 cm
- **Boundary:** Yellow tape marking (robot must NOT cross)
- **Surface:** Flat floor
- **Time Limit:** 5 minutes per run

### Objects to Collect
- **Type:** Small balls (bottle caps)
- **Colors:** Blue, Red, Silver (multi-color detection required)
- **Quantity:** ~22 balls (variable: 15-25)
- **Size:** Standard bottle cap (~3-4 cm diameter)

### Target Basket
- **Color:** Gray
- **Location:** Center of arena (stationary)
- **Identification:** Requires calibration at start
- **Dimensions:** Measure on-site

### Obstacles
- **Type:** Crates (glass bottle collection boxes) marked with yellow tape
- **Count:** 2 obstacles
- **Sizes:** 
  - Obstacle 1: 20 cm × 30 cm
  - Obstacle 2: 30 cm × 40 cm
- **Movement:** Static (fixed positions)
- **Detection:** Vision-based (yellow tape + edge detection)

---

## 🤖 Robot Hardware Specification

### Platform
- **Controller:** NVIDIA Jetson Nano 4GB
- **Chassis:** Tracked, dual DC geared motors
- **Arm:** 4-DOF servo-driven robotic arm
- **Camera:** CSI IMX219 (160° FOV, 320×240 operational)
- **Sensors:** Camera only (no ultrasonic)

### Component Ranges

#### Camera (CSI IMX219)
- **Resolution:** 320×240 (optimized for real-time)
- **FOV:** 160° wide-angle
- **Frame Rate:** 15-30 fps target
- **Height:** ~120 mm from ground
- **Mount:** Pan/tilt servos

#### Motors
- **Type:** 2× DC geared motors with encoders
- **Speed Range:** 0.0 - 1.0 (normalized)
- **Max Safe Speed:** 0.25
- **Control:** TB6612FNG driver

#### Servos (SCSCtrl Protocol)
| ID | Function | Model | Rotation Range | Safe Limits |
|----|----------|-------|----------------|-------------|
| 1 | Camera Pan | MG996R | 180° | ±90° |
| 5 | Camera Tilt | MG996R | 180° | ±60° |
| 2 | Arm Base | MG996R | 180° | ±90° |
| 3 | Arm Shoulder | MG996R | 180° | ±80° |
| 4 | Arm Elbow | MG996R | 180° | ±80° |
| 6 | Gripper | SG90 | 90° | 0-90° |

#### Robotic Arm
- **DOF:** 4 (base, shoulder, elbow, gripper)
- **Max Forward Reach:** ~180 mm
- **Max Vertical Reach:** ~160 mm
- **Gripper Opening:** 55 mm max
- **Payload:** ~50g (sufficient for bottle caps)

---

## 🎯 Solution Architecture

### State Machine

```
STARTUP → SEARCH → APPROACH → COLLECT → RETURN → DEPOSIT → SEARCH
    ↓         ↓         ↓
AVOID_BOUNDARY / AVOID_OBSTACLE (priority interrupts)
```

**States:**
- **STARTUP:** Initialize, calibrate basket
- **SEARCH:** Rotate and scan for balls
- **APPROACH:** Navigate to detected ball using PID
- **COLLECT:** Execute arm pickup sequence
- **RETURN:** Navigate back to basket
- **DEPOSIT:** Execute arm deposit sequence
- **AVOID_BOUNDARY:** Emergency boundary avoidance
- **AVOID_OBSTACLE:** Reactive obstacle avoidance

### Perception Pipeline

#### 1. Ball Detection (Multi-Color HSV)
```python
BLUE_HSV   = ([100, 150, 50], [130, 255, 255])
RED_HSV_1  = ([0, 150, 50], [10, 255, 255])
RED_HSV_2  = ([170, 150, 50], [180, 255, 255])
SILVER_HSV = ([0, 0, 150], [180, 30, 255])
```

**Process:**
1. BGR → HSV conversion
2. Apply color masks
3. Morphological operations (erode + dilate)
4. Contour detection with circularity filter
5. Multi-frame validation (3 consecutive frames)
6. Distance estimation from pixel area

#### 2. Obstacle Detection (Yellow Tape)
```python
YELLOW_HSV = ([20, 100, 100], [40, 255, 255])
```

**Process:**
1. HSV mask for yellow
2. ROI: bottom 30% (boundary) and front 15-65% (obstacles)
3. Canny edge detection
4. Pixel count thresholding
5. Turn direction logic (left/right/reverse)

#### 3. Basket Localization
```python
GRAY_HSV = ([0, 0, 50], [180, 50, 200])
```

**Process:**
1. Calibration phase: capture basket appearance
2. Runtime: detect gray region matching calibrated size
3. Calculate bearing angle and distance
4. Navigate to drop zone

---

## 📁 Implementation Structure

### Modules Created

```
perception/
├── ball_detector.py          ✓ Multi-color ball detection
├── obstacle_detector.py      ✓ Yellow tape + edge detection
└── basket_detector.py        ✓ Gray basket localization

control/
├── state_machine.py          ✓ Main FSM
├── pid.py                    ✓ PID controller
├── navigator.py              ✓ Motion planning
└── recovery.py               ✓ Stuck detection & escape

hardware/
├── arm.py                    ✓ 4-DOF arm control
├── chassis.py                ✓ Motor control wrapper
└── camera.py                 ✓ Camera + pan/tilt

notebooks/
├── 00_calibrate_basket.ipynb ✓ Basket calibration
└── 06_full_run.ipynb         ✓ Autonomous run

config.yaml                   ✓ Updated with all parameters
```

---

## 🚀 Usage Instructions

### 1. Pre-Competition Setup

```bash
# Connect to robot
# WiFi: TP-LINK_744C (password: 15253354)
# Jupyter: http://192.168.0.100:8888/lab
# Password: CIC@Tics1XAI
```

### 2. Calibration Sequence

**Step 1: Basket Calibration**
```
Open: notebooks/00_calibrate_basket.ipynb
1. Position robot ~30 cm from basket
2. Run all cells
3. Verify calibration saved to config.yaml
```

**Step 2: Color Calibration** (if needed)
```
Adjust HSV ranges in config.yaml for arena lighting
Test with actual balls (blue, red, silver)
```

**Step 3: Hardware Test**
```
Open: robot_tests/robot_diagnostics.ipynb
Run all sections to verify:
- Camera feed
- Motors
- Servos/Arm
- Perception
```

### 3. Competition Run

```
Open: notebooks/06_full_run.ipynb
1. Run setup cells
2. Test perception (optional)
3. Click START button
4. Robot runs autonomously for 5 minutes
5. Click STOP or wait for completion
```

---

## ⚙️ Configuration Parameters

### Key Settings in `config.yaml`

```yaml
# Arena
arena:
  width_cm: 175
  height_cm: 180

# Ball Colors (adjust on-site)
balls:
  colors:
    blue: {hsv_lower: [100, 150, 50], hsv_upper: [130, 255, 255]}
    red_1: {hsv_lower: [0, 150, 50], hsv_upper: [10, 255, 255]}
    red_2: {hsv_lower: [170, 150, 50], hsv_upper: [180, 255, 255]}
    silver: {hsv_lower: [0, 0, 150], hsv_upper: [180, 30, 255]}

# Motors
motors:
  max_speed: 0.25
  approach_speed: 0.15
  search_speed: 0.10

# Arm Poses (angles in degrees)
arm_poses:
  home: [0, 0, 0, 0]
  pickup: [0, -40, -60, 0]
  carry: [0, 20, 30, 90]
  deposit: [0, 40, 40, 0]
```

---

## 🧪 Testing Protocol

### Pre-Run Checklist
- [ ] Camera feed live at 15+ fps
- [ ] All servos respond (IDs 1-6)
- [ ] Motors drive forward/reverse/turn
- [ ] Ball detection works for all 3 colors
- [ ] Obstacle avoidance triggers correctly
- [ ] Basket calibration saved
- [ ] Arm pickup sequence completes
- [ ] Gripper holds ball securely
- [ ] Deposit sequence drops ball in basket

### Practice Runs
1. Run 3× practice runs before competition
2. Log: balls collected, time, collisions
3. Identify and fix failure modes
4. Tune HSV ranges if needed
5. Adjust arm poses if pickup fails

---

## ⚠️ Risk Mitigation

| Risk | Mitigation |
|------|------------|
| **Multi-color detection fails** | HSV calibration on-site; fallback to single color |
| **Basket not found** | Manual calibration cell; visual marker option |
| **Stuck in corner** | Timeout recovery (3s); reverse + rotate |
| **Gripper drops ball** | Test gripper force; add delay after close |
| **Boundary crossing** | Conservative yellow threshold; emergency stop |
| **Arm collision** | Predefined safe poses; test all motions |
| **Battery dies** | Fresh battery per run; voltage monitoring |

---

## 📊 Success Metrics

### Minimum Viable Performance (MVP)
- ✅ Detect and approach 1 ball
- ✅ Pick up ball with arm
- ✅ Navigate to basket
- ✅ Drop ball in basket
- ✅ Avoid 1 obstacle
- ✅ No boundary crossings

### Target Performance
- 🎯 Collect 10+ balls in 5 minutes
- 🎯 Zero collisions
- 🎯 Detect all 3 ball colors
- 🎯 Autonomous basket finding

### Stretch Goals
- 🚀 Collect 15+ balls
- 🚀 Complete in < 3 minutes
- 🚀 Path optimization (nearest ball first)

---

## 🔧 Troubleshooting

### Common Issues

**Camera not working:**
```bash
sudo pkill -f gst-launch
# Kernel → Shutdown All Kernels → reopen notebook
```

**Servos not responding:**
```bash
sudo chmod 777 /dev/ttyTHS1
# Restart kernel
```

**Ball detection fails:**
- Check lighting conditions
- Adjust HSV ranges in config.yaml
- Verify camera focus

**Arm doesn't pick up ball:**
- Run `calibrate_pickup_height()` in arm.py
- Adjust shoulder angle in config.yaml
- Test gripper force

---

## 📝 Competition Day Workflow

1. **Power on** (60s boot time)
2. **Connect** to WiFi and Jupyter
3. **Run calibration** (basket + colors)
4. **Test hardware** (diagnostics notebook)
5. **Practice run** (1-2 times)
6. **Tune parameters** based on results
7. **Competition run** (5 minutes)
8. **Log results** for analysis

---

## 📚 References

- [JETANK GitHub](https://github.com/waveshare/JETANK)
- [OpenCV HSV Color Detection](https://docs.opencv.org/4.x/df/d9d/tutorial_py_colorspaces.html)
- [Jetson Nano Docs](https://developer.nvidia.com/embedded/jetson-nano-developer-kit)

---

**Last Updated:** June 20, 2026  
**Status:** Implementation Complete — Ready for Testing
