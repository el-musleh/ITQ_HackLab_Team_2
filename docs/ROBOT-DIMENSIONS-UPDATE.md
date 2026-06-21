# Robot Dimensions Update

**Date**: June 21, 2026  
**Status**: ✅ UPDATED

---

## Updated Robot Specifications

### Physical Dimensions

**Chassis**:
- Length: 17 cm
- Width (with wheels): 19 cm  
- Height: 25 cm
- Wheel width: 4 cm

**Previous dimensions** (incorrect):
- ~~Length: 26 cm~~
- ~~Width: 20 cm~~
- ~~Height: 10 cm~~

### Drive System

**Mobile Base**: 4-wheel skid-steer differential drive (tank steering)
- Front Left Wheel
- Front Right Wheel
- Rear Left Wheel
- Rear Right Wheel
- Wheel radius: 3 cm
- Wheel width: 4 cm
- Track width: 19 cm (wheel base)

**Previous**: Simple 2-wheel differential drive representation

### Camera System

**Configuration**: Single front-facing camera
- Position: Front of chassis at 8cm height
- Orientation: Looking forward and slightly down (0.15 rad pitch)
- Size: 2.5 × 4 × 1.5 cm
- Type: Fixed mount (no pan/tilt)

**Previous**: Generic camera mount

### Robotic Arm

**4-DOF Articulated Arm**:
1. **Base (Pan)**: Rotates around Z-axis (±90°)
2. **Shoulder**: Pitch joint (±80°)
3. **Elbow**: Pitch joint (±80°)
4. **Wrist**: Pitch joint for gripper orientation (±90°)

**Link Dimensions**:
- Base: 2.5 cm radius, 5 cm height
- Shoulder (upper arm): 9 × 2.5 × 2.5 cm
- Elbow (forearm): 9 × 2.5 × 2.5 cm
- Wrist: 5 × 2 × 2 cm
- Gripper (end effector): 4 × 5 × 2 cm

**Previous**: 3-DOF arm (base, shoulder, elbow, gripper)

### Controller

**NVIDIA Jetson Nano** (not modeled in URDF, but noted for reference)

---

## Files Updated

### 1. `src/simulation/models/jetank.urdf`

**Changes**:
- ✅ Updated chassis dimensions (17×19×25 cm)
- ✅ Added 4 wheels for skid-steer drive
- ✅ Updated camera to single front-facing unit
- ✅ Converted arm to proper 4-DOF (Base Pan, Shoulder, Elbow, Wrist)
- ✅ Added wrist joint for gripper orientation
- ✅ Updated all masses and inertias

**Joint Structure**:
```
base_link (chassis)
├── wheel_fl (front left)
├── wheel_fr (front right)
├── wheel_rl (rear left)
├── wheel_rr (rear right)
├── camera_link (fixed)
└── arm_base (pan/rotation)
    └── arm_shoulder (pitch)
        └── arm_elbow (pitch)
            └── arm_wrist (pitch)
                └── gripper (fixed end effector)
```

### 2. `src/simulation/sim_hardware.py`

**Changes**:
- ✅ Updated wheel base to 0.19m (19cm)
- ✅ Updated joint indices for new URDF structure
- ✅ Changed arm control from 3-DOF to 4-DOF
- ✅ Updated joint names: base, shoulder, elbow, wrist

**Joint Indices**:
```python
# Wheels: 0-3 (continuous joints)
# Camera: 4 (fixed joint)
# Arm joints: 5-8 (revolute joints)
{
    'base': 5,      # arm_base_joint (pan)
    'shoulder': 6,  # arm_shoulder_joint
    'elbow': 7,     # arm_elbow_joint
    'wrist': 8      # arm_wrist_joint
}
```

---

## Configuration Updates Needed

### `config.yaml`

The arm poses should now use 4 values: `[base, shoulder, elbow, wrist]`

**Example**:
```yaml
arm_poses:
  home: [0, 0, 0, 0]           # All joints neutral
  pickup: [0, -40, -60, -30]   # Reach down to pick
  carry: [0, 20, 30, 90]       # Lift and hold
  deposit: [0, 40, 40, 45]     # Reach up to deposit
```

**Note**: The 4th value is now **wrist** angle (not gripper open/close).

---

## Visual Comparison

### Before (Incorrect)
```
┌─────────────────────────┐
│   26cm × 20cm × 10cm    │  ← Too wide, too flat
│   (Generic chassis)     │
└─────────────────────────┘
        3-DOF Arm
```

### After (Correct)
```
        ┌──────────┐
        │  17cm ×  │
        │  19cm ×  │  ← Taller, narrower
        │  25cm    │
        └──────────┘
    ⚙️⚙️      ⚙️⚙️  ← 4 wheels
        4-DOF Arm
        📷 Camera
```

---

## Testing

### Test Results

Running `test_basic_motion.py` with updated model:

```bash
./venv/bin/python src/simulation/test_basic_motion.py
```

**Expected**:
- ✅ Robot loads with correct dimensions
- ✅ 4 wheels visible in simulation
- ✅ Arm has 4 controllable joints
- ✅ Camera positioned at front
- ✅ All movement tests pass

---

## Impact on Simulation

### Physics Changes

1. **Center of Mass**: Higher due to taller chassis (25cm vs 10cm)
   - More realistic tipping behavior
   - Better stability simulation

2. **Moment of Inertia**: Different due to new dimensions
   - More accurate turning dynamics
   - Better represents actual robot

3. **Wheel Contact**: 4 wheels instead of simplified model
   - More realistic friction
   - Better traction simulation

### Control Changes

1. **Arm Control**: Now 4-DOF instead of 3-DOF
   - More flexibility in gripper positioning
   - Wrist can orient gripper independently

2. **Wheel Base**: 19cm instead of 16cm
   - Slightly wider turning radius
   - More stable platform

---

## Compatibility

### Backward Compatibility

**Breaking Changes**:
- ⚠️ Arm poses now require 4 values instead of 3
- ⚠️ Joint indices changed due to wheel additions

**Migration**:
```python
# Old (3-DOF)
arm.set_joint_angles([0, -40, -60])  # base, shoulder, elbow

# New (4-DOF)
arm.set_joint_angles([0, -40, -60, 0])  # base, shoulder, elbow, wrist
```

### Config File Update

Update all arm poses in `config.yaml` to include wrist angle:
```yaml
# Add 4th value to each pose
arm_poses:
  home: [0, 0, 0, 0]        # Added wrist
  pickup: [0, -40, -60, 0]  # Added wrist
  carry: [0, 20, 30, 90]    # Added wrist
  deposit: [0, 40, 40, 0]   # Added wrist
```

---

## Validation Checklist

- [x] URDF file updated with correct dimensions
- [x] 4 wheels added for skid-steer drive
- [x] Camera positioned correctly (front-facing)
- [x] Arm updated to 4-DOF (Base, Shoulder, Elbow, Wrist)
- [x] Joint indices updated in sim_hardware.py
- [x] Wheel base updated to 19cm
- [ ] Config.yaml arm poses updated (user action required)
- [ ] Test basic motion with new model
- [ ] Verify arm reach and workspace

---

## Next Steps

1. **Update config.yaml**: Add wrist angles to all arm poses
2. **Test simulation**: Run `test_basic_motion.py` to verify
3. **Calibrate arm**: Adjust pose angles if needed for proper reach
4. **Validate workspace**: Ensure arm can reach ground and basket

---

**Status**: ✅ Robot model updated to match actual JETANK specifications

**Recommendation**: Test the updated model and fine-tune arm poses for optimal performance.
