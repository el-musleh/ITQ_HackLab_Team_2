# Camera Vision Learning System

A comprehensive set of interactive Jupyter notebooks to learn OpenCV, camera operations, and vision-based robot control.

## 📚 Notebooks Overview

### 1. `01_camera_basics.ipynb` - Camera Fundamentals
**Start here if you're new to OpenCV and cameras**

Learn:
- How to initialize and read from the camera
- Frame structure (height × width × channels)
- BGR vs RGB color formats
- Live camera feed implementation
- Camera pan/tilt servo control
- Capturing and saving snapshots

**Time:** 15-20 minutes

---

### 2. `02_vision_explained.ipynb` - Perception System Deep Dive
**Understand how the robot "sees"**

Learn:
- HSV color space and why it's better than BGR
- Ball detection using color segmentation
- Obstacle detection (yellow tape + edge detection)
- Basket detection and recognition
- Distance estimation from pixel area
- Interactive HSV tuning tool

**Time:** 30-40 minutes

---

### 3. `03_live_detection_viewer.ipynb` - Real-time Detection
**See the vision system in action**

Features:
- Live camera feed with all detection overlays
- Real-time ball, obstacle, and basket detection
- FPS counter and performance metrics
- Toggle individual detection layers
- Screenshot capture
- Interactive camera controls

**Time:** 20-30 minutes

---

### 4. `04_vision_control_interactive.ipynb` - Vision-Based Control
**Control the robot using vision feedback**

Features:
- Manual robot control (Forward, Back, Left, Right, Stop)
- Vision-assisted modes:
  - Approach Ball (PID tracking)
  - Return to Basket (PID navigation)
  - Auto-avoid obstacles
- Real-time motor speed display
- PID control explanation tool
- Learning mode showing calculations

**Time:** 30-45 minutes

---

## 🚀 Getting Started

### Prerequisites
```bash
# Activate virtual environment
source venv/bin/activate

# Ensure all dependencies are installed
pip install opencv-python numpy ipywidgets jupyter
```

### Launch Jupyter
```bash
# From project root
jupyter notebook notebooks/camera/
```

### Recommended Learning Path

1. **Complete beginner?** Start with `01_camera_basics.ipynb`
2. **Want to understand detection?** Go to `02_vision_explained.ipynb`
3. **See it in action?** Try `03_live_detection_viewer.ipynb`
4. **Ready to control?** Use `04_vision_control_interactive.ipynb`

---

## 🎯 What You'll Learn

### Camera & OpenCV Basics
- Camera initialization (JetBot vs OpenCV)
- Frame capture and display
- Color spaces (BGR, RGB, HSV)
- Image encoding and saving

### Computer Vision Techniques
- HSV color segmentation
- Contour detection and filtering
- Morphological operations (erosion, dilation)
- Edge detection (Canny)
- Region of Interest (ROI) processing

### Robot Perception
- Multi-color ball detection (blue, red, silver)
- Boundary detection (yellow tape)
- Obstacle detection (edge-based)
- Basket recognition
- Distance estimation

### Control Systems
- PID controller principles
- Vision-based tracking
- Differential drive control
- Priority-based action selection
- Safe autonomous navigation

---

## 💡 Tips for Success

### Camera Setup
- Ensure camera is connected before starting
- Center and tilt camera down for best ground view
- Adjust lighting if detection is poor

### Detection Tuning
- Use the HSV tuning tool in notebook 2
- Adjust color ranges for your lighting conditions
- Test with actual balls/obstacles in your environment

### Control Practice
- Start with low speeds (0.10-0.15)
- Enable auto-avoid for safety
- Practice manual control before trying vision modes
- Watch the PID explanation to understand tracking

### Troubleshooting
- **No camera?** Check `/dev/video*` devices
- **Poor detection?** Tune HSV ranges in notebook 2
- **Slow FPS?** Reduce resolution in config.yaml
- **Motors not working?** Check robot initialization in notebook 4

---

## 📊 Detection Parameters

### Ball Detection
- **Colors:** Blue, Red, Silver (bottle caps)
- **Min area:** 100 pixels²
- **Known diameter:** 3.5 cm
- **Method:** HSV color segmentation + circularity filtering

### Obstacle Detection
- **Yellow boundary:** HSV range [20-40, 100-255, 100-255]
- **Threshold:** 1800 pixels
- **Edge detection:** Canny (50, 150)
- **ROIs:** Bottom 30% (boundary), Middle 15-65% (obstacles)

### Basket Detection
- **Method:** Color + shape recognition
- **Distance:** Calculated from contour area
- **Bearing:** Angle from frame center

---

## 🔧 Configuration

Edit `config.yaml` to adjust:
- Camera resolution and FPS
- HSV color ranges for each ball color
- Obstacle detection thresholds
- Motor speeds and PID parameters

---

## 🎓 Learning Outcomes

After completing all notebooks, you will:
- ✅ Understand OpenCV camera operations
- ✅ Know how HSV color detection works
- ✅ Be able to tune vision parameters
- ✅ Understand PID control for tracking
- ✅ Control the robot using vision feedback
- ✅ Debug and troubleshoot vision issues

---

## 📝 Next Steps

Once comfortable with these notebooks:
1. Review the main perception modules in `/perception`
2. Study the control system in `/control`
3. Try the full autonomous navigation in `/notebooks/06_full_run.ipynb`
4. Experiment with your own detection algorithms

---

## 🆘 Need Help?

- Check the troubleshooting sections in each notebook
- Review the code comments in `/hardware` and `/perception`
- Test individual components using `/robot_tests`
- Consult the main project README

---

**Happy Learning! 🤖📷**
