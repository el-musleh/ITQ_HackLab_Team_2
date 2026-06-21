# Implementation Summary — ITQ Bottle Cap Collector

**Date:** June 20, 2026  
**Status:** ✅ Complete — Ready for Testing  
**Team:** Team 2

---

## 🎯 Challenge Requirements

Build an autonomous robot to:
- Navigate 175×180 cm arena
- Collect ~22 colored balls (blue, red, silver)
- Avoid yellow-taped obstacles (2 crates)
- Deposit balls in gray basket (center)
- Complete within 5 minutes
- Zero collisions

---

## ✅ Implementation Complete

### Phase 1: Perception Module ✓

**Created:**
1. **`src/perception/ball_detector.py`** — Multi-color ball detection
   - HSV segmentation for blue, red, silver
   - Contour detection with circularity filter
   - Multi-frame validation (3 frames)
   - Distance estimation from pixel area
   - Methods: `detect()`, `validate_detection()`, `draw_detections()`

2. **`src/perception/obstacle_detector.py`** — Yellow tape & edge detection
   - Boundary detection (bottom 30% ROI)
   - Obstacle detection (front 15-65% ROI)
   - Turn direction logic (left/right/reverse)
   - Combined detection with priority
   - Methods: `detect_boundary()`, `detect_obstacle()`, `detect_combined()`

3. **`src/perception/basket_detector.py`** — Gray basket localization
   - HSV-based gray detection
   - Calibration system (10-frame average)
   - Bearing angle calculation
   - Distance estimation
   - Methods: `calibrate()`, `detect()`, `is_aligned()`

### Phase 2: Control Module ✓

**Created:**
1. **`src/control/state_machine.py`** — Main FSM
   - States: STARTUP, SEARCH, APPROACH, COLLECT, RETURN, DEPOSIT, AVOID_BOUNDARY, AVOID_OBSTACLE, STOPPED
   - Transition logic with timeouts
   - Priority handling (boundary > obstacle)
   - Ball tracking and collection counter
   - Method: `update(perception_data)` → action commands

2. **`src/control/pid.py`** — PID controller
   - Single PID for 1D tracking
   - Dual PID for X/Y tracking
   - Anti-windup integral limiting
   - Configurable gains (kp, ki, kd)
   - Method: `update(measurement)` → control output

3. **`src/control/navigator.py`** — Motion planning
   - Action execution (approach, return, rotate, avoid)
   - PID-based target tracking
   - Speed limiting and safety
   - Differential drive control
   - Methods: `execute_action()`, `approach_target()`, `return_to_basket()`

4. **`src/control/recovery.py`** — Stuck detection
   - Timeout-based stuck detection
   - Recovery sequence (reverse → turn)
   - Alternating turn direction
   - Method: `execute_recovery()` → recovery action

### Phase 3: Hardware Module ✓

**Created:**
1. **`src/hardware/arm.py`** — 4-DOF arm control
   - Predefined poses: HOME, PICKUP, CARRY, DEPOSIT
   - Pickup sequence (open → lower → close → lift)
   - Deposit sequence (position → open → home)
   - Individual joint control
   - Calibration helper
   - Methods: `pickup_sequence()`, `deposit_sequence()`

2. **`src/hardware/chassis.py`** — Motor control wrapper
   - Speed clamping (max 0.25)
   - Motor value tracking
   - Basic motion primitives
   - Methods: `set_motors()`, `forward()`, `backward()`, `turn_left()`, `turn_right()`

3. **`src/hardware/camera.py`** — Camera interface
   - JetBot camera with OpenCV fallback
   - Pan/tilt servo control
   - Frame capture
   - Camera positioning (center, look_down, look_forward)
   - Methods: `initialize()`, `read()`, `set_pan()`, `set_tilt()`

### Phase 4: Integration & Testing ✓

