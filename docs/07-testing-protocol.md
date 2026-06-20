# Testing Protocol — Run These in Order

> **Do not write new code until these 5 tests pass.** Each test builds on the previous.

## Test 1: Camera (Yashveer — First Priority)

**Goal:** Verify CSI camera captures frames.

```bash
python3 -c "from jetbot import Camera; c = Camera.instance(); print('Camera OK')"
```

**Notebook test:**
1. Open `/workspace/JETANK/JETANK_5_colorTracking/colorTracking_en.ipynb`
2. Run the first 2 cells (camera init + display)
3. **Verify:** A 300×300 video feed appears below the cell

**If camera fails:**
- Restart Jupyter kernel: right-click notebook tab → `Shut Down Kernel` → reopen
- Try again
- If still failing: ask organizer — may be hardware issue

---

## Test 2: Servos (Joaquin)

**Goal:** Verify arm joints move safely.

```bash
cd /workspace/JETANK/JETANK_1_servos
# Open JETANK_1_servos_en.ipynb in Jupyter
# Run servo test cells one by one
```

**Document in `config.yaml`:**
- Min/max safe angles for each servo
- Current servo positions after each movement
- Any servo that doesn't respond (note ID)

**Safety:** Keep arm away from people and fragile objects. Servos are strong.

---

## Test 3: Chassis Motors (Joaquin)

**Goal:** Verify tracked chassis moves forward, backward, rotates.

```bash
cd /workspace/JETANK/JETANK_2_ctrl
# Open ctrl notebook
# Run motor test cells
```

**Verify:**
- Left track moves forward
- Right track moves forward
- Robot rotates in place (left track forward + right track backward)
- Stop command works immediately

---

## Test 4: Color Detection (Yashveer)

**Goal:** Detect a real bottle cap in front of the camera.

```bash
cd /workspace/JETANK/JETANK_5_colorTracking
# Open colorTracking_en.ipynb
```

**Steps:**
1. Place a bottle cap ~30cm in front of camera
2. Run the color detection cells
3. Adjust `colorUpper` and `colorLower` HSV values until the cap is detected
4. **Save the working HSV values** — these go into `perception/detector.py`

**Example presets:**
```python
colorUpper = np.array([44, 255, 255])   # yellow max
colorLower = np.array([24, 100, 100])   # yellow min

# If caps are a different color, use these ranges:
# Red:    [160, 100, 100] to [180, 255, 255]
# Green:  [50, 200, 100]  to [70, 255, 255]
# Blue:   [110, 180, 200] to [135, 225, 255]
```

---

## Test 5: Full Loop (Mohammad + Myron)

**Goal:** Camera sees cap → chassis rotates to face cap → approaches → stops.

**Starting code:** Adapt `colorTracking_en.ipynb`:
- Keep the `findColor()` function (returns cap coordinates)
- **Replace** camera pan/tilt servo commands with **chassis rotation**
- When cap is centered in frame → drive forward
- When cap fills enough pixels → stop

**Pseudocode:**
```python
if cap_centered and not cap_close:
    chassis.move_forward(speed=40)
elif cap_left:
    chassis.rotate_left(speed=30)
elif cap_right:
    chassis.rotate_right(speed=30)
elif cap_close:
    chassis.stop()
    state = COLLECT
```

---

## Test 6: Arm Pickup (Joaquin + Yashveer)

**Goal:** When robot stops near cap, arm grabs it.

**Requires:** Working servos + known safe angles from Test 2.

**Motion sequence:**
1. Lower arm to ground level
2. Open gripper
3. Position over cap
4. Close gripper
5. Lift arm
6. Stow (tuck arm in for driving)

**Tune each angle in `config.yaml`**:
```yaml
arm_angles:
  reach_down: [500, 300, 600, 400]   # base, shoulder, elbow, gripper
  grip:       [500, 300, 600, 200]   # gripper closed
  lift:       [500, 400, 500, 200]   # arm raised
  stow:       [512, 512, 512, 200]   # neutral position
```

---

## What to Do If a Test Fails

| Fails | Action |
|-------|--------|
| Camera | Restart kernel → retry → ask organizer |
| Servos | Check `/dev/ttyTHS1` permissions → re-run servo init cell |
| Chassis | Verify servo IDs in config match actual wiring |
| Detection | Widen HSV range → adjust lighting → try different cap color |
| Approach | Lower PID_P → reduce speed → increase error tolerance |
| Pickup | Adjust arm angles incrementally (5-10 units at a time) |
