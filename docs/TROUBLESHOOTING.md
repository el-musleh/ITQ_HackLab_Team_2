# Troubleshooting Guide — ITQ Bottle Cap Collector

**Quick fixes for common issues**

---

## 🎥 Camera Issues

### Camera Not Initializing

**Symptoms:**
- "Could not initialize camera" error
- Black screen in notebooks
- `camera.value is None`

**Solutions:**

1. **Kill existing camera processes:**
```bash
# In Jupyter Terminal
sudo pkill -f gst-launch
```

2. **Shutdown all kernels:**
```
Kernel → Shutdown All Kernels
Close all notebook tabs
Reopen notebook
```

3. **Check camera cable:**
- Power off robot
- Reseat CSI camera cable
- Power on, wait 60s

4. **Test with simple capture:**
```python
import cv2
cap = cv2.VideoCapture(0)
ret, frame = cap.read()
print(f"Capture: {ret}, Shape: {frame.shape if ret else 'None'}")
cap.release()
```

---

## 🔧 Servo Issues

### Servos Not Responding

**Symptoms:**
- "Permission denied: /dev/ttyTHS1"
- Servos don't move
- Import error on SCSCtrl

**Solutions:**

1. **Fix permissions:**
```bash
# In Jupyter Terminal
sudo chmod 777 /dev/ttyTHS1
```

2. **Restart kernel:**
```
Kernel → Restart Kernel
Re-run import cells
```

3. **Test servo manually:**
```python
from src.SCSCtrl import TTLServo
TTLServo.servoAngleCtrl(1, 0, 1, 150)  # Pan to center
```

4. **Check servo power:**
- Verify 6-7.4V power to servo board
- Check battery voltage
- Ensure servo board LED is on

### Servo Jitters or Overheats

**Cause:** ID conflict or overload

**Solutions:**
1. Verify each servo has unique ID (1-6)
2. Reduce speed: `TTLServo.servoAngleCtrl(id, angle, 1, 80)`
3. Check for mechanical binding

---

## 🚗 Motor Issues

### Motors Not Moving

**Symptoms:**
- `robot.left_motor.value = 0.5` does nothing
- Robot doesn't respond to commands

**Solutions:**

1. **Test motor driver:**
```python
from jetbot import Robot
robot = Robot()
robot.left_motor.value = 0.2
robot.right_motor.value = 0.2
# Should move forward
robot.stop()
```

2. **Check I2C connection:**
```bash
# In Jupyter Terminal
sudo i2cdetect -y 1
# Look for 0x60 or 0x70
```

3. **Verify battery:**
- Check battery voltage (> 7V)
- Ensure battery switch is ON
- Try fresh battery

### Motors Spin Wrong Direction

**Solution:**
- Swap motor wires on terminal block
- OR adjust in code (multiply by -1)

---

## 👁️ Perception Issues

### No Balls Detected

**Symptoms:**
- `balls = []` always
- Ball in frame but not detected

**Solutions:**

1. **Check lighting:**
```python
# Run in 02_test_perception.ipynb, Section 5
# Place ball in center, check HSV values
```

2. **Adjust HSV ranges:**
```yaml
# In config.yaml
balls:
  colors:
    blue:
      hsv_lower: [90, 120, 40]   # Widen range
      hsv_upper: [140, 255, 255]
```

3. **Lower minimum area:**
```yaml
balls:
  min_area_px: 50  # Was 100
```

4. **Test with single color:**
```python
# Temporarily disable other colors
balls = ball_detector.detect(frame)
# Only test blue first
```

### False Positives (Detecting Non-Balls)

**Solutions:**

1. **Increase minimum area:**
```yaml
balls:
  min_area_px: 150  # Was 100
```

2. **Enable validation:**
```python
balls = ball_detector.detect(frame)
validated = ball_detector.validate_detection(balls)
# Use validated instead of balls
```

3. **Tighten HSV range:**
```yaml
# Reduce ±20 to ±10 for H
# Reduce ±50 to ±30 for S/V
```

### Basket Not Found

**Symptoms:**
- `basket['basket_found'] = False`
- Basket visible but not detected

**Solutions:**

1. **Re-run calibration:**
```
Open: notebooks/00_calibrate_basket.ipynb
Position robot closer (~20 cm)
Run all cells
```

2. **Adjust gray HSV:**
```yaml
basket:
  hsv_lower: [0, 0, 40]   # Lower V threshold
  hsv_upper: [180, 60, 220]  # Higher S threshold
```

3. **Check calibration saved:**
```python
import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)
print(config['basket'])
# Should show size_px, location_x, location_y
```

### Obstacle Detection Too Sensitive

**Symptoms:**
- Constantly avoiding when no obstacle
- Yellow pixels always > threshold

**Solutions:**

1. **Increase threshold:**
```yaml
obstacles:
  threshold_px: 2200  # Was 1800
  edge_threshold: 600  # Was 500
```

2. **Check camera angle:**
```python
camera_ctrl.set_tilt(-20)  # Look down more
```

---

## 🤖 State Machine Issues

### Robot Stuck in One State

**Symptoms:**
- Always in SEARCH
- Never transitions

**Solutions:**

1. **Check perception data:**
```python
# In 06_full_run.ipynb, add debug print
print(f"Balls: {len(validated_balls)}")
print(f"Basket: {basket['basket_found']}")
```

2. **Reset state machine:**
```python
state_machine.reset()
```

3. **Check timeouts:**
```yaml
# In config.yaml, increase if needed
state_machine:
  approach_timeout: 8  # Was 5
  search_timeout: 15   # Was 10
```

### Robot Won't Collect Ball

**Symptoms:**
- Approaches but doesn't trigger COLLECT
- Never enters pickup sequence

**Solutions:**

