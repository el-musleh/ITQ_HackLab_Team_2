import json
import os

# Auto-detect project root by searching for config.yaml marker
project_root = os.getcwd()
while not os.path.exists(os.path.join(project_root, 'config.yaml')) and project_root != '/':
    project_root = os.path.dirname(project_root)

def build_notebook():
    notebook = {
     "cells": [
      {
       "cell_type": "markdown",
       "metadata": {},
       "source": [
        "# 🚨 Robot Manager & Diagnostics Suite\n",
        "\n",
        "Use this notebook to control the robot components, perform emergency shutdown operations, and run diagnostic diagnostics on each component (motors, arm servos, and camera stream)."
       ]
      },
      {
       "cell_type": "markdown",
       "metadata": {},
       "source": [
        "## 🛑 EMERGENCY SHUTDOWN\n",
        "\n",
        "Run the cell below immediately to stop all motors, zero speed values, and stop/release the camera socket."
       ]
      },
      {
       "cell_type": "code",
       "execution_count": None,
       "metadata": {},
       "outputs": [],
       "source": [
        "# 🚨 EMERGENCY STOP\n",
        "from jetbot import Robot, Camera\n",
        "try:\n",
        "    robot = Robot()\n",
        "    robot.stop()\n",
        "    print(\"🚨 ROBOT MOTORS SHUT DOWN SUCCESSFULLY.\")\n",
        "except Exception as e:\n",
        "    print(\"Failed to stop motors:\", e)\n",
        "\n",
        "try:\n",
        "    camera = Camera.instance()\n",
        "    camera.unobserve_all()\n",
        "    camera.stop()\n",
        "    print(\"🚨 CAMERA STREAM STOPPED AND RESOURCE RELEASED.\")\n",
        "except Exception as e:\n",
        "    print(\"Failed to release camera:\", e)"
       ]
      },
      {
       "cell_type": "markdown",
       "metadata": {},
       "source": [
        "## 🔄 Initialize All Components\n",
        "\n",
        "Run this cell to setup connection with the Robot base, reset the camera tilt position, and open the video stream (utilizing our direct V4L2 fallback if GStreamer is locked)."
       ]
      },
      {
       "cell_type": "code",
       "execution_count": None,
       "metadata": {},
       "outputs": [],
       "source": [
        "import time\n",
        "import numpy as np\n",
        "from jetbot import Robot, Camera\n",
        "try:\n",
        "    from SCSCtrl import TTLServo\n",
        "    _servo_available = True\n",
        "except Exception as e:\n",
        "    _servo_available = False\n",
        "    print(\"Servo control driver not available.\")\n",
        "\n",
        "print(\"Connecting to motors...\")\n",
        "robot = Robot()\n",
        "robot.stop()\n",
        "print(\"Motors ready.\")\n",
        "\n",
        "if _servo_available:\n",
        "    print(\"Centering servos...\")\n",
        "    TTLServo.servoAngleCtrl(1, 0, 1, 100) # Center Pan\n",
        "    time.sleep(0.15)\n",
        "    TTLServo.servoAngleCtrl(5, 0, 1, 100) # Center Tilt\n",
        "    print(\"Servos ready.\")\n",
        "\n",
        "print(\"Initializing camera (GStreamer with V4L2 fallback)...\")\n",
        "camera = Camera.instance(width=320, height=240)\n",
        "print(\"Camera ready. Frame shape:\", camera.value.shape if hasattr(camera, 'value') else 'Unknown')"
       ]
      },
      {
       "cell_type": "markdown",
       "metadata": {},
       "source": [
        "## 🏎️ Test 1 — Motors\n",
        "\n",
        "Runs left motor forward for 0.5s, right motor forward for 0.5s, then both forward for 0.5s before stopping."
       ]
      },
      {
       "cell_type": "code",
       "execution_count": None,
       "metadata": {},
       "outputs": [],
       "source": [
        "print(\"Testing Left Motor...\")\n",
        "robot.left_motor.value = 0.15\n",
        "time.sleep(0.5)\n",
        "robot.left_motor.value = 0.0\n",
        "\n",
        "time.sleep(0.5)\n",
        "\n",
        "print(\"Testing Right Motor...\")\n",
        "robot.right_motor.value = 0.15\n",
        "time.sleep(0.5)\n",
        "robot.right_motor.value = 0.0\n",
        "\n",
        "time.sleep(0.5)\n",
        "\n",
        "print(\"Testing Both Forward...\")\n",
        "robot.forward(0.15)\n",
        "time.sleep(0.5)\n",
        "robot.stop()\n",
        "\n",
        "print(\"Motor diagnostics finished.\")"
       ]
      },
      {
       "cell_type": "markdown",
       "metadata": {},
       "source": [
        "## 🦾 Test 2 — Robotic Arm & Camera Tilt Servos\n",
        "\n",
        "Tests Pan, Tilt, and Claw movement sequentially."
       ]
      },
      {
       "cell_type": "code",
       "execution_count": None,
       "metadata": {},
       "outputs": [],
       "source": [
        "if _servo_available:\n",
        "    print(\"Moving Camera Pan (Servo 1) left and right...\")\n",
        "    TTLServo.servoAngleCtrl(1, -30, 1, 100)\n",
        "    time.sleep(0.5)\n",
        "    TTLServo.servoAngleCtrl(1, 30, 1, 100)\n",
        "    time.sleep(0.5)\n",
        "    TTLServo.servoAngleCtrl(1, 0, 1, 100)\n",
        "    time.sleep(0.3)\n",
        "    \n",
        "    print(\"Moving Camera Tilt (Servo 5) down and up...\")\n",
        "    TTLServo.servoAngleCtrl(5, 20, 1, 100)\n",
        "    time.sleep(0.5)\n",
        "    TTLServo.servoAngleCtrl(5, 0, 1, 100)\n",
        "    time.sleep(0.3)\n",
        "    \n",
        "    print(\"Opening and closing Claw (Servo 4)...\")\n",
        "    TTLServo.servoAngleCtrl(4, -10, 1, 100) # Open\n",
        "    time.sleep(0.5)\n",
        "    TTLServo.servoAngleCtrl(4, -75, 1, 100) # Close\n",
        "    time.sleep(0.5)\n",
        "    TTLServo.servoAngleCtrl(4, -10, 1, 100) # Open\n",
        "    print(\"Servo diagnostics complete.\")\n",
        "else:\n",
        "    print(\"Servos not available. Skipping servo diagnostics.\")"
       ]
      },
      {
       "cell_type": "markdown",
       "metadata": {},
       "source": [
        "## 📷 Test 3 — Camera Live View\n",
        "\n",
        "Displays a live streaming viewport from the V4L2 camera in the browser using widgets."
       ]
      },
      {
       "cell_type": "code",
       "execution_count": None,
       "metadata": {},
       "outputs": [],
       "source": [
        "import ipywidgets as widgets\n",
        "from IPython.display import display\n",
        "from jetbot import bgr8_to_jpeg\n",
        "import traitlets\n",
        "\n",
        "image_widget = widgets.Image(format='jpeg', width=320, height=240)\n",
        "display(image_widget)\n",
        "\n",
        "camera_link = traitlets.dlink((camera, 'value'), (image_widget, 'value'), transform=bgr8_to_jpeg)\n",
        "print(\"Live preview active. Remember to shutdown this kernel or run the Emergency Stop cell when leaving!\")"
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
    
    dest_path = os.path.join(project_root, "robot_manager.ipynb")
    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)
    print(f"Created manager notebook at {dest_path}")

if __name__ == "__main__":
    build_notebook()
