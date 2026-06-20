#!/usr/bin/env python3
"""
navigation.py — Autonomous bottle-cap detection and collection.
JETANK AI Kit · Jetson Nano

Run:
    python3 navigation.py

Stop:
    Ctrl+C  (motors are zeroed before exit)
"""

import cv2
import numpy as np
import time
import threading
import signal
import sys
import base64
import json
from urllib import request as _ul_req

from jetbot import Camera, Robot

try:
    from SCSCtrl import TTLServo
    _servo_available = True
except Exception:
    _servo_available = False
    print('TTLServo not available — camera tilt skipped.')

# ── Configuration ─────────────────────────────────────────────────────────
CAMERA_WIDTH     = 300
CAMERA_HEIGHT    = 300
CAMERA_TILT_DOWN = 22

FORWARD_SPEED = 0.18
REVERSE_SPEED = 0.15
TURN_SPEED    = 0.22
MAX_SPEED     = 0.25

AVOID_REVERSE_TIME = 0.40
AVOID_TURN_TIME    = 0.55

YELLOW_ROI_START      = 0.65
FRONT_ROI_TOP_FRAC    = 0.15
FRONT_ROI_BOTTOM_FRAC = 0.60

YELLOW_BOUNDARY_THRESHOLD = 900
OBSTACLE_EDGE_THRESHOLD   = 500
OBSTACLE_EQUAL_THRESH     = 50

TAPE_HSV_LOWER = np.array([15,  60,  60])
TAPE_HSV_UPPER = np.array([45, 255, 255])

CANNY_LOW  = 40
CANNY_HIGH = 120

ROBOFLOW_API_KEY     = "Ub1KVwtGHHdLLKRzoxdG"
ROBOFLOW_API_URL     = "https://serverless.roboflow.com/kais-workspace-stbmo/workflows/detect-count-and-visualize-3"
CONFIDENCE_THRESHOLD = 0.80
TARGET_CLASS         = "bottle cap"
INFERENCE_INTERVAL   = 0.75   # seconds between Roboflow API calls

SCAN_TURN_SPEED  = 0.12
APPROACH_SPEED   = 0.08
CENTER_TOLERANCE = 30     # px from frame centre to consider cap "centred"
CAP_CLOSE_SIZE   = 80     # bounding box px (width or height) → AT_CAP

# Optional config.yaml override
try:
    import yaml
    with open("config.yaml", encoding="utf-8") as _f:
        _cfg = yaml.safe_load(_f)
    CAMERA_WIDTH  = _cfg["camera"].get("width",  CAMERA_WIDTH)
    CAMERA_HEIGHT = _cfg["camera"].get("height", CAMERA_HEIGHT)
    _lo = _cfg["color"].get("lower_hsv")
    _hi = _cfg["color"].get("upper_hsv")
    if _lo: TAPE_HSV_LOWER = np.array(_lo)
    if _hi: TAPE_HSV_UPPER = np.array(_hi)
    print("config.yaml loaded.")
except Exception as _e:
    print("config.yaml not loaded (%s) — using defaults." % _e)

# ── Hardware init ─────────────────────────────────────────────────────────
if _servo_available:
    try:
        TTLServo.servoAngleCtrl(1, 0, 1, 100)
        time.sleep(0.15)
        TTLServo.servoAngleCtrl(5, CAMERA_TILT_DOWN, 1, 100)
        time.sleep(0.50)
        print('Camera: pan centred, tilt down %d deg.' % CAMERA_TILT_DOWN)
    except Exception as e:
        print('Servo init error:', e)

