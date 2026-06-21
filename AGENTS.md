# AGENTS.md — AI Agent Instructions

> **Read this file before making any changes to the ITQ_HackLab_Team_2 project.**

## Quick Reference

| File type | Where it goes | Root exceptions |
|-----------|---------------|-----------------|
| `.md` | `docs/` | `README.md`, `LICENSE`, `AGENTS.md` |
| `.py` | `src/` | `setup.py` |
| `.ipynb` | `notebooks/` | None |
| Config (`.yaml`, `.ini`, `.sh`, `.cfg`, `.txt`) | Root | — |
| Tests (`.py`) | `tests/` | — |

## Full Structure Guide

See **[docs/ai-project-structure.md](docs/ai-project-structure.md)** for the complete folder layout, import conventions, and verification checklist.

## Import Convention

Always prefix imports with `src.`:

```python
from src.control.state_machine import StateMachine
from src.hardware.camera import CameraController
from src.perception.ball_detector import BallDetector
```

Never use bare module imports like `from control.X import Y` — they will break.

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `src/control/` | State machine, PID, navigator, recovery |
| `src/hardware/` | Chassis, arm, camera hardware interfaces |
| `src/perception/` | Ball, basket, obstacle detection |
| `src/simulation/` | Simulation core, hardware sim, demos |
| `src/SCSCtrl/` | Waveshare servo SDK |
| `src/utils/` | Shared utilities |
| `tests/` | Pytest test suite |
| `notebooks/` | All Jupyter notebooks |
| `docs/` | All documentation |

## Before You Finish

Run this checklist:

- [ ] No `.md` in root except `README.md`, `LICENSE`, `AGENTS.md`
- [ ] No `.py` in root except `setup.py`
- [ ] No `.ipynb` outside `notebooks/`
- [ ] All imports use `src.<module>.<file>` prefix
- [ ] `python3 -m pytest tests/` passes

## Workflow File

An executable workflow is available at `.windsurf/workflows/organize-files.md`. Use `/organize-files` to invoke it.
