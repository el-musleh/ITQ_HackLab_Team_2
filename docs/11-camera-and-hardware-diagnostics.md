# Camera and Hardware Diagnostics

This document outlines the detailed findings and solutions for the Jetson CSI Camera, robotic arm servos, and headless simulation configurations developed during troubleshooting.

---

## 1. Jetson CSI Camera Diagnostics

### The "Solid Green Screen" Issue
* **Symptom:** The camera feed in notebooks displays a solid, static green color (`RGB 0, 135, 0`).
* **Root Cause:** In Linux Video4Linux2 (V4L2), a green screen indicates that the device driver successfully bound `/dev/video0` and opened the capture stream, but the **physical camera sensor is not sending any pixel clock or data lanes over the MIPI CSI bus**. 
  * Because the sensor fails to stream, the capture DMA buffers remain filled with absolute `0` bytes. 
  * When OpenCV converts a zeroed YUV/YCbCr buffer to BGR, the midpoints map mathematically to solid green.
* **Physical Cause:** Loose, slightly tilted, or backward-facing contacts on the camera ribbon cable. (The I2C control pins connect first, allowing successful kernel probing, but high-speed differential clock/data pins fail to connect).
* **Physical Fix:**
  1. **Shut down and unplug** the Jetson Nano completely (never hot-plug the ribbon cable, as it can burn the sensor).
  2. Pull out the camera ribbon cable.
  3. Verify the **contacts orientation**: For the CAM1 slot, the silver metal contacts must face **inward** (towards the processor/heatsink) and the blue backing tape must face **outward**.
  4. Insert the ribbon cable completely straight and lock the plastic clamp down firmly.

### GStreamer Daemon Lockups
* **Symptom:** Notebook calls to `Camera.instance()` hang indefinitely or time out.
* **Cause:** The NVIDIA Argus service (`nvargus-daemon`) on the host system locks up when a Python/Jupyter process exits abruptly without releasing the camera handle.
* **Host Reset Command (run on Host OS shell):**
  ```bash
  sudo systemctl restart nvargus-daemon
  ```
  *(Note: Since the Jupyter environment runs inside a Docker container, systemd is unavailable within the container. This command must be executed on the physical Jetson Nano host shell directly or via SSH).*

### OpenCV V4L2 Fallback Integration
To solve GStreamer nvargus daemon crashes, we modified the global `jetbot` camera library (`opencv_gst_camera.py`) to automatically fall back to direct V4L2 streaming if GStreamer fails:
1. It attempts to open `nvarguscamerasrc` GStreamer pipeline.
2. On failure, it falls back to `cv2.VideoCapture(0, cv2.CAP_V4L2)`.
3. It captures high-resolution frames directly from `/dev/video0` and resizes them on-the-fly to the requested dimensions (e.g. `320x240`) using OpenCV's fast `cv2.resize()`, taking only ~3.5ms per frame.

---

## 2. Actuator and Port Conflicts

### Multi-Kernel Resource Conflicts
* **Symptom:** Camera or V4L2 direct capture fails with `can't open camera by index` or busy errors.
* **Cause:** Multiple Jupyter notebook tabs open in the web browser. Jupyter Lab automatically spins up and keeps background Python kernels active for each open tab. Since `/dev/video0` is a hardware-exclusive resource, only one active kernel can lock it at a time.
* **Fix:** In Jupyter Lab, click the **Running Terminals and Kernels** tab in the left sidebar (circle icon with square inside) and click **Shut Down All** kernels except your active workspace notebook.

### Servo Non-Blocking Driver
* **Symptom:** importing `TTLServo` or `servoInt` blocks forever or crashes with `getch()` keyboard read prompts on failure to open the `/dev/ttyTHS1` serial port.
* **Fix:** The driver code (`SCSCtrl/TTLServo.py` and `servoInt.py`) was updated to track a `port_opened` boolean variable:
  * Port open failure is captured gracefully, printing a warning instead of calling `getch()` and `quit()`.
  * If `port_opened` is `False`, all serial writes are bypassed, and serial reads return a neutral mid-point position (`512`), allowing the codebase to load and run cleanly in mock/headless testing environments.

---

## 3. Headless/Mock Testing Environment

For automated container testing, standard GPU/hardware dependencies are mocked globally at the python level using `/etc/python3.6/sitecustomize.py`.

### Implemented Global Mock Hooks:
* **TensorRT & torch2trt:** If they fail to import (e.g., in a CPU-only sandbox), they are replaced dynamically with mock modules containing dummy `Logger`, `init_libnvinfer_plugins`, and a `TRTModule` returning zeroed prediction tensors.
* **Missing Checkpoints (`.pth` files):** Intercepts `torch.load()` requests for non-existent weight files and returns an empty dictionary. It also patches `nn.Module.load_state_dict()` to ignore state-dict load operations on empty inputs, allowing notebooks to bypass model-loading errors.

---

## 4. Quick Diagnostics

You can run diagnostics directly using [camera_diagnostic_suite.ipynb](file:///workspace/itq-bottle-cap-collector/camera_diagnostic_suite.ipynb) or the Python command line script:
```bash
python3 tests/camera_diagnostic.py
```
