#!/usr/bin/env python3
"""
JETANK bottle-cap parkour run.

Goal:
  * Wander the yellow-bounded square for up to 5 minutes.
  * Avoid the GREEN box and BLUE box (obstacles).
  * Never drive over the YELLOW boundary lines.
  * Avoid driving into the GRAY/CLEAR deposit bin in the middle
    (we only approach it on purpose, to drop caps).
  * Detect bottle caps with the Roboflow model and pick them up.
  * Carry each cap to the deposit bin and drop it in.

Obstacle / boundary / bin detection is done here with the `ColorDetector`
class (HSV color masks) so the robot has something concrete to avoid.
Cap detection is delegated to the Roboflow workflow you already have.

Send this whole file to the robot and run:  python3 jetank_caps_run.py

Tune the HSV ranges (CONFIG) under your actual lighting before the run —
that is the single most important thing for reliable avoidance.
"""

import time
import random
import base64

import cv2
import numpy as np
from urllib import request, error

# ----- robot hardware -------------------------------------------------------
# JetBot driving base
from jetbot import Robot, Camera

# JETANK arm/claw (Waveshare SCS servos). Wrapped so the script still runs
# (vision + driving) on a machine without the servo bus attached.
try:
    from SCSCtrl import TTLServo
    HAS_ARM = True
except Exception as _e:          # noqa: BLE001
    print("WARN: SCSCtrl not available, arm disabled:", _e)
    HAS_ARM = False


# ===========================================================================
# CONFIG
# ===========================================================================
class CONFIG:
    # --- timing ---
    RUN_SECONDS = 5 * 60          # hard stop at 5 minutes
    LOOP_DELAY = 0.05             # seconds between control loops

    # --- camera frame size (jetbot Camera default is 224 unless changed) ---
    FRAME_W = 300
    FRAME_H = 300

    # --- driving speeds (0..1) ---
    SPEED_FWD = 0.16
    SPEED_TURN = 0.18
    SPEED_APPROACH = 0.12         # slow creep when lining up on a cap/bin

    # --- avoidance tuning ---
    # An obstacle/boundary mask covering more than this fraction of the
    # bottom band of the frame == "too close, turn away".
    OBSTACLE_AREA_STOP = 0.045
    BOTTOM_BAND = 0.45            # use lower 45% of frame for proximity
    CENTER_BAND = (0.33, 0.66)    # x-fraction defining "ahead of me"

    # --- cap handling ---
    CAP_PICK_AREA = 0.02          # bbox area-fraction at which cap is grabbable
    CAP_CENTER_TOL = 0.12         # how centered (x) before we drive straight in
    CAP_CONF = 0.40               # min Roboflow confidence

    # --- deposit bin ---
    BIN_DROP_AREA = 0.18          # bin mask area-fraction == close enough to drop

    # --- Roboflow ---
    API_KEY = "Ub1KVwtGHHdLLKRzoxdG"
    API_URL = ("https://serverless.roboflow.com/kais-workspace-stbmo/"
               "workflows/detect-count-and-visualize-3")
    ROBOFLOW_EVERY = 4           # only call the API every Nth loop (latency)

    # --- HSV color ranges  [H 0-179, S 0-255, V 0-255] ---
    # GREEN obstacle box
    GREEN = [(35, 70, 40), (85, 255, 255)]
    # BLUE obstacle box
    BLUE = [(95, 80, 40), (130, 255, 255)]
    # YELLOW boundary line
    YELLOW = [(20, 80, 80), (34, 255, 255)]
    # GRAY / clear deposit bin (low saturation, mid value). Clear plastic is
    # hard to color-key — tune this hard, or tape a colored marker on the bin
    # and key on that instead.
    GRAY = [(0, 0, 70), (179, 50, 200)]


