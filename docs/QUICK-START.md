# Quick Start Guide — ITQ Bottle Cap Collector

**5-Minute Setup for Competition Day**

---

## 🚀 Pre-Competition Checklist

### Hardware
- [ ] Battery fully charged
- [ ] Robot powered on (wait 60s for boot)
- [ ] Camera cable connected
- [ ] All servos responding
- [ ] Motors working

### Software
- [ ] Connected to WiFi: `TP-LINK_744C` (password: `15253354`)
- [ ] Jupyter Lab open: `http://192.168.0.100:8888/lab`
- [ ] Password entered: `CIC@Tics1XAI`

---

## 📋 Competition Day Workflow

### Step 1: Basket Calibration (2 minutes)

```
1. Open: notebooks/00_calibrate_basket.ipynb
2. Position robot ~30 cm from basket
3. Run all cells
4. Verify: "Calibration saved to config.yaml"
```

### Step 2: Test Perception (1 minute)

```
1. Open: notebooks/02_test_perception.ipynb
2. Run Section 3 (Live Detection Test)
3. Verify:
   - Balls detected (all colors)
   - Basket found
   - Yellow tape detected
```

**If detection fails:**
- Adjust HSV ranges in Section 5
- Update `config.yaml` with new values

### Step 3: Test Arm (1 minute)

```
1. Open: notebooks/03_test_arm.ipynb (if exists)
   OR run in terminal:
   
from src.hardware.arm import ArmController
import yaml

with open('config.yaml') as f:
    config = yaml.safe_load(f)

arm = ArmController(config)
arm.pickup_sequence()  # Test pickup
arm.deposit_sequence() # Test deposit
```

### Step 4: Practice Run (2-3 minutes)

```
1. Open: notebooks/06_full_run.ipynb
2. Run setup cells (1-5)
3. Click START
4. Observe for 30-60 seconds
5. Click STOP
6. Check: Did it collect at least 1 ball?
```

### Step 5: Competition Run (5 minutes)

```
1. Fresh notebook kernel (Kernel → Restart)
2. Run setup cells
3. Click START
4. Let it run for full 5 minutes
5. Record: balls collected
```

---

## ⚙️ Quick Tuning

### Ball Detection Not Working?

**Check lighting:**
```python
# In 02_test_perception.ipynb, Section 5
# Place ball in center, run cell
# Copy suggested HSV range to config.yaml
```

**Update config.yaml:**
```yaml
balls:
  colors:
    blue:
      hsv_lower: [YOUR_H-20, YOUR_S-50, YOUR_V-50]
      hsv_upper: [YOUR_H+20, YOUR_S+50, YOUR_V+50]
```

### Arm Not Picking Up?

**Adjust pickup height:**
```yaml
arm_poses:
  pickup: [0, -45, -60, 0]  # Try -45 instead of -40
```

### Robot Too Fast/Slow?

```yaml
motors:
  max_speed: 0.20      # Lower = slower (safer)
  approach_speed: 0.12 # Lower = more precise
```

### Obstacle Avoidance Too Sensitive?

```yaml
obstacles:
  threshold_px: 2000   # Higher = less sensitive
  edge_threshold: 600  # Higher = less sensitive
```

---

## 🐛 Emergency Troubleshooting

### Camera Not Working
```bash
# In Jupyter Terminal:
sudo pkill -f gst-launch
# Then: Kernel → Shutdown All Kernels → Reopen notebook
```

### Servos Not Responding
```bash
# In Jupyter Terminal:
sudo chmod 777 /dev/ttyTHS1
# Then: Restart kernel
```

### Robot Stuck/Unresponsive
```python
# In any notebook cell:
from jetbot import Robot
robot = Robot()
robot.stop()

from src.hardware.arm import ArmController
arm = ArmController()
arm.home()
```

### Reset Everything
```bash
# In Jupyter Terminal:
sudo reboot
# Wait 60s, reconnect to Jupyter
```

---

## 📊 Expected Performance

### Minimum (MVP)
- 1-3 balls collected
- No collisions
- Completes pickup + deposit cycle

### Good
- 5-10 balls collected
- Smooth navigation
- Reliable detection

### Excellent
- 10+ balls collected
- Fast cycle time
- All colors detected

---

## 🎯 Competition Strategy

1. **Safety First:** Avoid collisions (penalty!)
2. **Nearest Ball:** Approach closest ball first
3. **Color Priority:** If multiple balls, prioritize blue (easiest to detect)
4. **Time Management:** Don't waste time on stuck balls
5. **Basket Returns:** Quick deposit, back to searching

---

## 📝 Quick Commands

### Stop Robot
```python
robot.stop()
```

### Reset State Machine
```python
state_machine.reset()
```

### Manual Arm Control
```python
arm.home()
arm.gripper_open()
arm.gripper_close()
```

### Check Status
```python
status = state_machine.get_status()
print(f"Balls collected: {status['balls_collected']}")
```

---

## 🔗 File Locations

- **Config:** `config.yaml`
- **Calibration:** `notebooks/00_calibrate_basket.ipynb`
- **Testing:** `notebooks/02_test_perception.ipynb`
- **Full Run:** `notebooks/06_full_run.ipynb`
- **Diagnostics:** `robot_tests/robot_diagnostics.ipynb`

---

**Good luck! 🏆**
