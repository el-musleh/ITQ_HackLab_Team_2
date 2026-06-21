# Bottle Cap Collector Simulation

Simulation of the **Autonomous Detection and Collection of Bottle Caps** robotics challenge.
The physical robot (Waveshare JETANK AI Kit) is replaced by a digital twin built in MuJoCo.

## Stage 1 — Arena Digital Twin

Stage 1 establishes the MuJoCo scene: arena, obstacles, basket, robot placeholder, and bottle caps.

### Arena specs

| Property | Value |
|---|---|
| Size | 1.75 m × 1.80 m |
| Boundary | Yellow walls |
| Caps | 22 (blue / red / silver) |
| Obstacles | 2 wooden crates near basket |
| Basket | Gray, open-top container |
| Time limit | 300 s |

### Robot placeholder (JETANK)

| Property | Value |
|---|---|
| Width (with tracks) | 0.19 m |
| Length | 0.17 m |
| Height | 0.25 m |

## Setup

```bash
cd bottle-cap-sim
pip install -r requirements.txt
```

Requires Python ≥ 3.9 and a display (MuJoCo viewer uses OpenGL).

## Run

```bash
# From inside bottle-cap-sim/
python -m src.main
```

This generates `assets/arena.xml` and opens the interactive MuJoCo viewer.

### Viewer controls

| Key / Mouse | Action |
|---|---|
| Left drag | Rotate camera |
| Right drag | Pan |
| Scroll | Zoom |
| `Space` | Pause / resume simulation |
| `Esc` | Exit |

## Project structure

```
bottle-cap-sim/
├── requirements.txt
├── src/
│   ├── config.py          # all constants (dimensions, colours, paths)
│   ├── scene_builder.py   # generates MJCF XML with random cap placement
│   ├── viewer.py          # launches MuJoCo interactive viewer
│   └── main.py            # entry point
└── assets/
    └── arena.xml          # generated scene (overwritten on each run)
```

## Roadmap

- **Stage 2** — Classical robotics controller (FSM + A\* path planning)
- **Stage 3** — Reinforcement learning agent (Gymnasium + Stable-Baselines3 PPO)
- **Stage 4** — Comparison experiments and plots
