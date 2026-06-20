# Quick Reference Card

## Network

| | |
|---|---|
| WiFi SSID | `TP-LINK_744C` |
| WiFi Password | `15253354` |
| Jetson IP | `192.168.0.100` |
| Jupyter URL | `http://192.168.0.100:8888/lab` |
| Jupyter Password | `CIC@Tics1XAI` |

## Commands

### Laptop → Jetson (No SSH — Use Jupyter Instead)

```bash
# Open Jupyter in browser
http://192.168.0.100:8888/lab

# Then: File → New → Terminal (this IS the Jetson shell)
```

### Git (On Jetson Jupyter Terminal)

```bash
cd /workspace/itq-bottle-cap-collector
git config user.name "Mohammad El Musleh"
git config user.email "your-email@example.com"
git add -A
git commit -m "message"
git push origin $(git branch --show-current)
# Password: use GitHub Personal Access Token
```

### Store Token Permanently

```bash
git config credential.helper store
git push origin $(git branch --show-current)
# Enter token once — saved forever
```

### Manual Setup on Jetson (If setup.sh fails)

```bash
cd /workspace/itq-bottle-cap-collector
python3 -m venv venv
source venv/bin/activate
pip install opencv-python numpy matplotlib pyserial imutils jupyter ipywidgets traitlets pyyaml
pip install -e .
python3 -c "import cv2; import SCSCtrl; print('OK')"
```

### Camera Test

```bash
python3 -c "from jetbot import Camera; c = Camera.instance(); print('Camera OK')"
```

### Servo Test

```bash
python3 -c "from SCSCtrl import TTLServo; TTLServo.servoAngleCtrl(1, 0, 1, 150); print('Servo OK')"
```

### Fix Serial Port Permissions

```bash
chmod 777 /dev/ttyTHS1
```

### Restart Jupyter Kernel

```
Right-click notebook tab → Shut Down Kernel → Reopen notebook
```

## File Locations

| Path | What |
|------|------|
| `/workspace/JETANK/` | Official JETANK examples (REFERENCE) |
| `/workspace/JETANK/JETANK_5_colorTracking/colorTracking_en.ipynb` | Cap detection starter |
| `/workspace/JETANK/JETANK_1_servos/JETANK_1_servos_en.ipynb` | Servo test |
| `/workspace/JETANK/JETANK_2_ctrl/JETANK_2_ctrl_en.ipynb` | Chassis test |
| `/workspace/itq-bottle-cap-collector/` | Your project |
| `/workspace/itq-bottle-cap-collector/config.yaml` | Tuning parameters |

## Important Rules

1. **Never delete `JETANK/`** — keep as reference
2. **Never commit `venv/`** — it's in `.gitignore`
3. **Restart kernel often** — Jetson has 4GB RAM
4. **Save before every run** — `Ctrl+S`
5. **One notebook at a time** — RAM limits
6. **Camera resolution: 320×240** — faster detection

## Team Contacts

| Name | Role | Module |
|------|------|--------|
| Yashveer Sookun | Vision | `perception/` |
| Salawu Wareeth | Logging | `utils/telemetry.py` |
| Mohammed Abubakr Khan | QA | `robot_tests/` |
| Joaquín Morillo Soto | Hardware | `hardware/` |
| Mohammad El Musleh | Control + Operator | `control/` |
| Myron Sydorov | Recovery | `control/recovery.py` |

## Event Info

- **Event:** AI & Robotics Hackathon Berlin
- **Team:** Team 2
- **Track:** ITQ
- **Robot:** Waveshare JETANK on NVIDIA Jetson Nano
