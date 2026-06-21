# Simulation Troubleshooting

Common issues and solutions for the PyBullet simulation environment.

## Installation Issues

### "No module named 'pybullet'"

**Symptoms:**
```
ImportError: No module named 'pybullet'
```

**Solution:**
```bash
# Activate virtual environment
source venv/bin/activate

# Install PyBullet
pip install pybullet

# Verify
python -c "import pybullet; print('OK')"
```

### "externally-managed-environment" Error

**Symptoms:**
```
error: externally-managed-environment
```

**Solution:**
```bash
# Use virtual environment (don't install system-wide)
source venv/bin/activate
pip install pybullet
```

### PyBullet Build Fails

**Symptoms:**
```
Building wheels for collected packages: pybullet
ERROR: Failed building wheel for pybullet
```

**Solution:**
```bash
# Install build dependencies
sudo apt-get install python3-dev build-essential

# Or use pre-built wheel
pip install --upgrade pip
pip install pybullet
```

## Runtime Issues

### "FileNotFoundError: Robot URDF not found"

**Symptoms:**
```
FileNotFoundError: Robot URDF not found: simulation/models/jetank.urdf
```

**Solution:**
```bash
# Make sure you're running from project root
cd /path/to/ITQ_HackLab_Team_2
python src/simulation/test_basic_motion.py

# NOT from simulation directory:
# cd simulation  # ❌ Wrong
# python test_basic_motion.py  # ❌ Won't work
```

### PyBullet GUI Doesn't Open

**Symptoms:**
- Script runs but no window appears
- "Failed to create GL context" error

**Solutions:**

**Option 1: Check display**
```bash
echo $DISPLAY
# Should show something like :0 or :1
```

**Option 2: Run headless**
```python
# Edit test script
sim = SimulationCore(gui=False, real_time=False)
```

**Option 3: Install OpenGL**
```bash
# Ubuntu/Debian
sudo apt-get install libgl1-mesa-glx libgl1-mesa-dri

# Check OpenGL
glxinfo | grep "OpenGL version"
```

### Robot Falls Through Floor

**Symptoms:**
- Robot disappears or falls infinitely
- Z position becomes very negative

**Causes:**
- URDF collision shapes missing
- Mass/inertia set to zero

**Solution:**
```python
# Check robot state
state = sim.get_robot_state()
print(state['position'])  # Z should be ~0.05

# If falling, check URDF:
# - All links need <collision> tags
# - Mass must be > 0
# - Inertia must be > 0
```

### Simulation Runs Too Slow

**Symptoms:**
- GUI is laggy
- Takes forever to complete tests

**Solutions:**

**Option 1: Disable real-time**
```python
sim = SimulationCore(gui=True, real_time=False)
# Runs as fast as possible
```

**Option 2: Disable GUI**
```python
sim = SimulationCore(gui=False, real_time=False)
# Fastest mode
```

**Option 3: Reduce physics rate**
```python
# In sim_core.py, change:
self.time_step = 1.0 / 120.0  # 120 Hz instead of 240 Hz
```

### Robot Doesn't Move

**Symptoms:**
- Motors set but robot stays still
- No error messages

**Debug Steps:**

**1. Check motor commands**
```python
chassis.forward(speed=0.2)
print(f"Left: {chassis.left_speed}, Right: {chassis.right_speed}")
# Should print: Left: 0.2, Right: 0.2
```

**2. Check robot mass**
```python
# Robot needs mass > 0 to move
# Check URDF <inertial><mass value="1.5"/></inertial>
```

**3. Check physics stepping**
```python
# Must call sim.step() to advance physics
for _ in range(100):
    chassis.forward(speed=0.2)
    sim.step()  # ← Don't forget this!
```

**4. Increase velocity scale**
```python
# In sim_hardware.py, SimChassis.set_motors():
# Increase scale factor from 2.0 to 3.0 or 4.0
```

### Camera Returns Black Image

**Symptoms:**
```python
frame = camera.read()
# frame is all zeros or black
```

**Solutions:**

**1. Check renderer**
```python
# In sim_hardware.py, change renderer:
renderer=p.ER_TINY_RENDERER  # Software renderer
# OR
renderer=p.ER_BULLET_HARDWARE_OPENGL  # Hardware renderer
```

**2. Check camera position**
```python
# Debug camera view
state = sim.get_robot_state()
print(f"Robot at: {state['position']}")
# Camera should be above ground (z > 0)
```

**3. Check lighting**
```python
# PyBullet needs light sources for ER_BULLET_HARDWARE_OPENGL
# Use ER_TINY_RENDERER for simple rendering
```