1. **Check distance threshold:**
```python
# In state_machine.py, _handle_approach()
# Line: if distance < 15:
# Try: if distance < 20:  # Increase threshold
```

2. **Test arm manually:**
```python
from src.hardware.arm import ArmController
arm = ArmController(config)
arm.pickup_sequence()
```

---

## 🎮 Navigation Issues

### Robot Moves Too Fast

**Solution:**
```yaml
motors:
  max_speed: 0.18      # Reduce from 0.25
  approach_speed: 0.12  # Reduce from 0.15
```

### Robot Doesn't Track Ball Smoothly

**Symptoms:**
- Oscillates left/right
- Overshoots target

**Solutions:**

1. **Tune PID gains:**
```yaml
pid:
  kp: 2.0   # Reduce from 3.0
  kd: 0.8   # Increase from 0.5
```

2. **Lower approach speed:**
```yaml
motors:
  approach_speed: 0.10
```

### Robot Gets Stuck in Corners

**Solutions:**

1. **Enable recovery:**
```python
# Already implemented in recovery.py
# Check it's being called in main loop
```

2. **Increase avoidance timeout:**
```python
# In state_machine.py
self.avoid_timeout = 3.0  # Was 2.0
```

---

## 🦾 Arm Issues

### Arm Doesn't Pick Up Ball

**Symptoms:**
- Gripper closes on empty space
- Ball too far/high/low

**Solutions:**

1. **Calibrate pickup height:**
```python
from src.hardware.arm import ArmController
arm = ArmController(config)
arm.calibrate_pickup_height([-35, -40, -45, -50])
# Test different shoulder angles
```

2. **Adjust pickup pose:**
```yaml
arm_poses:
  pickup: [0, -45, -65, 0]  # Lower shoulder & elbow
```

3. **Test gripper force:**
```python
arm.gripper_close()
# Should hold ball firmly
# If not, check servo power
```

### Gripper Drops Ball

**Solutions:**

1. **Increase close angle:**
```yaml
arm_poses:
  carry: [0, 20, 30, 95]  # 95° instead of 90°
```

2. **Add delay after close:**
```python
# In arm.py, pickup_sequence()
# After gripper_close()
time.sleep(0.8)  # Was 0.5
```

### Arm Collides with Chassis

**Solution:**
```yaml
arm_poses:
  home: [0, 10, 10, 0]  # Lift slightly
  carry: [0, 25, 35, 90]  # Higher carry
```

---

## 💻 Software Issues

### Import Errors

**Symptoms:**
- `ModuleNotFoundError: No module named 'perception'`

**Solutions:**

1. **Check sys.path:**
```python
import sys, os
# Auto-detect project root by searching for config.yaml marker
project_root = os.getcwd()
while not os.path.exists(os.path.join(project_root, 'config.yaml')) and project_root != '/':
    project_root = os.path.dirname(project_root)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
```

2. **Verify file exists:**
```bash
ls -la perception/ball_detector.py
```

### Kernel Crashes

**Symptoms:**
- Notebook freezes
- "Kernel died" message

**Solutions:**

1. **Reduce memory usage:**
```python
# Lower camera resolution
camera_ctrl = CameraController({'camera': {'width': 224, 'height': 224}})
```

2. **Restart kernel frequently:**
```
Kernel → Restart Kernel
Re-run setup cells
```

3. **Close other notebooks:**
- Only run one notebook at a time
- Shutdown unused kernels

### Config Not Loading

**Symptoms:**
- `KeyError` when accessing config
- Default values used instead

**Solutions:**

1. **Check YAML syntax:**
```bash
# In Jupyter Terminal
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

2. **Verify file path:**
```python
import os
# Auto-detect project root by searching for config.yaml marker
project_root = os.getcwd()
while not os.path.exists(os.path.join(project_root, 'config.yaml')) and project_root != '/':
    project_root = os.path.dirname(project_root)
config_path = os.path.join(project_root, 'config.yaml')
print(f"Exists: {os.path.exists(config_path)}")
```

---

## 🔋 Power Issues

### Robot Shuts Down Randomly

**Cause:** Low battery

**Solutions:**
1. Charge battery fully (11.1V)
2. Use fresh battery for competition
3. Monitor voltage during run

### Servos Weak or Slow

**Cause:** Insufficient servo power

**Solutions:**
1. Check servo power supply (6-7.4V)
2. Ensure battery > 7V
3. Reduce servo speed if overheating

---

## 🆘 Emergency Procedures

### Robot Out of Control

```python
# EMERGENCY STOP
from jetbot import Robot
robot = Robot()
robot.stop()

from src.hardware.arm import ArmController
arm = ArmController()
arm.home()
```

### Complete System Reset

```bash
# In Jupyter Terminal
sudo reboot
# Wait 60 seconds
# Reconnect to Jupyter
# Re-run calibration
```

### Backup Plan (Manual Mode)

If autonomous fails:
1. Use `JETANK_6_gamepadCtrl/` for manual control
2. Drive manually to collect balls
3. Better than zero score!

---

## 📞 Quick Reference

### Test Commands

```python
# Test camera
frame = camera_ctrl.read()
print(f"Frame: {frame.shape if frame is not None else 'None'}")

# Test motors
robot.forward(0.2)
time.sleep(1)
robot.stop()

# Test servos
TTLServo.servoAngleCtrl(1, 0, 1, 150)

# Test perception
balls = ball_detector.detect(frame)
print(f"Balls: {len(balls)}")

# Test state machine
response = state_machine.update(perception_data)
print(response['message'])
```

### Reset Commands

```python
# Reset state machine
state_machine.reset()

# Reset PID
navigator.pid.reset()

# Stop everything
robot.stop()
arm.home()
```

---

**Remember:** Stay calm, test systematically, and use the diagnostic notebook!
