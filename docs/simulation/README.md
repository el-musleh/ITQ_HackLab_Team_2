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
# From project root
python simulation/test_basic_motion.py
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
simulation/
├── models/
│   ├── jetank.urdf          # Robot model
│   └── arena.urdf           # Arena + objects
├── sim_core.py              # PyBullet engine
├── sim_hardware.py          # Simulated hardware interfaces
└── test_basic_motion.py     # Phase 1 validation

docs/simulation/
├── README.md                # This file
├── SETUP.md                 # Detailed installation
├── USAGE.md                 # How to run simulations
└── ARCHITECTURE.md          # Technical design
```

## Next Steps

1. **Phase 1 Complete**: Basic physics ✓
2. **Phase 2**: Add camera rendering and perception testing
3. **Phase 3**: Full autonomous loop with state machine

See [USAGE.md](USAGE.md) for detailed instructions.

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
cd /path/to/ITQ_HackLab_Team_2
python simulation/test_basic_motion.py
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more help.
