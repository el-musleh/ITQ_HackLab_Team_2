#!/bin/bash
set -e

# Resolve project root from script location
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Activate virtual environment
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo "Error: Virtual environment not found at $PROJECT_ROOT/venv"
    echo "Run ./setup.sh first to create it."
    exit 1
fi
source "$PROJECT_ROOT/venv/bin/activate"

# Verify MuJoCo is installed
if ! python -c "import mujoco" 2>/dev/null; then
    echo "Error: MuJoCo package not found."
    echo "Install it with:  pip install mujoco>=3.0.0"
    exit 1
fi

# Run MuJoCo bottle-cap simulation
echo "Starting MuJoCo bottle-cap simulation..."
cd "$PROJECT_ROOT/src/simulation_mujoco/bottle-cap-sim"
python -m src.main