### Collisions Not Detected

**Symptoms:**
```python
colliding = sim.check_collision(robot_id, arena_id)
# Always returns False even when touching wall
```

**Solutions:**

**1. Check collision shapes**
```xml
<!-- In URDF, ensure <collision> tags exist -->
<link name="base_link">
  <collision>
    <geometry>
      <box size="0.26 0.20 0.10"/>
    </geometry>
  </collision>
</link>
```

**2. Check contact points**
```python
# Debug contact detection
contacts = p.getContactPoints(robot_id, arena_id)
print(f"Contact points: {len(contacts)}")
for c in contacts:
    print(f"  Position: {c[5]}, Normal: {c[7]}")
```

**3. Enable collision visualization**
```python
# In PyBullet GUI
p.configureDebugVisualizer(p.COV_ENABLE_WIREFRAME, 1)
```

## Import Errors

### "No module named 'hardware'"

**Symptoms:**
```
ModuleNotFoundError: No module named 'hardware'
```

**Solution:**
```python
# Add parent directory to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now imports work
from src.hardware.chassis import Chassis
```

### "No module named 'perception'"

**Same as above** - need to add project root to Python path.

## Configuration Issues

### "KeyError: 'arm_poses'"

**Symptoms:**
```
KeyError: 'arm_poses'
```

**Solution:**
```bash
# Check config.yaml exists
ls config.yaml

# Check it has arm_poses section
grep -A 5 "arm_poses" config.yaml

# Should show:
# arm_poses:
#   home: [0, 0, 0, 0]
#   pickup: [0, -40, -60, 0]
#   ...
```

### Wrong Config Values

**Symptoms:**
- Robot moves too fast/slow
- Arm doesn't reach correctly

**Solution:**
```yaml
# Edit config.yaml
motors:
  max_speed: 0.25  # Adjust if too fast/slow

arm_poses:
  pickup: [0, -40, -60, 0]  # Adjust angles if needed
```

## Performance Issues

### High CPU Usage

**Symptoms:**
- CPU at 100%
- Computer fans loud

**Solutions:**

**1. Limit frame rate**
```python
import time

for i in range(1000):
    sim.step()
    time.sleep(0.01)  # Limit to ~100 Hz
```

**2. Use headless mode**
```python
sim = SimulationCore(gui=False, real_time=False)
```

**3. Reduce physics rate**
```python
self.time_step = 1.0 / 60.0  # 60 Hz instead of 240 Hz
```

### High Memory Usage

**Symptoms:**
- RAM usage keeps increasing
- System becomes slow

**Solutions:**

**1. Close simulation properly**
```python
try:
    # ... run simulation ...
finally:
    sim.close()  # Always close!
```

**2. Reset instead of recreating**
```python
# Good: Reuse simulation
for trial in range(100):
    sim.reset()
    # ... run trial ...

# Bad: Create new simulation each time
for trial in range(100):
    sim = SimulationCore(...)  # Memory leak!
```

**3. Limit camera captures**
```python
# Don't capture every frame if not needed
if i % 10 == 0:  # Only every 10th frame
    frame = camera.read()
```

## Platform-Specific Issues

### macOS: "Library not loaded"

**Solution:**
```bash
# Install OpenGL dependencies
brew install glfw3

# Or use conda
conda install -c conda-forge pybullet
```

### Windows: "DLL load failed"

**Solution:**
```bash
# Install Visual C++ Redistributable
# Download from Microsoft website

# Or use conda
conda install -c conda-forge pybullet
```

### Linux: "libGL error"

**Solution:**
```bash
sudo apt-get install libgl1-mesa-glx libgl1-mesa-dri
```

## Getting Help

If your issue isn't listed here:

1. **Check PyBullet docs**: [PyBullet Quickstart](https://docs.google.com/document/d/10sXEhzFRSnvFcl3XxNGhnD4N2SedqwdAvK3dsihxVUA/edit)
2. **Search GitHub issues**: [PyBullet Issues](https://github.com/bulletphysics/bullet3/issues)
3. **Enable debug output**:
   ```python
   import pybullet as p
   p.setDebugObjectColor(robot_id, -1, [1, 0, 0])  # Make robot red
   ```

## Debug Checklist

When something doesn't work:

- [ ] Virtual environment activated?
- [ ] Running from project root?
- [ ] URDF files exist?
- [ ] Config.yaml loaded correctly?
- [ ] Calling `sim.step()` in loop?
- [ ] Robot has mass > 0?
- [ ] Collision shapes defined?
- [ ] OpenGL/display working?
- [ ] Latest PyBullet version?
- [ ] Python 3.8+?
