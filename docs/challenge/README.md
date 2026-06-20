# Challenge: Autonomous Mobile Robot with Vision & Manipulation

## Overview

Develop an autonomous navigation and manipulation system for the **JETANK AI Kit**, a tracked mobile robot built on the NVIDIA Jetson Nano. The robot must perceive its environment through computer vision, navigate autonomously, avoid obstacles, and optionally interact with objects using its 4‑DOF robotic arm.

---

## Problem Statement

Build a software stack that enables the JETANK robot to:
1. **See** — process live camera feeds for road following, object detection, and color recognition.
2. **Navigate** — follow paths, avoid collisions, and reach target waypoints.
3. **Interact** — (if arm equipped) detect, track, and manipulate objects within reach.
4. **Teleoperate** — provide a reliable manual control fallback via gamepad or remote interface.

---

## Hardware Constraints

The solution must run on the following hardware platform:

---

# JETANK AI Kit — Full Hardware Specification

## 1. Overview

The JETANK AI Kit is a tracked mobile robot platform designed for NVIDIA Jetson Nano–based AI projects, including computer vision, autonomous navigation, and robotic manipulation.

---

## 2. Mechanical Structure

### 2.1 Body Dimensions
- **Total Length:** ~260 mm
- **Total Width:** ~200 mm
- **Total Height:** ~140 mm (without arm)
- **Ground Clearance:** ~25 mm
- **Track Width:** ~40 mm each
- **Wheelbase:** ~160 mm

### 2.2 Chassis Material
- CNC‑machined aluminum alloy
- High‑strength acrylic top plate

---

## 3. Motors & Servos

### 3.1 Drive Motors
- **Type:** Dual high‑torque DC gear motors
- **Voltage:** 6–12 V
- **Encoder:** Yes (optical encoder)
- **Motor Count:** 2

### 3.2 Servo Motors (Arm Version Only)
If you have the **4‑DOF robotic arm version**, it includes:

| Joint | Servo Model | Count | Rotation Range |
|------|-------------|--------|----------------|
| Base rotation | MG996R | 1 | 180° |
| Shoulder | MG996R | 1 | 180° |
| Elbow | MG996R | 1 | 180° |
| Gripper | SG90 | 1 | 90° |

- **Total Servos:** 4
- **Total DOF:** 4

---

## 4. Sensors

### 4.1 Vision
- **Camera:** 8MP IMX219 (Jetson Nano CSI camera)
- **FOV:** 160° wide‑angle
- **Resolution:** 3280×2464

### 4.2 IMU
- **6‑axis IMU:** Accelerometer + Gyroscope

### 4.3 Other Sensors
- Motor encoders
- Optional ultrasonic module (depending on kit version)

---

## 5. Electronics

### 5.1 Main Controller
- **NVIDIA Jetson Nano** (2GB or 4GB depending on kit)

### 5.2 Motor Driver
- **TB6612FNG dual‑channel driver**

### 5.3 Power System
- **Battery:** 2‑cell or 3‑cell Li‑ion pack (7.4–11.1 V)
- **Runtime:** 60–120 minutes depending on load

---

## 6. Distances & Clearances

### 6.1 Camera Height
- **Camera height from ground:** ~120 mm

### 6.2 Arm Reach (Arm Version)
- **Max forward reach:** ~180 mm
- **Max vertical reach:** ~160 mm
- **Gripper opening:** 55 mm

---

## 7. Weight

- **Base robot:** ~1.2 kg
- **With arm:** ~1.5 kg

---

## 8. Included Components

- Tracked chassis
- Jetson Nano carrier board
- 8MP CSI camera
- Motor driver
- IMU
- Battery holder
- Optional 4‑DOF robotic arm
- Acrylic + aluminum frame

---

## Goals

- [ ] Implement real-time road following using the CSI camera.
- [ ] Integrate collision avoidance using vision and/or ultrasonic sensors.
- [ ] Deploy object detection and tracking models optimized for Jetson Nano.
- [ ] (Optional) Achieve basic pick-and-place with the 4‑DOF arm.
- [ ] Provide smooth teleoperation via gamepad control.

---

## Success Criteria

- Robot successfully follows a defined path for at least 2 minutes without human intervention.
- Collision avoidance triggers correctly when obstacles are placed within 30 cm.
- Vision pipeline runs at ≥ 15 FPS on the Jetson Nano.
- (Optional) Arm can reliably grasp and reposition a target object within its reach envelope.