**Created:**
1. **`notebooks/00_calibrate_basket.ipynb`** — Basket calibration
   - Interactive positioning
   - 10-frame capture
   - Average size/location calculation
   - Save to config.yaml
   - Visual verification

2. **`notebooks/02_test_perception.ipynb`** — Perception testing
   - Live detection test
   - Continuous feed with overlays
   - HSV tuning helper
   - Status display

3. **`notebooks/06_full_run.ipynb`** — Autonomous run
   - Complete system initialization
   - State machine loop
   - Action execution
   - Telemetry logging
   - Start/stop controls

4. **`config.yaml`** — Updated configuration
   - Arena dimensions
   - Multi-color ball HSV ranges
   - Basket parameters (calibrated)
   - Obstacle thresholds
   - Motor speeds
   - Arm poses
   - PID gains

### Documentation ✓

**Created:**
1. **`docs/challenge/ITQ-CHALLENGE-SPEC.md`** — Complete challenge specification
2. **`docs/QUICK-START.md`** — 5-minute competition day guide
3. **`IMPLEMENTATION-SUMMARY.md`** — This file

---

## 📁 File Structure

```
ITQ_HackLab_Team_2/
├── perception/
│   ├── __init__.py
│   ├── ball_detector.py          ✓ NEW
│   ├── obstacle_detector.py      ✓ NEW
│   └── basket_detector.py        ✓ NEW
│
├── control/
│   ├── __init__.py
│   ├── state_machine.py          ✓ NEW
│   ├── pid.py                    ✓ NEW
│   ├── navigator.py              ✓ NEW
│   └── recovery.py               ✓ NEW
│
├── hardware/
│   ├── __init__.py
│   ├── arm.py                    ✓ NEW
│   ├── chassis.py                ✓ NEW
│   └── camera.py                 ✓ NEW
│
├── notebooks/
│   ├── 00_calibrate_basket.ipynb ✓ NEW
│   ├── 02_test_perception.ipynb  ✓ NEW
│   └── 06_full_run.ipynb         ✓ NEW
│
├── docs/
│   ├── challenge/
│   │   └── ITQ-CHALLENGE-SPEC.md ✓ NEW
│   └── QUICK-START.md            ✓ NEW
│
├── config.yaml                   ✓ UPDATED
└── IMPLEMENTATION-SUMMARY.md     ✓ NEW
```

---

## 🔧 Technical Specifications

### Perception
- **Ball Detection:** 3 colors (blue, red, silver) via HSV
- **Validation:** 3-frame consensus
- **Distance:** Estimated from pixel area
- **Frame Rate:** 15-30 fps target

### Control
- **State Machine:** 9 states with priority interrupts
- **PID:** Dual controller (X/Y) for smooth tracking
- **Navigation:** Reactive obstacle avoidance
- **Recovery:** Timeout-based stuck detection

### Hardware
- **Motors:** Max speed 0.25, approach 0.15, min crawl 0.05 (distance-ramped)
- **Servos:** 6 servos (pan, tilt, 4-DOF arm)
- **Camera:** 320×240 @ 30fps
- **Arm:** 4 predefined poses

---

## 🎯 Key Features

1. **Multi-Color Detection** — Handles blue, red, and silver balls
2. **Robust Validation** — Multi-frame consensus reduces false positives
3. **Priority Avoidance** — Boundary > obstacle > normal operation
4. **Smooth Tracking** — PID controller for precise approach with distance-based speed ramping (fast when far, gradual deceleration near ball)
5. **Autonomous Calibration** — Basket learning at startup
6. **Modular Design** — Each component independently testable
7. **Safety Limits** — Speed clamping, servo angle limits
8. **Recovery System** — Automatic stuck detection and escape
9. **Trapezoidal Arm Motion** — Servo movements use accel/cruise/decel velocity profile for smooth operation
10. **SafetyMonitor** — Proactive detection of stuck (motor vs displacement), dark frames (vision blackout), and arm collisions (visual pre-check + physics + timeout)

---

## 🧪 Testing Strategy

