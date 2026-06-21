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
- ✅ Joint indices discovered from URDF at runtime (no hardcoded indices)

**Test Results:**
```
✓ Move forward and backward
✓ Turn left and right
✓ Detect collisions
✓ Move arm to all poses
✓ Execute pickup sequence
✓ Execute deposit sequence
```

### Phase 2: Camera & Vision ✅ COMPLETE

- ✅ Camera rendering from robot perspective
- ✅ Synthetic image generation (RGB + BGR for OpenCV)
- ✅ Perception pipeline testing
- ✅ Ball/obstacle/basket detection
- ✅ Headless renderer fallback (OpenGL → Tiny)

### Phase 3: Full System ✅ COMPLETE

- ✅ State machine integration (real `StateMachine` API via `tick()`)
- ✅ PID controller testing
- ✅ Autonomous navigation
- ✅ Headless pytest tests in `tests/`

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
# Phase 1: Basic motion (GUI)
python src/simulation/test_basic_motion.py

# Phase 2: Perception (GUI)
python src/simulation/test_perception.py

# Phase 3: Full autonomous run (GUI)
python src/simulation/run_simulation.py

# Headless pytest suite (no GUI, safe for CI)
python -m pytest tests/ -m simulation
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
2. ✅ **Phase 2 Complete**: Camera rendering + perception
3. ✅ **Phase 3 Complete**: State machine + perception integration
4. Tune `locomotion_mode: wheels` and ball-grasp parameters for higher realism

## Configuration

Simulation behavior is controlled by the `simulation:` section of `config.yaml`:

| Key | Default | Description |
|-----|---------|-------------|
| `gui` | `true` | Show PyBullet GUI window (set `false` for headless/CI) |
| `real_time` | `true` | Step at wall-clock real time |
| `locomotion_mode` | `velocity` | `velocity` (stable, default) or `wheels` (realistic, drives wheel joints) |
| `ball_spawn_seed` | `42` | RNG seed for reproducible ball positions |
| `camera_fov` | `160` | Simulated camera field of view (degrees) |
| `renderer` | `auto` | `auto` / `opengl` / `tiny` (fallback for headless) |
| `num_balls` | `22` | Default ball count for `run_simulation.py` |
| `max_duration_sec` | `300` | Default run timeout for `run_simulation.py` |
| `steps_per_tick` | `12` | Physics steps per state-machine tick |
| `show_visualization` | `true` | OpenCV debug window in `run_simulation.py` |

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
