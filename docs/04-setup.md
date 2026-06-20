# Setup Guide

## Laptop Setup (Dev Environment)

```bash
cd itq-bottle-cap-collector
./setup.sh
source venv/bin/activate
```

This installs: OpenCV, NumPy, PySerial, Ultralytics, Jupyter, SCSCtrl.

## Jetson Setup (Docker Container)

The Jetson runs in a Docker container with some quirks:

### What Works
- `git clone` from GitHub
- `pip install`
- `python3`, `cv2`, `jetbot` pre-installed
- Internet access

### What Does NOT Work
- `sudo` (you are already root)
- `systemctl` (no systemd in container)
- `sshd` (no SSH daemon)
- The `setup.sh` script's `sudo` and Jetson detection

### Manual Setup on Jetson

```bash
cd /workspace

# 1. Clone the project
git clone https://github.com/el-musleh/ITQ_HackLab_Team_2.git itq-bottle-cap-collector

# 2. Create venv (no sudo needed)
cd itq-bottle-cap-collector
python3 -m venv venv
source venv/bin/activate

# 3. Install packages manually
pip install --upgrade pip
pip install opencv-python numpy matplotlib pyserial imutils jupyter ipywidgets traitlets pyyaml

# 4. Install SCSCtrl from local source
pip install -e .

# 5. Verify
python3 -c "import cv2; import SCSCtrl; print('All OK')"
```

### Git Config on Jetson (Required Before Commit)

```bash
git config user.name "Mohammad El Musleh"
git config user.email "your-github-email@example.com"
```

## Project Structure After Setup

```
/workspace/
├── JETANK/                    # Official examples (REFERENCE — do not modify)
│   ├── JETANK_1_servos/
│   ├── JETANK_2_ctrl/
│   ├── JETANK_5_colorTracking/
│   └── SCSCtrl/
│
└── itq-bottle-cap-collector/  # YOUR project
    ├── main.py
    ├── config.yaml
    ├── setup.sh
    ├── venv/
    ├── perception/
    ├── control/
    ├── hardware/
    ├── utils/
    ├── robot_tests/
    └── notebooks/
```

> **Rule:** Keep `JETANK/` as reference. Do all work in `itq-bottle-cap-collector/`.
