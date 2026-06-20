import json
import os

def build_notebook():
    notebook = {
     "cells": [
      {
       "cell_type": "markdown",
       "metadata": {},
       "source": [
        "# 📷 Camera Diagnostic Suite & Hardware Verifier\n",
        "\n",
        "Use this notebook to capture actual raw test frames from both V4L2 and GStreamer, save them to the filesystem, and diagnose basic actuator movement (motors and servos)."
       ]
      },
      {
       "cell_type": "markdown",
       "metadata": {},
       "source": [
        "### [1] Reset Hardware Lock\n",
        "Run this cell first to release any active locks on the camera socket."
       ]
      },
      {
       "cell_type": "code",
       "execution_count": None,
       "metadata": {},
       "outputs": [],
       "source": [
        "from jetbot import Robot, Camera\n",
        "try:\n",
        "    robot = Robot()\n",
        "    robot.stop()\n",
        "    print(\"Motors stopped.\")\n",
        "except Exception:\n",
        "    pass\n",
        "try:\n",
        "    camera = Camera.instance()\n",
        "    camera.unobserve_all()\n",
        "    camera.stop()\n",
        "    print(\"Camera resource released.\")\n",
        "except Exception:\n",
        "    pass"
       ]
      },
      {
       "cell_type": "markdown",
       "metadata": {},
       "source": [
        "### [2] Test V4L2 Direct Frame Capture\n",
        "Attempts to capture a frame from `/dev/video0` directly via V4L2, saves it as `v4l2_capture.jpg`, and prints pixel channel statistics."
       ]
      },
      {
       "cell_type": "code",
       "execution_count": None,
       "metadata": {},
       "outputs": [],
       "source": [
        "import cv2\n",
        "import numpy as np\n",
        "import os\n",
        "\n",
        "print(\"Opening camera via V4L2...\")\n",
        "cap = cv2.VideoCapture(0, cv2.CAP_V4L2)\n",
        "if cap.isOpened():\n",
        "    print(\"V4L2 driver opened /dev/video0. Reading frame...\")\n",
        "    re, img = cap.read()\n",
        "    cap.release()\n",
        "    if re:\n",
        "        # Save image\n",
        "        cv2.imwrite(\"v4l2_capture.jpg\", img)\n",
        "        print(\"SUCCESS: Captured frame saved to v4l2_capture.jpg\")\n",
        "        print(\"Image Dimensions:\", img.shape)\n",
        "        \n",
        "        mean_b = np.mean(img[:, :, 0])\n",
        "        mean_g = np.mean(img[:, :, 1])\n",
        "        mean_r = np.mean(img[:, :, 2])\n",
        "        print(\"Mean Color Values (BGR): Blue={:.1f}, Green={:.1f}, Red={:.1f}\".format(mean_b, mean_g, mean_r))\n",
        "        \n",
        "        if mean_g > 100 and mean_b < 10 and mean_r < 10:\n",
        "            print(\"🚨 ANALYSIS: Solid Green Screen detected! Camera sensor is not streaming data (connection issue).\")\n",
        "        elif np.all(img == 0):\n",
        "            print(\"🚨 ANALYSIS: Solid Black Screen detected!\")\n",
        "        else:\n",
        "            print(\"🎉 ANALYSIS: Real image data detected (non-static colors)!\")\n",
        "    else:\n",
        "        print(\"ERROR: VideoCapture opened, but failed to read any pixels.\")\n",
        "else:\n",
        "    print(\"ERROR: Could not open /dev/video0. Device busy or not found.\")"
       ]
      },
      {
       "cell_type": "markdown",
       "metadata": {},
       "source": [
        "### [3] Test GStreamer Frame Capture\n",
        "Attempts to capture a frame using the GStreamer nvarguscamerasrc pipeline and saves it as `gstreamer_capture.jpg`."
       ]
      },
      {
       "cell_type": "code",
       "execution_count": None,
       "metadata": {},
       "outputs": [],
       "source": [
        "import cv2\n",
        "import numpy as np\n",
        "\n",
        "gst_str = 'nvarguscamerasrc sensor-mode=3 ! video/x-raw(memory:NVMM), width=320, height=240, format=(string)NV12, framerate=(fraction)30/1 ! nvvidconv ! video/x-raw, width=(int)320, height=(int)240, format=(string)BGRx ! videoconvert ! appsink'\n",
        "\n",
        "print(\"Opening GStreamer pipeline...\")\n",
        "cap = cv2.VideoCapture(gst_str, cv2.CAP_GSTREAMER)\n",
        "if cap.isOpened():\n",
        "    print(\"GStreamer opened successfully. Reading frame...\")\n",
        "    re, img = cap.read()\n",
        "    cap.release()\n",
        "    if re:\n",
        "        cv2.imwrite(\"gstreamer_capture.jpg\", img)\n",
        "        print(\"SUCCESS: Captured GStreamer frame saved to gstreamer_capture.jpg\")\n",
        "    else:\n",
        "        print(\"ERROR: GStreamer pipeline opened, but failed to read pixels.\")\n",
        "else:\n",
        "    print(\"ERROR: Failed to open GStreamer pipeline. Argus service crashed or busy.\")"
       ]
      },
      {
       "cell_type": "markdown",
       "metadata": {},
       "source": [
        "### [4] Actuator Quick Verification\n",
        "Moves motors and robotic arm servos slightly to verify basic electronic signaling is functional."
       ]
      },
      {
       "cell_type": "code",
       "execution_count": None,
       "metadata": {},
       "outputs": [],
       "source": [
        "import time\n",
        "from jetbot import Robot\n",
        "try:\n",
        "    from SCSCtrl import TTLServo\n",
        "    _servo = True\n",
        "except ImportError:\n",
        "    _servo = False\n",
        "\n",
        "print(\"Testing Left crawler motor (0.15 speed)...\")\n",
        "robot = Robot()\n",
        "robot.left_motor.value = 0.15\n",
        "time.sleep(0.4)\n",
        "robot.left_motor.value = 0.0\n",
        "\n",
        "if _servo:\n",
        "    print(\"Testing pan servo (10 deg)...\")\n",
        "    TTLServo.servoAngleCtrl(1, 10, 1, 100)\n",
        "    time.sleep(0.5)\n",
        "    TTLServo.servoAngleCtrl(1, 0, 1, 100)\n",
        "    print(\"Diagnostics run completed.\")\n",
        "else:\n",
        "    print(\"Robotic arm servos not available.\")"
       ]
      }
     ],
     "metadata": {
      "kernelspec": {
       "display_name": "Python 3",
       "language": "python",
       "name": "python3"
      },
      "language_info": {
       "codemirror_mode": {
        "name": "ipython",
        "version": 3
       },
       "file_extension": ".py",
       "mimetype": "text/x-python",
       "name": "python",
       "nbconvert_exporter": "python",
       "pygments_lexer": "ipython3",
       "version": "3.6.9"
      }
     },
     "nbformat": 4,
     "nbformat_minor": 4
    }
    
    dest_path = "/workspace/itq-bottle-cap-collector/camera_diagnostic_suite.ipynb"
    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)
    print(f"Created manager notebook at {dest_path}")

if __name__ == "__main__":
    build_notebook()
