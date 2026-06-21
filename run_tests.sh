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

# Run the test suite
echo "Running test suite..."
cd "$PROJECT_ROOT"
python3 -m pytest tests/ -v
