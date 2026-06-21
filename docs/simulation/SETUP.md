# Simulation Setup Guide

Detailed installation and configuration instructions for the PyBullet simulation environment.

## Prerequisites

- Python 3.8+
- Virtual environment (already created in project)
- Linux/macOS/Windows

## Installation

### Step 1: Activate Virtual Environment

```bash
cd /path/to/ITQ_HackLab_Team_2
source venv/bin/activate  # Linux/macOS
# OR
venv\Scripts\activate     # Windows
```

### Step 2: Install PyBullet

```bash
pip install pybullet numpy opencv-python pyyaml
```

**Expected output:**
```
Successfully installed pybullet-3.2.7
```

### Step 3: Verify Installation

```bash
python -c "import pybullet as p; print('PyBullet version:', p.getVersionInfo())"
```

Should print version info without errors.

## Directory Structure

The simulation files are organized as follows:

```
ITQ_HackLab_Team_2/
├── simulation/              # Simulation code (project root)
│   ├── models/
│   │   ├── jetank.urdf      # Robot URDF model
│   │   ├── arena.urdf       # Arena URDF model
│   │   └── textures/        # (Future: ball/basket textures)
│   ├── sim_core.py          # Core PyBullet engine
│   ├── sim_hardware.py      # Simulated hardware interfaces
│   └── test_basic_motion.py # Phase 1 validation script
│
└── docs/simulation/         # Documentation
    ├── README.md            # Quick start
    ├── SETUP.md             # This file
    ├── USAGE.md             # Usage guide
    └── ARCHITECTURE.md      # Technical details
```

## Configuration

The simulation uses the same `config.yaml` as the real robot:

```yaml
# config.yaml
motors:
  max_speed: 0.25
  approach_speed: 0.15
  search_speed: 0.10

arm_poses:
  home: [0, 0, 0, 0]
  pickup: [0, -40, -60, 0]
  carry: [0, 20, 30, 90]
  deposit: [0, 40, 40, 0]

camera:
  width: 320
  height: 240
  fps: 30
```

No simulation-specific configuration needed - it reads from the main config.

## Testing Installation

### Test 1: Import Modules

```bash
python -c "from src.simulation.sim_core import SimulationCore; print('✓ sim_core OK')"
python -c "from src.simulation.sim_hardware import SimChassis; print('✓ sim_hardware OK')"
```

### Test 2: Run Basic Motion Test

```bash
python src/simulation/test_basic_motion.py
```

**Expected behavior:**
1. PyBullet GUI window opens
2. Arena loads with walls, obstacles, basket
3. Robot appears at starting position
4. 22 colored balls spawn
5. Robot performs movement tests
6. Console shows test progress

### Test 3: Check URDF Models

```bash
python -c "
import os
assert os.path.exists('simulation/models/jetank.urdf'), 'Robot URDF missing'
assert os.path.exists('simulation/models/arena.urdf'), 'Arena URDF missing'
print('✓ URDF models found')
"
```

## Common Issues

### Issue 1: "No module named 'pybullet'"

**Solution:**
```bash
# Make sure virtual environment is activated
source venv/bin/activate
pip install pybullet
```

### Issue 2: "FileNotFoundError: Robot URDF not found"

**Solution:**
```bash
# Run from project root, not from simulation/ directory
cd /path/to/ITQ_HackLab_Team_2
python src/simulation/test_basic_motion.py
```

### Issue 3: PyBullet GUI doesn't open

**Possible causes:**
- Running over SSH without X11 forwarding
- Missing OpenGL libraries

**Solution:**
```bash
# For headless mode (no GUI), edit test script:
# Change: sim = SimulationCore(gui=True, ...)
# To:     sim = SimulationCore(gui=False, ...)
```

### Issue 4: Slow performance

**Solution:**
```bash
# Disable real-time mode for faster simulation
# In test script, change:
# sim = SimulationCore(gui=True, real_time=True)
# To:
# sim = SimulationCore(gui=True, real_time=False)
```

## Hardware Requirements

### Minimum
- CPU: Dual-core 2.0 GHz
- RAM: 4 GB
- GPU: Integrated graphics
- Disk: 500 MB free space

### Recommended
- CPU: Quad-core 2.5 GHz+
- RAM: 8 GB+
- GPU: Dedicated GPU with OpenGL 3.3+
- Disk: 1 GB free space

## Next Steps

After successful installation:

1. ✅ Run `test_basic_motion.py` to verify Phase 1
2. 📖 Read [USAGE.md](USAGE.md) for detailed usage
3. 🔧 Read [ARCHITECTURE.md](ARCHITECTURE.md) for technical details
4. 🚀 Proceed to Phase 2: Camera & Vision simulation

## Support

If you encounter issues not covered here, check:
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- [PyBullet Documentation](https://docs.google.com/document/d/10sXEhzFRSnvFcl3XxNGhnD4N2SedqwdAvK3dsihxVUA/edit)
- [PyBullet GitHub Issues](https://github.com/bulletphysics/bullet3/issues)
