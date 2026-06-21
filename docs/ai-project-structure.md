# AI Project Structure Guide

This document defines the canonical folder layout for the ITQ_HackLab_Team_2 project. All AI agents and contributors must follow these rules when adding or moving files.

## Folder Layout

```
ITQ_HackLab_Team_2/
├── AGENTS.md                    # AI agent instructions (read this first)
├── README.md                    # Project overview (stays in root)
├── LICENSE                      # License file (stays in root)
├── setup.py                     # Package install config (stays in root)
├── config.yaml                  # Runtime configuration (stays in root)
├── pytest.ini                   # Test configuration (stays in root)
├── config.sh                    # Shell scripts (stays in root)
├── install.sh
├── setup.sh
├── .gitignore
│
├── docs/                        # ALL Markdown documentation
│   ├── ai-project-structure.md  # This file
│   ├── challenge/               # Challenge specs
│   ├── simulation/              # Simulation docs
│   └── *.md                     # All other docs
│
├── src/                         # ALL Python source code
│   ├── __init__.py
│   ├── main.py                  # Entry point
│   ├── navigation.py            # Autonomous navigation
│   ├── brainrot.py              # Vision + driving script
│   ├── example_hardware_switch.py
│   ├── servoInt.py
│   ├── control/                 # State machine, PID, navigator, recovery
│   ├── hardware/                # Chassis, arm, camera
│   ├── perception/              # Ball, basket, obstacle detectors
│   ├── simulation/              # Sim core, hardware sim, demos
│   ├── SCSCtrl/                 # Waveshare servo SDK
│   └── utils/                   # Shared utilities
│
├── notebooks/                   # ALL Jupyter notebooks
│   ├── basic_motion/
│   ├── collison_aviodance/
│   ├── jetank/
│   ├── object_following/
│   ├── road_following/
│   ├── teleoperations/
│   ├── camera/
│   ├── detection/
│   ├── master/
│   ├── misc/
│   ├── robot/
│   └── *.ipynb
│
├── tests/                       # Test suite
│   ├── test_state_machine.py
│   ├── test_utils.py
│   ├── mocks.py
│   └── __init__.py
│
└── logs/                        # Runtime logs
```

## Rules

### Markdown files (`.md`)

| Rule | Detail |
|------|--------|
| **Location** | `docs/` |
| **Root exceptions** | `README.md`, `LICENSE`, `AGENTS.md` only |
| **Subfolders** | Use `docs/challenge/`, `docs/simulation/` for topic grouping |
| **Naming** | lowercase-with-hyphens.md for new files |

### Python files (`.py`)

| Rule | Detail |
|------|--------|
| **Location** | `src/` |
| **Root exception** | `setup.py` only |
| **Module folders** | `src/control/`, `src/hardware/`, `src/perception/`, `src/simulation/`, `src/SCSCtrl/`, `src/utils/` |
| **Import style** | Always use `from src.<module>.<file> import <Class>` |
| **Tests** | `tests/` folder stays at root level (not inside `src/`) |

### Jupyter notebooks (`.ipynb`)

| Rule | Detail |
|------|--------|
| **Location** | `notebooks/` |
| **Root exception** | None — every notebook goes in `notebooks/` |
| **Subfolders** | Preserve feature-based grouping (e.g., `notebooks/jetank/`, `notebooks/camera/`) |
| **Misc notebooks** | Place one-off/experimental notebooks in `notebooks/misc/` |

### Configuration files

| File | Location | Reason |
|------|----------|--------|
| `setup.py` | Root | Needed by `pip install` |
| `config.yaml` | Root | Runtime config loaded by scripts |
| `pytest.ini` | Root | Pytest auto-discovery |
| `*.sh` | Root | Shell scripts run from project root |
| `.gitignore` | Root | Git convention |

## Import Conventions

```python
# Correct — always prefix with src.
from src.control.state_machine import StateMachine
from src.hardware.camera import CameraController
from src.perception.ball_detector import BallDetector

# Incorrect — will break after reorganization
from control.state_machine import StateMachine
from hardware.camera import CameraController
```

### In Jupyter notebooks

Add the project root to `sys.path` before importing:

```python
import sys, os
project_root = os.path.abspath(os.path.join(os.getcwd(), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.control.state_machine import StateMachine
```

### In pytest.ini

The `pythonpath = src` setting in `pytest.ini` ensures tests can import from `src/` without manipulation.

## Verification Checklist

Before finishing any file addition or move:

- [ ] No `.md` files in root except `README.md`, `LICENSE`, `AGENTS.md`
- [ ] No `.py` files in root except `setup.py`
- [ ] No `.ipynb` files outside `notebooks/`
- [ ] All Python imports use the `src.<module>.<file>` prefix
- [ ] `pytest` passes (run `python3 -m pytest tests/`)
- [ ] No hardcoded paths in moved notebooks/scripts that reference old locations
