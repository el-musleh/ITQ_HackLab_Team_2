# Simulation Environment

PyBullet-based physics simulation for the ITQ Bottle Cap Collector robot.

## Quick Start

```bash
# Activate virtual environment
source venv/bin/activate

# Run Phase 1 test
python src/simulation/test_basic_motion.py
```

## What's Included

### Phase 1: Basic Robot & Arena ✅ COMPLETE

- ✅ Robot model with chassis and 4-DOF arm
- ✅ Arena with boundaries, obstacles, and basket
- ✅ 22 colored balls (blue, red, silver)
- ✅ Physics simulation (240 Hz)
- ✅ Collision detection
- ✅ Hardware abstraction layer

**Test Results:**
```
✓ Move forward and backward
✓ Turn left and right
✓ Detect collisions
✓ Move arm to all poses
✓ Execute pickup sequence
✓ Execute deposit sequence
```

### Phase 2: Camera & Vision (TODO)

- [ ] Camera rendering from robot perspective
- [ ] Synthetic image generation
- [ ] Perception pipeline testing
- [ ] Ball/obstacle/basket detection

### Phase 3: Full System (TODO)

- [ ] State machine integration
- [ ] PID controller testing
- [ ] Autonomous navigation
- [ ] Performance benchmarking

## Files

```
simulation/
├── models/
│   ├── jetank.urdf          # Robot URDF model
│   └── arena.urdf           # Arena URDF model
├── sim_core.py              # PyBullet engine
├── sim_hardware.py          # Simulated hardware interfaces
├── test_basic_motion.py     # Phase 1 validation
└── README.md                # This file
```

## Usage

### Import Simulation

```python
from src.simulation.sim_core import SimulationCore
from src.simulation.sim_hardware import create_sim_hardware
import yaml

# Load config
config = yaml.safe_load(open('config.yaml'))

# Initialize
sim = SimulationCore(gui=True, real_time=True)
sim.initialize()
sim.load_arena()
robot_id = sim.load_robot()
sim.spawn_balls()

# Create hardware
chassis, arm, camera = create_sim_hardware(robot_id, config)

# Use same API as real hardware
chassis.forward(speed=0.2)
arm.pickup_sequence()
```

### Run Tests

```bash
# Phase 1: Basic motion
python src/simulation/test_basic_motion.py

# Phase 2: Perception (coming soon)
# python src/simulation/test_perception.py

# Phase 3: Full system (coming soon)
# python src/simulation/run_simulation.py
```

## Documentation

See `docs/simulation/` for detailed guides:

- [README.md](../docs/simulation/README.md) - Quick start
- [SETUP.md](../docs/simulation/SETUP.md) - Installation guide
- [USAGE.md](../docs/simulation/USAGE.md) - Usage examples
- [ARCHITECTURE.md](../docs/simulation/ARCHITECTURE.md) - Technical details
- [TROUBLESHOOTING.md](../docs/simulation/TROUBLESHOOTING.md) - Common issues

## Hardware Abstraction

The simulation provides drop-in replacements for real hardware:

| Real Hardware | Simulation | API Compatible |
|---------------|------------|----------------|
| `hardware.chassis.Chassis` | `SimChassis` | ✅ Yes |
| `hardware.arm.Arm` | `SimArm` | ✅ Yes |
| `hardware.camera.Camera` | `SimCamera` | ✅ Yes |

**Same code works in both environments!**

## Next Steps

1. ✅ **Phase 1 Complete**: Basic physics working
2. **Phase 2**: Add camera rendering (see plan)
3. **Phase 3**: Integrate state machine and perception

## Requirements

- Python 3.8+
- PyBullet 3.2.7+
- NumPy
- OpenCV
- PyYAML

Install with:
```bash
pip install pybullet numpy opencv-python pyyaml
```

## License

Same as main project.