camera = Camera.instance(width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
robot  = Robot()
robot.stop()
print('Camera + Robot ready.')

# ── Helpers ───────────────────────────────────────────────────────────────
def clamp(val, lo, hi):
    return max(lo, min(hi, val))

def safe_stop():
    try:
        robot.left_motor.value  = 0.0
        robot.right_motor.value = 0.0
    except Exception:
        pass

def set_drive(left, right):
    try:
        robot.left_motor.value  = clamp(left,  -MAX_SPEED, MAX_SPEED)
        robot.right_motor.value = clamp(right, -MAX_SPEED, MAX_SPEED)
    except Exception:
        pass

# ── Yellow boundary detection ─────────────────────────────────────────────
def detect_yellow_boundary(frame):
    h         = frame.shape[0]
    roi_start = int(h * YELLOW_ROI_START)
    roi       = frame[roi_start:, :]

    hsv_roi  = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    roi_mask = cv2.inRange(hsv_roi, TAPE_HSV_LOWER, TAPE_HSV_UPPER)

    yellow_area  = int(np.sum(roi_mask > 0))
    mid          = roi_mask.shape[1] // 2
    yellow_left  = int(np.sum(roi_mask[:, :mid] > 0))
    yellow_right = int(np.sum(roi_mask[:, mid:] > 0))

    return {
        'detected':     yellow_area >= YELLOW_BOUNDARY_THRESHOLD,
        'yellow_area':  yellow_area,
        'yellow_left':  yellow_left,
        'yellow_right': yellow_right,
    }

# ── Obstacle detection ────────────────────────────────────────────────────
def detect_obstacle(frame):
    h, w    = frame.shape[:2]
    roi_top = int(h * FRONT_ROI_TOP_FRAC)
    roi_bot = int(h * FRONT_ROI_BOTTOM_FRAC)
    roi     = frame[roi_top:roi_bot, :]

    hsv_roi     = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    yellow_mask = cv2.inRange(hsv_roi, TAPE_HSV_LOWER, TAPE_HSV_UPPER)

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray[yellow_mask > 0] = 0

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges   = cv2.Canny(blurred, CANNY_LOW, CANNY_HIGH)
    edges   = cv2.dilate(edges, None, iterations=1)

    mid        = edges.shape[1] // 2
    edge_left  = int(np.sum(edges[:, :mid] > 0))
    edge_right = int(np.sum(edges[:, mid:] > 0))

    return {
        'detected':   edge_left + edge_right >= OBSTACLE_EDGE_THRESHOLD,
        'edge_left':  edge_left,
        'edge_right': edge_right,
    }

# ── Roboflow inference ────────────────────────────────────────────────────
def _infer_frame(frame):
    ok, enc = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise RuntimeError('JPEG encode failed')
    b64 = base64.b64encode(enc.tobytes()).decode('utf-8')
    payload = {
        'api_key': ROBOFLOW_API_KEY,
        'inputs': {
            'image': {'type': 'base64', 'value': b64},
            'confidence': CONFIDENCE_THRESHOLD,
        },
    }
    req = _ul_req.Request(
        url     = ROBOFLOW_API_URL,
        data    = json.dumps(payload).encode('utf-8'),
        headers = {
            'Content-Type': 'application/json',
            'Accept':       'application/json',
            'User-Agent':   'python-urllib/3',
        },
        method = 'POST',
    )
    with _ul_req.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode('utf-8'))

def _extract_caps(result):
    outputs = result.get('outputs', [])
    if not outputs:
        return []
    preds = outputs[0].get('predictions', {})
    if isinstance(preds, dict):
        preds = preds.get('predictions', [])
    if not preds:
        return []
    return [p for p in preds
            if p.get('class') == TARGET_CLASS
            and p.get('confidence', 0) >= CONFIDENCE_THRESHOLD]

# ── State machine globals ─────────────────────────────────────────────────
nav_state           = 'SCAN'
avoid_start_time    = 0.0
avoid_turn_right    = True
_obstacle_alt_right = True

running        = False
_infer_running = False

_cap_lock = threading.Lock()
_cap_det  = None   # latest cap detection dict, or None