# ===========================================================================
# COLOR DETECTOR  -- obstacles, boundary, deposit bin
# ===========================================================================
class ColorDetector:
    """Detects colored regions (obstacles / boundary / bin) in a BGR frame.

    For each color it reports:
      area  : fraction of the proximity band covered by that color (0..1)
      side  : 'left' | 'center' | 'right' | None  -- where the blob sits
    """

    def __init__(self, cfg=CONFIG):
        self.cfg = cfg

    @staticmethod
    def _mask(hsv, rng):
        lo, hi = np.array(rng[0]), np.array(rng[1])
        m = cv2.inRange(hsv, lo, hi)
        m = cv2.erode(m, None, iterations=1)
        m = cv2.dilate(m, None, iterations=2)
        return m

    def _band_metrics(self, mask):
        """area-fraction + horizontal side, using the lower part of frame."""
        h, w = mask.shape
        y0 = int(h * (1 - self.cfg.BOTTOM_BAND))
        band = mask[y0:, :]
        area = float(cv2.countNonZero(band)) / band.size

        side = None
        if area > 0:
            cols = band.sum(axis=0)
            cx = float(np.argmax(np.convolve(cols, np.ones(15), "same")))
            fx = cx / w
            lo, hi = self.cfg.CENTER_BAND
            side = "left" if fx < lo else "right" if fx > hi else "center"
        return area, side

    def detect(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        out = {}
        for name, rng in (("green", self.cfg.GREEN),
                          ("blue", self.cfg.BLUE),
                          ("yellow", self.cfg.YELLOW),
                          ("gray", self.cfg.GRAY)):
            area, side = self._band_metrics(self._mask(hsv, rng))
            out[name] = {"area": area, "side": side}
        return out

    # -- high level helpers --------------------------------------------------
    def blocking(self, det, ignore_gray=False):
        """True if something we must avoid is close & ahead.

        Returns (is_blocked, suggested_turn) where turn is 'left'/'right'.
        """
        hazards = ["green", "blue", "yellow"]
        if not ignore_gray:
            hazards.append("gray")

        worst_side = None
        blocked = False
        for h in hazards:
            d = det[h]
            if d["area"] >= self.cfg.OBSTACLE_AREA_STOP:
                blocked = True
                if d["side"] in ("center", "left", "right"):
                    worst_side = d["side"]
        if not blocked:
            return False, None
        # turn away from the blob; if it's dead center pick a random side
        if worst_side == "left":
            return True, "right"
        if worst_side == "right":
            return True, "left"
        return True, random.choice(["left", "right"])


# ===========================================================================
# CAP DETECTOR  -- Roboflow workflow (model already trained)
# ===========================================================================
class CapDetector:
    """Calls the Roboflow serverless workflow to find bottle caps."""

    def __init__(self, cfg=CONFIG):
        self.cfg = cfg

    def detect(self, frame):
        """Return list of {x,y,w,h,conf} in pixels, or [] on failure.

        x,y are bbox CENTER in pixels (Roboflow convention).
        """
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            return []
        b64 = base64.b64encode(buf).decode("ascii")

        payload = {
            "api_key": self.cfg.API_KEY,
            "inputs": {"image": {"type": "base64", "value": b64}},
        }
        body = bytes(__import__("json").dumps(payload), "utf-8")
        req = request.Request(
            self.cfg.API_URL, data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=4) as resp:
                data = __import__("json").loads(resp.read().decode("utf-8"))
        except (error.URLError, error.HTTPError, ValueError) as e:
            print("roboflow error:", e)
            return []

        return self._parse(data)

    def _parse(self, data):
        """Dig predictions out of the workflow response (shape varies)."""
        preds = self._find_predictions(data)
        caps = []
        for p in preds:
            try:
                conf = float(p.get("confidence", 1.0))
                if conf < self.cfg.CAP_CONF:
                    continue
                caps.append({
                    "x": float(p["x"]), "y": float(p["y"]),
                    "w": float(p["width"]), "h": float(p["height"]),
                    "conf": conf,
                })
            except (KeyError, TypeError, ValueError):
                continue
        return caps

    def _find_predictions(self, obj):
        """Recursively locate the first list of prediction dicts."""
        if isinstance(obj, dict):
            if "predictions" in obj and isinstance(obj["predictions"], list):
                return obj["predictions"]
            for v in obj.values():
                r = self._find_predictions(v)
                if r:
                    return r
        elif isinstance(obj, list):
            if obj and isinstance(obj[0], dict) and "x" in obj[0]:
                return obj
            for v in obj:
                r = self._find_predictions(v)
                if r:
                    return r
        return []


# ===========================================================================
# ARM / CLAW  -- pick up and drop  (JETANK SCS servos)
# ===========================================================================
# Servo map on Waveshare JETANK:
#   ID 1 -> arm base pan      ID 2 -> shoulder
#   ID 3 -> elbow/extend      ID 4 -> camera/wrist tilt
#   ID 5 -> gripper (claw)    (smaller angle = more closed)
# These angles are STARTING POINTS. Replace this whole block with the
# pick/drop routine from your Joaquin-Test2_camera_claw_combined notebook
# if you already tuned it — the interface the run loop needs is just
# arm_grab() and arm_release().
class Arm:
    GRIP_OPEN = 60
    GRIP_CLOSE = -25
    REST = [(2, -30), (3, 60), (4, 0)]      # arm tucked / camera forward
    DOWN = [(2, 40), (3, -10), (4, -20)]    # reach down to floor cap
    LIFT = [(2, -20), (3, 40), (4, 10)]     # raised, holding cap

    def __init__(self):
        if HAS_ARM:
            self._set(5, self.GRIP_OPEN)
            self._pose(self.REST)

    def _set(self, sid, angle, speed=150):
        if HAS_ARM:
            TTLServo.servoAngleCtrl(sid, angle, 1, speed)
            time.sleep(0.25)

    def _pose(self, pose):
        for sid, ang in pose:
            self._set(sid, ang)

    def grab(self):
        """Lower, close claw, lift. Call when a cap is right in front."""
        print("ARM: grab")
        self._set(5, self.GRIP_OPEN)
        self._pose(self.DOWN)
        self._set(5, self.GRIP_CLOSE)        # close on the cap
        self._pose(self.LIFT)

    def release(self):
        """Open claw over the bin, return to rest."""
        print("ARM: release")
        self._set(5, self.GRIP_OPEN)
        self._pose(self.REST)
        self._set(5, self.GRIP_OPEN)


# ===========================================================================
# MAIN CONTROLLER  -- state machine
# ===========================================================================
class Mission:
    SEARCH, APPROACH, PICK, DELIVER, DROP = range(5)

    def __init__(self):
        self.cfg = CONFIG
        self.robot = Robot()
        self.camera = Camera.instance(width=self.cfg.FRAME_W,
                                      height=self.cfg.FRAME_H)
        self.eye = ColorDetector()
        self.caps = CapDetector()
        self.arm = Arm()
        self.state = self.SEARCH
        self.caps_collected = 0
        self._rf_tick = 0
        self._target = None       # current cap bbox

    # -- low level driving ---------------------------------------------------
    def stop(self):
        self.robot.stop()

    def forward(self, s=None):
        self.robot.forward(s or self.cfg.SPEED_FWD)

    def turn(self, side, s=None):
        s = s or self.cfg.SPEED_TURN
        if side == "left":
            self.robot.left(s)
        else:
            self.robot.right(s)

    # -- perception throttled cap call --------------------------------------
    def _maybe_caps(self, frame):
        self._rf_tick += 1
        if self._rf_tick % self.cfg.ROBOFLOW_EVERY != 0:
            return None              # None == "didn't look this loop"
        return self.caps.detect(frame)

    def _biggest_cap(self, caps):
        return max(caps, key=lambda c: c["w"] * c["h"]) if caps else None

    # -- states --------------------------------------------------------------
    def do_search(self, frame, det):
        blocked, turn_to = self.eye.blocking(det)   # avoid bin too while searching
        if blocked:
            self.stop()
            self.turn(turn_to)
            return
        caps = self._maybe_caps(frame)
        if caps:
            self._target = self._biggest_cap(caps)
            self.state = self.APPROACH
            return
        # random wander: mostly forward, occasional turn
        if random.random() < 0.15:
            self.turn(random.choice(["left", "right"]))
        else:
            self.forward()

    def do_approach(self, frame, det):
        # never plow through an obstacle/line even while chasing a cap
        blocked, turn_to = self.eye.blocking(det, ignore_gray=True)
        if blocked:
            self.stop(); self.turn(turn_to)
            self._target = None
            self.state = self.SEARCH
            return

        caps = self._maybe_caps(frame)
        if caps is not None:
            self._target = self._biggest_cap(caps)
        if not self._target:
            self.state = self.SEARCH
            return

        c = self._target
        fx = c["x"] / self.cfg.FRAME_W
        area = (c["w"] * c["h"]) / (self.cfg.FRAME_W * self.cfg.FRAME_H)

        if area >= self.cfg.CAP_PICK_AREA and abs(fx - 0.5) < self.cfg.CAP_CENTER_TOL:
            self.stop()
            self.state = self.PICK
            return
        # steer toward cap
        if fx < 0.5 - self.cfg.CAP_CENTER_TOL:
            self.turn("left", self.cfg.SPEED_APPROACH)
        elif fx > 0.5 + self.cfg.CAP_CENTER_TOL:
            self.turn("right", self.cfg.SPEED_APPROACH)
        else:
            self.forward(self.cfg.SPEED_APPROACH)

    def do_pick(self, frame, det):
        self.stop()
        self.arm.grab()
        self.caps_collected += 1
        print("caps collected:", self.caps_collected)
        self._target = None
        self.state = self.DELIVER

    def do_deliver(self, frame, det):
        # drive toward the gray bin; avoid green/blue/yellow on the way
        blocked, turn_to = self.eye.blocking(det, ignore_gray=True)
        if blocked:
            self.stop(); self.turn(turn_to)
            return
        bin_d = det["gray"]
        if bin_d["area"] >= self.cfg.BIN_DROP_AREA:
            self.stop()
            self.state = self.DROP
            return
        if bin_d["side"] == "left":
            self.turn("left", self.cfg.SPEED_APPROACH)
        elif bin_d["side"] == "right":
            self.turn("right", self.cfg.SPEED_APPROACH)
        elif bin_d["side"] == "center":
            self.forward(self.cfg.SPEED_APPROACH)
        else:
            # can't see bin -> sweep to find it
            self.turn("right")

    def do_drop(self, frame, det):
        self.stop()
        self.arm.release()
        self.state = self.SEARCH

    # -- main loop -----------------------------------------------------------
    def run(self):
        handlers = {
            self.SEARCH: self.do_search,
            self.APPROACH: self.do_approach,
            self.PICK: self.do_pick,
            self.DELIVER: self.do_deliver,
            self.DROP: self.do_drop,
        }
        names = {v: k for k, v in
                 zip(["SEARCH", "APPROACH", "PICK", "DELIVER", "DROP"],
                     handlers.keys())}
        t_end = time.time() + self.cfg.RUN_SECONDS
        last_state = None
        try:
            while time.time() < t_end:
                frame = self.camera.value
                if frame is None:
                    time.sleep(self.cfg.LOOP_DELAY)
                    continue
                det = self.eye.detect(frame)
                if self.state != last_state:
                    print("STATE ->", names[self.state])
                    last_state = self.state
                handlers[self.state](frame, det)
                time.sleep(self.cfg.LOOP_DELAY)
        except KeyboardInterrupt:
            print("interrupted")
        finally:
            self.stop()
            print("DONE. caps collected:", self.caps_collected)


if __name__ == "__main__":
    Mission().run()