### Unit Testing
- [x] Ball detector with sample images
- [x] Obstacle detector with yellow tape
- [x] Basket detector with gray objects
- [x] State machine transitions (logic only)
- [x] PID controller response
- [x] SafetyMonitor detectors (StuckDetector, DarkFrameDetector, ArmCollisionDetector)
- [x] SafetyMonitor priority and aggregation

### Integration Testing
- [ ] Camera + perception pipeline
- [ ] State machine + navigator
- [ ] Arm sequences (pickup/deposit)
- [ ] Full system loop

### System Testing
- [ ] Calibration workflow
- [ ] Single ball collection
- [ ] Multiple ball collection
- [ ] Obstacle avoidance
- [ ] Basket return
- [ ] Full 5-minute run

---

## 📊 Expected Performance

### Baseline (Conservative)
- **Balls:** 5-8 collected
- **Time:** Full 5 minutes
- **Collisions:** 0
- **Success Rate:** 80% pickup, 90% deposit

### Target (Optimized)
- **Balls:** 10-15 collected
- **Time:** 3-4 minutes
- **Collisions:** 0
- **Success Rate:** 90% pickup, 95% deposit

### Stretch (Perfect)
- **Balls:** 18+ collected
- **Time:** < 3 minutes
- **Collisions:** 0
- **Success Rate:** 95% pickup, 98% deposit

---

## ⚠️ Known Limitations

1. **No Encoder Feedback** — Stuck detection uses motor commands vs pose displacement (SafetyMonitor)
2. **No Ultrasonic** — Relies purely on vision for obstacle detection
3. **Fixed Arm Poses** — May need on-site tuning for pickup height
4. **Lighting Sensitivity** — HSV ranges require calibration
5. **Single Ball Tracking** — Doesn't optimize for nearest ball
6. **No Path Planning** — Reactive navigation only

---

## 🚀 Next Steps (On-Site)

### Day 1: Setup & Calibration
1. Power on robot, verify hardware
2. Run `robot_tests/robot_diagnostics.ipynb`
3. Calibrate basket (`00_calibrate_basket.ipynb`)
4. Test perception (`02_test_perception.ipynb`)
5. Tune HSV ranges for arena lighting

### Day 2: Testing & Tuning
1. Test arm pickup/deposit sequences
2. Practice runs (3-5 times)
3. Tune PID gains if needed
4. Adjust arm poses if pickup fails
5. Optimize motor speeds

### Day 3: Competition
1. Fresh battery
2. Quick calibration check
3. 1 practice run
4. Competition run
5. Log results

---

## Recent Enhancements (June 21, 2026)

### Out-of-Bounds Ball Handling ✓

**Problem:** Robot would attempt to collect balls detected by camera but whose estimated world position was outside the arena boundary.

**Solution:** `CHECK_FOR_BALL` now iterates all detected balls (sorted by distance) and skips any whose world position is outside arena bounds (rejected by `WorldMap.register_ball`). If yellow boundary tape is visible in the same frame, the ball is confirmed outside. Tries remaining balls before falling through to `BALLS_LEFT`/`BLIND_SPOT`/`END`.

**Files modified:** `src/control/state_machine.py`, `tests/mocks.py`, `tests/test_state_machine.py`

### Ball Detection Robustness ✓

**Problem:** HSV-based detection was vulnerable to false positives from glare, reflections, and bright surfaces. No size limit relative to claw capacity.

**Solution:** Five improvements:
1. **Multi-frame validation** — `validate_detection()` (3 consecutive frames) wired into all 4 detection call sites
2. **Max size check** — Objects with estimated real diameter > 5cm (claw limit) rejected via pinhole model
3. **Aspect ratio check** — Bounding box `w/h` must be 0.6–1.4 (balls are roughly square)
4. **Obstacle cross-validation** — Ball detections overlapping yellow tape pixels rejected via `ObstacleDetector.get_yellow_mask()`
5. **Tighter silver HSV** — `V_min` 150→180, `S_max` 30→25 to reduce bright surface false positives