# ── Frame callback ────────────────────────────────────────────────────────
def execute(frame):
    global nav_state, avoid_start_time, avoid_turn_right
    global _obstacle_alt_right

    left_spd  = 0.0
    right_spd = 0.0

    try:
        boundary = detect_yellow_boundary(frame)
        obstacle = detect_obstacle(frame)
        now      = time.time()

        with _cap_lock:
            cap = _cap_det

        # Priority interrupts
        if nav_state not in ('AVOID_YELLOW', 'AVOID_OBSTACLE', 'AT_CAP', 'STOPPED'):
            if boundary['detected']:
                avoid_turn_right = boundary['yellow_left'] >= boundary['yellow_right']
                avoid_start_time = now
                nav_state        = 'AVOID_YELLOW'
            elif obstacle['detected']:
                el = obstacle['edge_left']
                er = obstacle['edge_right']
                if el - er > OBSTACLE_EQUAL_THRESH:
                    avoid_turn_right = True
                elif er - el > OBSTACLE_EQUAL_THRESH:
                    avoid_turn_right = False
                else:
                    avoid_turn_right    = _obstacle_alt_right
                    _obstacle_alt_right = not _obstacle_alt_right
                avoid_start_time = now
                nav_state        = 'AVOID_OBSTACLE'

        if nav_state in ('STOPPED', 'AT_CAP'):
            pass

        elif nav_state in ('AVOID_YELLOW', 'AVOID_OBSTACLE'):
            elapsed = now - avoid_start_time
            if elapsed < AVOID_REVERSE_TIME:
                left_spd  = -REVERSE_SPEED
                right_spd = -REVERSE_SPEED
            elif elapsed < AVOID_REVERSE_TIME + AVOID_TURN_TIME:
                if avoid_turn_right:
                    left_spd  =  TURN_SPEED
                    right_spd = -TURN_SPEED
                else:
                    left_spd  = -TURN_SPEED
                    right_spd =  TURN_SPEED
            else:
                nav_state = 'SCAN'

        elif nav_state == 'SCAN':
            if cap is not None:
                nav_state = 'CENTER_CAP'
            else:
                left_spd  =  SCAN_TURN_SPEED
                right_spd = -SCAN_TURN_SPEED

        elif nav_state == 'CENTER_CAP':
            if cap is None:
                nav_state = 'SCAN'
            else:
                offset = cap['x'] - (CAMERA_WIDTH / 2.0)
                if abs(offset) < CENTER_TOLERANCE:
                    nav_state = 'APPROACH_CAP'
                elif offset > 0:
                    left_spd  =  SCAN_TURN_SPEED
                    right_spd = -SCAN_TURN_SPEED
                else:
                    left_spd  = -SCAN_TURN_SPEED
                    right_spd =  SCAN_TURN_SPEED

        elif nav_state == 'APPROACH_CAP':
            if cap is None:
                nav_state = 'SCAN'
            elif max(cap.get('width', 0), cap.get('height', 0)) >= CAP_CLOSE_SIZE:
                nav_state = 'AT_CAP'
                safe_stop()
                print('\n>>> AT CAP — stopped.')
            else:
                offset = cap['x'] - (CAMERA_WIDTH / 2.0)
                if abs(offset) > CENTER_TOLERANCE * 2:
                    nav_state = 'CENTER_CAP'
                else:
                    correction = (offset / (CAMERA_WIDTH / 2.0)) * APPROACH_SPEED * 0.4
                    left_spd  = APPROACH_SPEED + correction
                    right_spd = APPROACH_SPEED - correction

        set_drive(left_spd, right_spd)

        cap_info = ('x=%.0f w=%.0f' % (cap['x'], cap['width'])) if cap else 'none'
        print('\r%-16s cap=%-16s L=%+.2f R=%+.2f' % (
            nav_state, cap_info, left_spd, right_spd), end='', flush=True)

    except Exception as e:
        safe_stop()
        print('\n[ERROR in execute]', e)

# ── Background threads ────────────────────────────────────────────────────
def _inference_loop():
    global _cap_det
    while _infer_running:
        try:
            frame  = camera.value.copy()
            result = _infer_frame(frame)
            caps   = _extract_caps(result)
            best   = max(caps, key=lambda p: p['confidence']) if caps else None
            with _cap_lock:
                _cap_det = best
            if best:
                print('\n[cap] x=%.0f y=%.0f w=%.0f conf=%.2f' % (
                    best['x'], best['y'], best['width'], best['confidence']))
        except Exception as e:
            print('\n[Inference error]', e)
            with _cap_lock:
                _cap_det = None
        time.sleep(INFERENCE_INTERVAL)

def _nav_loop():
    while running:
        execute(camera.value)
        time.sleep(1 / 30)

# ── Shutdown ──────────────────────────────────────────────────────────────
def _shutdown():
    global running, _infer_running
    print('\nShutting down...')
    running        = False
    _infer_running = False
    safe_stop()

signal.signal(signal.SIGTERM, lambda s, f: (_shutdown(), sys.exit(0)))

# ── Entry point ───────────────────────────────────────────────────────────
if __name__ == '__main__':
    nav_state           = 'SCAN'
    avoid_start_time    = 0.0
    avoid_turn_right    = True
    _obstacle_alt_right = True

    with _cap_lock:
        _cap_det = None

    _infer_running = True
    running        = True

    threading.Thread(target=_inference_loop, daemon=True).start()
    threading.Thread(target=_nav_loop,       daemon=True).start()

    print('Navigation running.  Ctrl+C to stop.')
    print('State: SCAN — rotating to find bottle caps...\n')

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        _shutdown()
