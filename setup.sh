#!/bin/bash
set -e

echo "========================================"
echo "  ITQ Bottle Cap Collector — Setup"
echo "  Team 2 — AI & Robotics Hackathon"
echo "========================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Detect if we're on Jetson Nano
IS_JETSON=false
if [ -f /etc/nv_tegra_release ]; then
    IS_JETSON=true
    echo -e "${GREEN}Detected: NVIDIA Jetson Nano${NC}"
else
    echo -e "${YELLOW}Detected: Development machine (not Jetson)${NC}"
fi
echo ""

# ========================================
# Step 1: System Dependencies
# ========================================
echo -e "${YELLOW}[1/6] Installing system dependencies...${NC}"

sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgstreamer1.0-0 \
    libgstreamer-plugins-base1.0-0 \
    git \
    htop \
    i2c-tools \
    libi2c-dev \
    2>/dev/null || true

# Fix serial port permissions if on Jetson
if [ "$IS_JETSON" = true ]; then
    echo -e "${YELLOW}Fixing /dev/ttyTHS1 permissions...${NC}"
    sudo usermod -aG dialout $USER
    sudo chmod 777 /dev/ttyTHS1 2>/dev/null || true
fi

echo -e "${GREEN}System dependencies installed.${NC}"
echo ""

# ========================================
# Step 2: Python Virtual Environment
# ========================================
echo -e "${YELLOW}[2/6] Setting up Python virtual environment...${NC}"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}Virtual environment created.${NC}"
else
    echo -e "${GREEN}Virtual environment already exists.${NC}"
fi

source venv/bin/activate

echo -e "${GREEN}Virtual environment activated.${NC}"
echo ""

# ========================================
# Step 3: Python Dependencies
# ========================================
echo -e "${YELLOW}[3/6] Installing Python packages...${NC}"

# Core dependencies
pip install --upgrade pip
pip install \
    opencv-python \
    numpy \
    matplotlib \
    pyserial \
    imutils \
    requests \
    pyyaml \
    jupyter \
    ipywidgets \
    traitlets

# Detection (optional — color blob may be enough)
echo -e "${YELLOW}Installing Ultralytics YOLO (this may take a while)...${NC}"
pip install ultralytics || echo -e "${RED}YOLO install failed — will use HSV color blob fallback${NC}"

# Jetson-specific packages
if [ "$IS_JETSON" = true ]; then
    echo -e "${YELLOW}Installing Jetson-specific packages...${NC}"
    pip install jetson-stats || true
    # jetson-inference may need manual install from source
fi

echo -e "${GREEN}Python packages installed.${NC}"
echo ""

# ========================================
# Step 4: Install SCSCtrl (JETANK Servo Library)
# ========================================
echo -e "${YELLOW}[4/6] Installing SCSCtrl servo library...${NC}"

if [ -d "src/SCSCtrl" ]; then
    pip install -e . || pip install .
    echo -e "${GREEN}SCSCtrl installed from local source.${NC}"
else
    echo -e "${RED}src/SCSCtrl folder not found! Cloning from GitHub...${NC}"
    git clone https://github.com/waveshare/JETANK.git /tmp/JETANK
    cd /tmp/JETANK
    pip install -e . || pip install .
    cd "$PROJECT_DIR"
fi

echo ""

# ========================================
# Step 5: Create Project Structure
# ========================================
echo -e "${YELLOW}[5/6] Creating project directories...${NC}"

mkdir -p \
    src/perception \
    src/control \
    src/hardware \
    src/utils \
    tests \
    notebooks \
    logs

touch \
    src/__init__.py \
    src/perception/__init__.py \
    src/control/__init__.py \
    src/hardware/__init__.py \
    src/utils/__init__.py

# Create starter files if they don't exist
[ ! -f "src/main.py" ] && cat > src/main.py << 'PYEOF'
#!/usr/bin/env python3
"""Entry point for ITQ Bottle Cap Collector.

Run on NVIDIA Jetson Nano via Jupyter or command line.
"""

import sys
import time
from src.perception.detector import CapDetector
from src.hardware.chassis import Chassis
from src.hardware.arm import Arm
from src.control.state_machine import StateMachine

