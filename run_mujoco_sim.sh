#!/bin/bash
set -e

# Resolve project root from script location
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Activate virtual environment
source "$PROJECT_ROOT/venv/bin/activate"

# Run MuJoCo bottle-cap simulation
cd "$PROJECT_ROOT/src/simulation_mujoco/bottle-cap-sim"
python -m src.main
