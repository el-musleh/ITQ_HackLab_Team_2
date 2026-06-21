# Simulation Environment - Quick Start

PyBullet-based simulation for testing the ITQ Bottle Cap Collector robot without hardware.

## What is This?

A virtual environment that mimics the real challenge arena, allowing you to:
- Test control algorithms (PID, state machine)
- Validate perception pipeline (ball/obstacle/basket detection)
- Debug navigation logic
- Tune parameters before hardware deployment

## Quick Start

### 1. Install Dependencies

```bash
# Activate virtual environment
source venv/bin/activate

# Install PyBullet (already done if you followed setup)
pip install pybullet numpy opencv-python pyyaml
```

### 2. Run Basic Test

```bash
# Headless mode (no GUI, for CI / automated testing)
python3 src/simulation/test_basic_motion.py --headless

# GUI mode (requires display)
python3 src/simulation/test_basic_motion.py
```

This will:
- Open PyBullet GUI window
- Load robot and arena
- Test forward/backward movement
- Test turning
- Test arm movements
- Verify collision detection

### 3. What You'll See

- **Arena**: 175×180 cm floor with yellow boundary walls
- **Obstacles**: 2 crates with yellow tape
- **Basket**: Gray cylinder at center
- **Balls**: 22 colored spheres (blue, red, silver)
- **Robot**: JETANK with 4-DOF arm

## File Structure

```
src/simulation/
├── models/
│   ├── jetank.urdf          # Robot model
│   └── arena.urdf           # Arena + objects
├── sim_core.py              # PyBullet engine
├── sim_hardware.py          # Simulated hardware interfaces
├── run_simulation.py        # Phase 3 full autonomous run
├── test_basic_motion.py     # Phase 1 validation
├── test_perception.py       # Phase 2 validation
└── tests/
    └── test_scenario_happy_path.py

tests/                       # Headless pytest suite
├── test_simulation_core.py
├── test_sim_hardware.py
└── test_simulation_scenario.py

docs/simulation/
├── README.md                # This file
├── SETUP.md                 # Detailed installation
├── USAGE.md                 # How to run simulations
└── ARCHITECTURE.md          # Technical design
```

## Next Steps

1. **Phase 1**: Basic physics — tests in progress
2. **Phase 2**: Camera rendering and perception testing — tests in progress
3. **Phase 3**: Full autonomous loop with state machine — tests in progress

See [USAGE.md](USAGE.md) for detailed instructions.

## Configuration

Simulation behavior is controlled by the `simulation:` section of `config.yaml`:

| Key | Default | Description |
|-----|---------|-------------|
| `gui` | `true` | Show PyBullet GUI (set `false` for headless/CI) |
| `real_time` | `true` | Step at wall-clock real time |
| `locomotion_mode` | `velocity` | `velocity` (stable) or `wheels` (realistic, drives wheel joints) |
| `ball_spawn_seed` | `42` | RNG seed for reproducible ball positions |
| `camera_fov` | `160` | Simulated camera FOV (degrees) |
| `renderer` | `auto` | `auto` / `opengl` / `tiny` (headless fallback) |

## Headless Tests

The simulation ships with pytest tests that run headless (`p.DIRECT`), safe for CI:

```bash
# All simulation tests
python3 -m pytest tests/ -m simulation

# Non-simulation tests only
python3 -m pytest tests/ -m "not simulation"

# All tests
python3 -m pytest tests/

# Standalone headless scripts
python3 src/simulation/test_basic_motion.py --headless
python3 src/simulation/test_perception.py --headless
python3 src/simulation/run_simulation.py --headless --duration 60 --balls 5
```

## Key Features

- ✅ **Drop-in replacement**: Same API as real hardware
- ✅ **Realistic physics**: PyBullet 240 Hz simulation
- ✅ **Visual debugging**: See robot in 3D
- ✅ **Fast iteration**: No hardware setup needed
- ✅ **Reproducible**: Same initial conditions every run

## Troubleshooting

**PyBullet GUI not showing?**
```bash
# Check if running in virtual environment
which python
# Should show: .../venv/bin/python
```

**Import errors?**
```bash
# Make sure you're in project root
python3 src/simulation/test_basic_motion.py --headless
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more help.
