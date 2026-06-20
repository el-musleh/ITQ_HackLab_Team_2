#!/usr/bin/env python3
"""
navigation.py -- Autonomous bottle-cap detection and approach.
JETANK AI Kit . Jetson Nano

States: SCAN -> CENTER_CAP -> APPROACH_CAP -> AT_CAP

Run:   python3 navigation.py
Stop:  Ctrl+C
"""

import cv2
import base64
import json
import signal
import sys
import threading
import time
from urllib import request as _ul_req

from jetbot import Camera, Robot

try:
    from SCSCtrl import TTLServo
    _servo_available = True
except Exception:
    _servo_available = False
    print('TTLServo not available -- camera tilt skipped.')

# -- Configuration ---------------------------------------------------------
CAMERA_WIDTH     = 300
CAMERA_HEIGHT    = 300
CAMERA_TILT_DOWN = 22

MAX_SPEED        = 0.25
SCAN_TURN_SPEED  = 0.12   # rotation speed while scanning
APPROACH_SPEED   = 0.18   # forward speed while approaching
CENTER_TOLERANCE = 30     # px offset from frame centre to consider "centred"
CAP_BOTTOM_FRAC  = 0.80   # cap centre y / frame height to trigger grab (0=top, 1=bottom)

ROBOFLOW_API_KEY     = "Ub1KVwtGHHdLLKRzoxdG"
ROBOFLOW_API_URL     = "https://serverless.roboflow.com/kais-workspace-stbmo/workflows/detect-count-and-visualize-3"
CONFIDENCE_THRESHOLD = 0.50   # lowered from 0.80 -- easier to detect
TARGET_CLASS         = "bottle cap"
INFERENCE_INTERVAL   = 0.20   # seconds between API calls

# -- Hardware init ---------------------------------------------------------
if _servo_available:
    try:
        TTLServo.servoAngleCtrl(1, 0, 1, 100)
        time.sleep(0.15)
        TTLServo.servoAngleCtrl(5, CAMERA_TILT_DOWN, 1, 100)
        time.sleep(0.50)
        print('Camera tilted down %d deg.' % CAMERA_TILT_DOWN)
    except Exception as e:
        print('Servo error:', e)