**Files modified:** `src/perception/ball_detector.py`, `src/perception/obstacle_detector.py`, `src/control/state_machine.py`, `config.yaml`, `tests/mocks.py`, `tests/test_state_machine.py`

### YOLOv8 Future Enhancement (Documented)

YOLOv8n with TensorRT is feasible on Jetson Nano (10-15 FPS) and would improve detection robustness in varied lighting. The `ultralytics` package is already installed. See `docs/yolov8-future-enhancement.md` for full feasibility analysis, comparison table, and integration approach.

**Status:** Documented only — not implemented. HSV detection with robustness improvements is sufficient for competition.

### Distance-Based Speed Ramping ✓

**Problem:** Robot approached balls at a fixed speed (0.15) regardless of distance — too slow when far, too fast when close, risking overshoot or collision. Arm servos also moved at constant speed with no acceleration/deceleration profile.

**Solution:** Two improvements:

1. **Chassis distance ramping** — `_distance_to_speed(distance)` in `state_machine.py` linearly interpolates approach speed between `min_approach_speed` (0.05) and `max_speed` (0.25) based on ball distance. Far balls (>50cm) get full speed; close balls (<15cm) get crawl speed; in between gets linear ramp. Replaces the fixed `approach_speed` multiplier in `_sub_approach()`.

2. **Arm trapezoidal velocity profile** — `move_to_pose_ramped()` in `arm.py` breaks servo movements into N interpolation steps with a trapezoidal speed profile: accelerate (0-30%), cruise (30-70%), decelerate (70-100%). `pickup_sequence()` and `deposit_sequence()` now use the ramped version for all pose transitions.

**Config additions:** `motors.min_approach_speed`, `motors.far_distance_threshold`, `motors.close_distance_threshold`

**Files modified:** `src/control/state_machine.py`, `src/hardware/arm.py`, `config.yaml`, `tests/test_speed_ramp.py`

---

## 📝 Configuration Tuning Guide

### If balls not detected:
```yaml
balls.colors.[color].hsv_lower: [H-10, S-30, V-30]
balls.colors.[color].hsv_upper: [H+10, S+30, V+30]
```

### If robot too slow:
```yaml
motors.approach_speed: 0.20  # Increase
motors.search_speed: 0.15    # Increase
motors.far_distance_threshold: 40.0  # Reach full speed sooner
```

### If robot too fast (unsafe):
```yaml
motors.max_speed: 0.20       # Decrease
motors.approach_speed: 0.12  # Decrease
motors.min_approach_speed: 0.03  # Slower crawl near ball
motors.close_distance_threshold: 20.0  # Start slowing earlier
```

### If arm doesn't reach ball:
```yaml
arm_poses.pickup: [0, -45, -65, 0]  # Lower shoulder/elbow
```

### If obstacle avoidance too sensitive:
```yaml
obstacles.threshold_px: 2200    # Increase
obstacles.edge_threshold: 600   # Increase
```

---

## 🏆 Success Criteria

- [x] **Code Complete** — All modules implemented
- [ ] **Hardware Tested** — All components verified
- [ ] **Calibration Done** — Basket + colors tuned
- [ ] **Practice Run** — At least 1 ball collected
- [ ] **Competition Ready** — Full autonomous run

---

## 📚 References

- **Plan:** `~/.windsurf/plans/itq-bottle-cap-challenge-plan-dc18ff.md`
- **Spec:** `docs/challenge/ITQ-CHALLENGE-SPEC.md`
- **Quick Start:** `docs/QUICK-START.md`
- **Config:** `config.yaml`

---

**Status:** Implementation complete. Ready for hardware testing and on-site calibration.

**Estimated Time to Competition Ready:** 2-3 hours (calibration + testing)

**Confidence Level:** High — All core functionality implemented and modular design allows easy debugging.