def main():
    print("=" * 50)
    print("ITQ Bottle Cap Collector — Team 2")
    print("=" * 50)
    
    # Initialize hardware
    detector = CapDetector()
    chassis = Chassis()
    arm = Arm()
    state_machine = StateMachine(detector, chassis, arm)
    
    print("Hardware initialized. Starting state machine...")
    print("Press Ctrl+C to stop.\n")
    
    try:
        while True:
            state_machine.tick()
            time.sleep(0.05)  # 20 Hz control loop
    except KeyboardInterrupt:
        print("\nShutting down...")
        chassis.stop()
        arm.reset()
        sys.exit(0)

if __name__ == "__main__":
    main()
PYEOF

[ ! -f "config.yaml" ] && cat > config.yaml << 'YAMLEOF'
# ITQ Bottle Cap Collector — Configuration

# Camera settings
camera:
  width: 320
  height: 240
  fps: 30
  source: 0  # CSI camera on Jetson

# Color detection (HSV)
# Adjust these on-site during calibration!
color:
  lower_hsv: [24, 100, 100]   # H, S, V min
  upper_hsv: [44, 255, 255]  # H, S, V max
  # Example presets:
  # yellow: [24, 100, 100] to [44, 255, 255]
  # red:    [160, 100, 100] to [180, 255, 255]
  # green:  [50, 200, 100] to [70, 255, 255]
  # blue:   [110, 180, 200] to [135, 225, 255]

# State machine tuning
state_machine:
  approach_distance_px: 50    # Stop when cap fills this many pixels
  search_rotate_speed: 30      # Degrees per second while searching
  approach_speed: 40           # Motor speed during approach
  recovery_timeout_sec: 5      # Back up if stuck for N seconds

# PID controller
pid:
  kp: 3.0   # Proportional gain
  ki: 0.0   # Integral gain
  kd: 0.5   # Derivative gain

# Servo IDs (JETANK hardware)
servos:
  pan: 1     # Camera pan servo
  tilt: 5    # Camera tilt servo
  arm_base: 2
  arm_shoulder: 3
  arm_elbow: 4
  gripper: 6

# Serial port
serial:
  port: /dev/ttyTHS1
  baudrate: 1000000
YAMLEOF

echo -e "${GREEN}Project structure created.${NC}"
echo ""

# ========================================
# Step 6: Verification
# ========================================
echo -e "${YELLOW}[6/6] Verifying installation...${NC}"
echo ""

echo "Python version:"
python3 --version

echo ""
echo "Checking key packages..."

python3 -c "import cv2; print(f'  OpenCV: {cv2.__version__}')" || echo -e "  ${RED}OpenCV: MISSING${NC}"
python3 -c "import numpy; print(f'  NumPy: {numpy.__version__}')" || echo -e "  ${RED}NumPy: MISSING${NC}"
python3 -c "import serial; print(f'  PySerial: OK')" || echo -e "  ${RED}PySerial: MISSING${NC}"
python3 -c "import SCSCtrl; print(f'  SCSCtrl: OK')" || echo -e "  ${RED}SCSCtrl: MISSING — run again or install manually${NC}"
python3 -c "import ultralytics; print(f'  Ultralytics: OK')" || echo -e "  ${YELLOW}Ultralytics: not installed (optional)${NC}"

echo ""
echo "Directory structure:"
ls -1F

echo ""
echo ""

# ========================================
# Done
# ========================================
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""

if [ "$IS_JETSON" = true ]; then
    echo -e "${GREEN}Next steps on Jetson Nano:${NC}"
    echo "  1. Activate venv:  source venv/bin/activate"
    echo "  2. Start Jupyter:    jupyter notebook --ip=0.0.0.0 --port=8888"
    echo "  3. Open browser:     http://<jetson-ip>:8888"
    echo "  4. Open notebooks/01_calibrate.ipynb"
    echo ""
    echo -e "${YELLOW}IMPORTANT:${NC} Log out and back in (or reboot) to apply dialout group permissions."
else
    echo -e "${GREEN}Next steps on dev machine:${NC}"
    echo "  1. Activate venv:  source venv/bin/activate"
    echo "  2. Edit code in:     src/"
    echo "  3. Test modules:     python3 -m pytest tests/"
    echo "  4. When ready, push: git push origin elmusleh"
    echo ""
    echo "  (This is a dev environment — robot hardware only works on the Jetson Nano)"
fi

echo ""
echo "Team members should run:"
echo "  ./setup.sh"
echo "  source venv/bin/activate"
echo ""
