# Run MuJoCo Sim Script

Create a shell script `run_mujoco_sim.sh` in the project root that activates the venv and launches the MuJoCo bottle-cap simulation.

## Script behavior
1. `cd` to the project root (via `$(dirname "$0")`)
2. `source venv/bin/activate`
3. `cd` into `src/simulation_mujoco/bottle-cap-sim`
4. Run `python -m src.main`
5. `set -e` so any failure aborts

## File to create
- `run_mujoco_sim.sh` (project root, `chmod +x`)

## Verification
```bash
./run_mujoco_sim.sh
```
Should activate venv and launch the MuJoCo viewer with 22 caps, diagonal obstacles, and cylindrical basket.
