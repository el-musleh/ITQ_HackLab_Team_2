# Hardware API Quick Reference

**One-page guide for switching between simulation and hardware**

---

## 🔄 Switch Between Sim and Hardware

```python
# CHANGE THIS ONE LINE:
USE_SIMULATION = True  # False for hardware

if USE_SIMULATION:
    from src.simulation import ChassisController, ArmController, CameraController
else:
    from src.hardware.chassis import ChassisController
    from src.hardware.arm import ArmController
    from src.hardware.camera import CameraController

# REST IS IDENTICAL!
```

---

## 🚗 ChassisController

```python
chassis = ChassisController(robot_id, max_speed=0.25)

chassis.forward(speed=0.15)
chassis.backward(speed=0.15)
chassis.turn_left(speed=0.10)
chassis.turn_right(speed=0.10)
chassis.stop()

left, right = chassis.get_motor_values()
```

---

## 🦾 ArmController

```python
arm = ArmController(robot_id, config)

# Gripper
arm.gripper_open()   # Returns True/False
arm.gripper_close()  # Returns True/False

# Poses
arm.home()
arm.move_to_pose([0, -35, -55, -25], speed=150)

# Predefined
arm.pose_home      # [0, 0, 0, 0]
arm.pose_pickup    # [0, -35, -55, -25]
arm.pose_carry     # [0, 15, 25, 50]
arm.pose_deposit   # [0, 35, 35, 35]

# Status
pose = arm.get_current_pose()
```

---

## 📷 CameraController

```python
camera = CameraController(config, robot_id=robot_id)

camera.initialize()
frame = camera.read()  # BGR numpy array

camera.center()
camera.look_down()
camera.look_forward()

width, height = camera.get_frame_size()
```

---

## 📝 Complete Example

```python
# Works on BOTH simulation and hardware!

# Movement
chassis.forward(0.15)
time.sleep(2)
chassis.stop()

# Arm
arm.gripper_open()
arm.move_to_pose(arm.pose_pickup)
time.sleep(1)
arm.gripper_close()
arm.move_to_pose(arm.pose_carry)

# Camera
frame = camera.read()
cv2.imshow('View', frame)
```

---

## ⚠️ Method Name Changes

| Old (Sim Only) | New (Hardware Compatible) |
|----------------|---------------------------|
| `open_claw()` | `gripper_open()` |
| `close_claw()` | `gripper_close()` |
| `SimChassis` | `ChassisController` |
| `SimArm` | `ArmController` |
| `SimCamera` | `CameraController` |

---

## 📚 Documentation

- Full guide: `HARDWARE-API-COMPATIBILITY.md`
- Example: `example_hardware_switch.py`
- Implementation: `IMPLEMENTATION-COMPLETE.md`

---

**✅ Ready to deploy to hardware with ZERO code changes!**