camera = Camera.instance(width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
robot  = Robot()
robot.stop()
print('Camera + Robot ready.')

# -- Motor helpers ---------------------------------------------------------
def safe_stop():
    try:
        robot.left_motor.value  = 0.0
        robot.right_motor.value = 0.0
    except Exception:
        pass

def set_drive(left, right):
    try:
        robot.left_motor.value  = max(-MAX_SPEED, min(MAX_SPEED, left))
        robot.right_motor.value = max(-MAX_SPEED, min(MAX_SPEED, right))
    except Exception:
        pass

# -- Arm / claw ------------------------------------------------------------
CLAW_SERVO_ID = 4
CLAW_OPEN     = -10
CLAW_CLOSED   = -75
ARM_HOME_X    = 130
ARM_HOME_Y    = 20
ARM_DOWN_X    = 150
ARM_DOWN_Y    = -138
ARM_UP_X      = 120
ARM_UP_Y      = 45

def _pick_cap():
    if not _servo_available:
        print('[ARM] servo not available -- skipping pick.')
        return
    try:
        print('\nARM: home...')
        TTLServo.xyInputSmooth(ARM_HOME_X, ARM_HOME_Y, 0.5);      time.sleep(2.0)
        print('ARM: open claw...')
        TTLServo.servoAngleCtrl(CLAW_SERVO_ID, CLAW_OPEN, 1, 150); time.sleep(1.0)
        print('ARM: lower to cap...')
        TTLServo.xyInputSmooth(ARM_DOWN_X, ARM_DOWN_Y, 0.5);       time.sleep(2.0)
        print('ARM: grab...')
        TTLServo.servoAngleCtrl(CLAW_SERVO_ID, CLAW_CLOSED, 1, 150); time.sleep(2.0)
        print('ARM: lift...')
        TTLServo.xyInputSmooth(ARM_UP_X, ARM_UP_Y, 0.8);           time.sleep(2.0)
        print('ARM: home with cap.')
        TTLServo.xyInputSmooth(ARM_HOME_X, ARM_HOME_Y, 0.8);       time.sleep(2.0)
        print('Cap picked. Resuming scan...')
    except Exception as e:
        print('[ARM ERROR]', e)

# -- Roboflow inference ----------------------------------------------------
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

# -- State -----------------------------------------------------------------
nav_state      = 'SCAN'
running        = False
_infer_running = False
_cap_lock      = threading.Lock()
_cap_det       = None

# Lock-on: once we pick a cap to chase we ignore all others
_locked_x      = None   # x-coord of the cap we committed to
_lock_lost     = 0      # consecutive inference cycles without the locked cap
LOCK_TOLERANCE = 80     # px -- how far the locked cap can drift before re-id
LOCK_MAX_LOST  = 2      # inference cycles before releasing lock and re-scanning

# -- Frame loop ------------------------------------------------------------
def execute():
    global nav_state, _cap_det, _locked_x, _lock_lost

    with _cap_lock:
        cap = _cap_det

    left_spd  = 0.0
    right_spd = 0.0

    try:
        if nav_state == 'AT_CAP':
            # Pick the cap, release lock, then scan for the next one
            safe_stop()
            _pick_cap()
            _locked_x  = None
            _lock_lost = 0
            with _cap_lock:
                _cap_det = None
            nav_state = 'SCAN'

        elif nav_state == 'SCAN':
            if cap is not None:
                nav_state = 'APPROACH_CAP'   # go immediately, skip stationary centering
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
                    # cap right of centre -> turn right
                    left_spd  = -SCAN_TURN_SPEED
                    right_spd =  SCAN_TURN_SPEED
                else:
                    # cap left of centre -> turn left
                    left_spd  =  SCAN_TURN_SPEED
                    right_spd = -SCAN_TURN_SPEED

        elif nav_state == 'APPROACH_CAP':
            if cap is None:
                nav_state = 'SCAN'
            elif cap.get('y', 0) >= CAMERA_HEIGHT * CAP_BOTTOM_FRAC:
                nav_state = 'AT_CAP'
                safe_stop()
                print('\n>>> AT CAP -- cap at bottom of frame, stopping to grab.')
            else:
                offset = cap['x'] - (CAMERA_WIDTH / 2.0)
                if abs(offset) > CENTER_TOLERANCE * 2:
                    nav_state = 'CENTER_CAP'
                else:
                    correction = (offset / (CAMERA_WIDTH / 2.0)) * APPROACH_SPEED * 0.4
                    left_spd  = -(APPROACH_SPEED + correction)
                    right_spd = -(APPROACH_SPEED - correction)

        set_drive(left_spd, right_spd)

        cap_info = ('x=%.0f y=%.0f w=%.0f' % (cap['x'], cap['y'], cap['width'])) if cap else 'none'
        print('\r%-14s cap=%-14s L=%+.2f R=%+.2f' % (
            nav_state, cap_info, left_spd, right_spd), end='', flush=True)

    except Exception as e:
        safe_stop()
        print('\n[ERROR]', e)

# -- Background threads ----------------------------------------------------
def _inference_loop():
    global _cap_det, _locked_x, _lock_lost
    while _infer_running:
        t0 = time.time()
        try:
            frame  = camera.value.copy()
            result = _infer_frame(frame)
            caps   = _extract_caps(result)

            if _locked_x is None:
                # No lock yet -- pick the closest cap (largest bbox)
                best = max(caps, key=lambda p: max(p.get('width', 0), p.get('height', 0))) if caps else None
                if best:
                    _locked_x  = best['x']
                    _lock_lost = 0
                    print('\n[LOCK] new cap at x=%.0f y=%.0f conf=%.2f' % (
                        best['x'], best['y'], best['confidence']))
            else:
                # Locked -- only accept detections near the locked x position
                near = [c for c in caps if abs(c['x'] - _locked_x) < LOCK_TOLERANCE]
                if near:
                    best = min(near, key=lambda c: abs(c['x'] - _locked_x))
                    _locked_x  = best['x']
                    _lock_lost = 0
                else:
                    _lock_lost += 1
                    if _lock_lost >= LOCK_MAX_LOST:
                        print('\n[LOCK] lost cap -- releasing lock, back to SCAN')
                        _locked_x  = None
                        _lock_lost = 0
                        best = None
                    else:
                        best = _cap_det  # hold last known position briefly

            with _cap_lock:
                _cap_det = best

        except Exception as e:
            print('\n[Inference error]', e)
            with _cap_lock:
                _cap_det = None

        # Sleep only the time remaining in the interval (API call already ate some of it)
        elapsed = time.time() - t0
        gap = INFERENCE_INTERVAL - elapsed
        if gap > 0:
            time.sleep(gap)

def _nav_loop():
    while running:
        execute()
        time.sleep(1 / 30)

# -- Shutdown --------------------------------------------------------------
def _shutdown():
    global running, _infer_running
    print('\nShutting down...')
    running        = False
    _infer_running = False
    safe_stop()

signal.signal(signal.SIGTERM, lambda s, f: (_shutdown(), sys.exit(0)))

# -- Entry point -----------------------------------------------------------
if __name__ == '__main__':
    import sys as _sys

    if '--test' in _sys.argv:
        # One-shot inference: print full raw API response and exit.
        print('TEST MODE -- grabbing one frame and calling Roboflow...')
        time.sleep(1.0)   # let camera warm up
        frame = camera.value.copy()
        try:
            result = _infer_frame(frame)
            import json as _json
            print('=== RAW RESPONSE ===')
            print(_json.dumps(result, indent=2))
            caps = _extract_caps(result)
            print('=== CAPS FOUND (conf >= %.2f) ===' % CONFIDENCE_THRESHOLD)
            for c in caps:
                print('  x=%.0f y=%.0f w=%.0f h=%.0f conf=%.2f' % (
                    c['x'], c['y'], c['width'], c['height'], c['confidence']))
            if not caps:
                print('  (none)')
        except Exception as e:
            print('FAILED:', e)
        safe_stop()
        _sys.exit(0)

    nav_state = 'SCAN'
    with _cap_lock:
        _cap_det = None

    _infer_running = True
    running        = True

    threading.Thread(target=_inference_loop, daemon=True).start()
    threading.Thread(target=_nav_loop,       daemon=True).start()

    print('Running. Ctrl+C to stop.')
    print('SCAN -- rotating to find bottle caps...\n')

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        _shutdown()
