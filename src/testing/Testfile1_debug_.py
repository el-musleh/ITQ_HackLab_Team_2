#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Converted from Testfile1_debug_hardware_params.ipynb
JETANK bottle-cap navigation project with hardware parameters, debugging, camera feed, detection overlays, and map visualization.
"""


# %% [markdown] Cell 1
# # JETANK Bottle Cap Robot — Debug Hardware Version
# 
# This notebook merges the tested claw/arm parameters from `Joaquin-Test2.ipynb` into the autonomous navigation code from `Testfile1.ipynb`.
# 
# Run the cells from top to bottom. Start with camera and claw tests before running the autonomous loop.

# %% Cell 2
# CELL 1 — Imports, debug helpers, and safe hardware initialization

import cv2
import time
import math
import heapq
import traceback
import numpy as np
import ipywidgets as widgets
from IPython.display import display, clear_output

DEBUG = True


def log(step, message):
    """Notebook-friendly debug logger."""
    stamp = time.strftime("%H:%M:%S")
    print("[{}] [{}] {}".format(stamp, step, message))


def run_step(step_name, func, *args, **kwargs):
    """Run one operation with clear success/fail logging."""
    log(step_name, "START")
    try:
        result = func(*args, **kwargs)
        log(step_name, "OK")
        return result
    except Exception as e:
        log(step_name, "FAILED: {}".format(e))
        traceback.print_exc()
        try:
            hard_stop()
        except Exception:
            pass
        return None

try:
    from jetbot import Robot, Camera, bgr8_to_jpeg
    from SCSCtrl import TTLServo
    log("IMPORT", "jetbot, Camera and TTLServo imported")
except Exception as e:
    log("IMPORT", "Hardware import failed: {}".format(e))
    raise

robot = None
camera = None

try:
    robot = Robot()
    log("ROBOT", "Robot initialized")
except Exception as e:
    log("ROBOT", "Robot initialization failed: {}".format(e))
    raise


def hard_stop():
    """Always use this instead of robot.stop() directly."""
    try:
        if robot is not None:
            robot.stop()
        if DEBUG:
            log("MOTION", "Hard stop sent")
    except Exception as e:
        log("MOTION", "Hard stop failed: {}".format(e))

hard_stop()

# %% Cell 3
# CELL 2 — Configuration and tested hardware parameters

# Camera settings. These match the original Testfile1 size and keep processing light.
CAMERA_WIDTH = 320
CAMERA_HEIGHT = 240

# Field dimensions. Measure your real yellow-tape field and tune these two values.
CFG = {
    "field_w_m": 1.60,
    "field_h_m": 1.20,
    "grid_res_m": 0.05,

    # Robot physical safety model. Tune to your JETANK dimensions.
    "robot_width_m": 0.22,
    "robot_length_m": 0.26,
    "front_claw_overhang_m": 0.08,
    "obstacle_margin_m": 0.12,
    "boundary_margin_m": 0.10,
    "emergency_stop_distance_m": 0.23,

    # Motion parameters. Conservative values for first real-hardware tests.
    "speed_forward": 0.22,
    "speed_slow": 0.15,
    "speed_turn": 0.14,
    "max_drive_step_s": 0.12,

    # Detection thresholds. Tune with the debug detection cell.
    "min_cap_area": 80,
    "max_cap_area": 2500,
    "min_sphere_area": 600,
    "min_obstacle_area": 900,
    "min_box_area": 700,

    # HSV ranges are starting points only. Use the HSV debug output to tune them on the real field.
    "HSV": {
        "yellow": ((18, 80, 80), (40, 255, 255)),
        "blue": ((90, 70, 40), (130, 255, 255)),
        "green": ((40, 50, 40), (85, 255, 255)),
        "grey": ((0, 0, 45), (180, 60, 180)),
        "cap_red_1": ((0, 70, 50), (10, 255, 255)),
        "cap_red_2": ((170, 70, 50), (180, 255, 255)),
        "cap_white": ((0, 0, 150), (180, 55, 255)),
        "sphere_orange": ((5, 80, 80), (22, 255, 255)),
        "sphere_purple": ((125, 40, 40), (165, 255, 255)),
    }
}

# Tested claw/arm parameters from Joaquin-Test2.ipynb
CLAW_SERVO_ID = 4
CLAW_OPEN_ANGLE = -10
CLAW_CLOSED_ANGLE = -75

ARM_HOME_X = 130
ARM_HOME_Y = 20

ARM_DOWN_X = 150
ARM_DOWN_Y = -138

ARM_UP_X = 120
ARM_UP_Y = 45

DROP_X = 130
DROP_Y = 20

# Starting pose: fixed corner. Tune theta depending on which direction the robot faces at start.
robot_pose = {
    "x": CFG["boundary_margin_m"] + 0.08,
    "y": CFG["boundary_margin_m"] + 0.08,
    "theta": 0.0
}

# Image-field calibration corners, ordered: top-left, top-right, bottom-right, bottom-left.
# These are placeholders. Replace with measured pixel corners from the live feed.
IMAGE_FIELD_CORNERS = np.float32([
    [25, 25],
    [295, 25],
    [295, 215],
    [25, 215]
])
WORLD_FIELD_CORNERS = np.float32([
    [0.0, 0.0],
    [CFG["field_w_m"], 0.0],
    [CFG["field_w_m"], CFG["field_h_m"]],
    [0.0, CFG["field_h_m"]]
])

H_img_to_world = cv2.getPerspectiveTransform(IMAGE_FIELD_CORNERS, WORLD_FIELD_CORNERS)
H_world_to_img = cv2.getPerspectiveTransform(WORLD_FIELD_CORNERS, IMAGE_FIELD_CORNERS)

log("CONFIG", "Loaded CFG and tested claw parameters")
log("CLAW PARAMS", "servo={}, open={}, closed={}, home=({},{}), down=({},{}), up=({},{})".format(
    CLAW_SERVO_ID, CLAW_OPEN_ANGLE, CLAW_CLOSED_ANGLE,
    ARM_HOME_X, ARM_HOME_Y, ARM_DOWN_X, ARM_DOWN_Y, ARM_UP_X, ARM_UP_Y
))

# %% Cell 4
# CELL 3 — Start camera and show real-time feed

camera_widget = widgets.Image(format="jpeg", width=640, height=480)
detection_widget = widgets.Image(format="jpeg", width=640, height=480)
map_widget = widgets.Image(format="jpeg", width=480, height=360)
status_box = widgets.Output()

display(widgets.HTML("<b>Raw camera feed</b>"))
display(camera_widget)
display(widgets.HTML("<b>Detection/debug feed</b>"))
display(detection_widget)
display(widgets.HTML("<b>Discovered map</b>"))
display(map_widget)
display(status_box)


def start_camera():
    global camera
    try:
        if camera is None:
            camera = Camera.instance(width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
        time.sleep(1.0)
        frame = camera.value
        if frame is None:
            raise RuntimeError("Camera started but returned None frame")
        camera_widget.value = bgr8_to_jpeg(frame)
        log("CAMERA", "Started and first frame received: {}".format(frame.shape))
        return True
    except Exception as e:
        log("CAMERA", "Start failed: {}".format(e))
        traceback.print_exc()
        return False


def update_raw_camera_feed(seconds=10, fps=8):
    """Run this cell to visually confirm the camera works in real time."""
    if camera is None:
        log("CAMERA", "Camera is not started. Run start_camera() first.")
        return False
    delay = 1.0 / max(fps, 1)
    end_t = time.time() + seconds
    frames = 0
    while time.time() < end_t:
        frame = camera.value
        if frame is None:
            log("CAMERA", "No frame received")
            continue
        camera_widget.value = bgr8_to_jpeg(frame)
        frames += 1
        time.sleep(delay)
    log("CAMERA", "Live feed finished, frames shown: {}".format(frames))
    return True

# Run once to start the camera.
start_camera()

# %% Cell 5
# CELL 4 — Utility functions and calibration helpers

def require_frame(step="FRAME"):
    if camera is None:
        raise RuntimeError("Camera is not started")
    frame = camera.value
    if frame is None:
        raise RuntimeError("Camera returned None")
    return frame


def hsv_mask(frame, lower, upper):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)
    return mask


def clean_mask(mask, k=5):
    kernel = np.ones((k, k), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def contour_center(cnt):
    M = cv2.moments(cnt)
    if M["m00"] == 0:
        return None
    return int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])


def image_to_world(px, py):
    p = np.array([[[px, py]]], dtype=np.float32)
    out = cv2.perspectiveTransform(p, H_img_to_world)[0][0]
    return float(out[0]), float(out[1])


def world_to_image(x, y):
    p = np.array([[[x, y]]], dtype=np.float32)
    out = cv2.perspectiveTransform(p, H_world_to_img)[0][0]
    return int(out[0]), int(out[1])


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def refresh_homography():
    global H_img_to_world, H_world_to_img
    H_img_to_world = cv2.getPerspectiveTransform(IMAGE_FIELD_CORNERS, WORLD_FIELD_CORNERS)
    H_world_to_img = cv2.getPerspectiveTransform(WORLD_FIELD_CORNERS, IMAGE_FIELD_CORNERS)
    log("CALIBRATION", "Homography refreshed")


def show_calibration_overlay():
    frame = require_frame("CALIBRATION")
    out = frame.copy()
    pts = IMAGE_FIELD_CORNERS.astype(np.int32).reshape((-1, 1, 2))
    cv2.polylines(out, [pts], True, (0, 255, 255), 2)
    for i, p in enumerate(IMAGE_FIELD_CORNERS.astype(int)):
        cv2.circle(out, tuple(p), 5, (0, 0, 255), -1)
        cv2.putText(out, str(i), tuple(p + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
    detection_widget.value = bgr8_to_jpeg(out)
    log("CALIBRATION", "Yellow field corner overlay shown. If wrong, edit IMAGE_FIELD_CORNERS in Cell 2.")

show_calibration_overlay()

# %% Cell 6
# CELL 5 — Object detection with rectangles, names, and debug counts

def detect_colored_objects(frame, hsv_names, min_area=80, max_area=999999):
    detections = []
    for name in hsv_names:
        if name not in CFG["HSV"]:
            log("DETECTION", "Missing HSV range: {}".format(name))
            continue
        lower, upper = CFG["HSV"][name]
        mask = clean_mask(hsv_mask(frame, lower, upper))
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in cnts:
            area = cv2.contourArea(cnt)
            if area < min_area or area > max_area:
                continue
            center = contour_center(cnt)
            if center is None:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            perimeter = cv2.arcLength(cnt, True)
            circularity = 0
            if perimeter > 0:
                circularity = 4 * math.pi * area / (perimeter * perimeter)
            wx, wy = image_to_world(center[0], center[1])
            detections.append({
                "type": name,
                "kind": name,
                "center_px": center,
                "bbox": (x, y, w, h),
                "area": area,
                "circularity": circularity,
                "world": (wx, wy),
                "contour": cnt
            })
    return detections


def detect_boundary(frame):
    mask = clean_mask(hsv_mask(frame, *CFG["HSV"]["yellow"]))
    edges = cv2.Canny(mask, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=35, minLineLength=40, maxLineGap=15)
    return mask, lines


def detect_obstacles(frame):
    blue = detect_colored_objects(frame, ["blue"], CFG["min_obstacle_area"])
    green = detect_colored_objects(frame, ["green"], CFG["min_obstacle_area"])
    for o in blue:
        o["kind"] = "obstacle_blue"
    for o in green:
        o["kind"] = "obstacle_green"
    return blue + green


def detect_grey_box(frame):
    boxes = detect_colored_objects(frame, ["grey"], CFG["min_box_area"])
    for b in boxes:
        b["kind"] = "drop_box"
    if not boxes:
        return None
    return max(boxes, key=lambda x: x["area"])


def looks_like_sphere(det):
    return det["circularity"] > 0.72 and det["area"] >= CFG["min_sphere_area"]


def detect_spheres(frame):
    spheres = detect_colored_objects(frame, ["sphere_orange", "sphere_purple"], CFG["min_sphere_area"])
    for s in spheres:
        s["kind"] = "sphere_ignore"
    return spheres


def detect_bottle_caps(frame):
    raw_caps = detect_colored_objects(frame, ["cap_red_1", "cap_red_2", "cap_white"], CFG["min_cap_area"], CFG["max_cap_area"])
    caps = []
    for c in raw_caps:
        if looks_like_sphere(c):
            continue
        x, y, w, h = c["bbox"]
        aspect = w / max(h, 1)
        if 0.45 <= aspect <= 2.2:
            c["kind"] = "bottle_cap"
            caps.append(c)
    return caps


def run_detection_once(verbose=True):
    frame = require_frame("DETECTION")
    obstacles = detect_obstacles(frame)
    grey_box = detect_grey_box(frame)
    spheres = detect_spheres(frame)
    caps = detect_bottle_caps(frame)
    grid = build_local_map(obstacles)
    show_debug(frame, obstacles, caps, spheres, grey_box, grid=grid)
    if verbose:
        names = []
        names += [o["kind"] for o in obstacles]
        names += ["drop_box"] if grey_box is not None else []
        names += ["bottle_cap"] * len(caps)
        names += ["sphere_ignore"] * len(spheres)
        if names:
            log("DETECTION", "Objects detected: {}".format(", ".join(names)))
        else:
            log("DETECTION", "No object detected")
        log("DETECTION", "caps={}, spheres={}, obstacles={}, grey_box={}".format(len(caps), len(spheres), len(obstacles), grey_box is not None))
    return obstacles, caps, spheres, grey_box, grid

# %% Cell 7
# CELL 6 — Mapping with inflated forbidden zones and live map display

def make_empty_grid():
    gw = int(CFG["field_w_m"] / CFG["grid_res_m"])
    gh = int(CFG["field_h_m"] / CFG["grid_res_m"])
    return np.zeros((gh, gw), dtype=np.uint8)


def world_to_grid(x, y):
    gx = int(x / CFG["grid_res_m"])
    gy = int(y / CFG["grid_res_m"])
    return gx, gy


def grid_to_world(gx, gy):
    return ((gx + 0.5) * CFG["grid_res_m"], (gy + 0.5) * CFG["grid_res_m"])


def mark_circle(grid, center, radius_m, value=1):
    cx, cy = world_to_grid(center[0], center[1])
    r = int(radius_m / CFG["grid_res_m"])
    h, w = grid.shape
    for yy in range(max(0, cy-r), min(h, cy+r+1)):
        for xx in range(max(0, cx-r), min(w, cx+r+1)):
            wx, wy = grid_to_world(xx, yy)
            if distance((wx, wy), center) <= radius_m:
                grid[yy, xx] = value


def build_local_map(obstacles):
    grid = make_empty_grid()
    body_radius = max(CFG["robot_width_m"] / 2, CFG["robot_length_m"] / 2 + CFG["front_claw_overhang_m"])
    margin_cells = int(CFG["boundary_margin_m"] / CFG["grid_res_m"])
    if margin_cells > 0:
        grid[:margin_cells, :] = 1
        grid[-margin_cells:, :] = 1
        grid[:, :margin_cells] = 1
        grid[:, -margin_cells:] = 1
    inflated_radius = body_radius + CFG["obstacle_margin_m"]
    for obs in obstacles:
        mark_circle(grid, obs["world"], inflated_radius, 1)
    return grid


def draw_grid_map(grid, path=None, caps=None, grey_box=None, obstacles=None):
    # 0 free = dark, 1 forbidden = bright
    img = np.zeros((grid.shape[0], grid.shape[1], 3), dtype=np.uint8)
    img[grid == 0] = (30, 30, 30)
    img[grid == 1] = (220, 220, 220)

    def mark_world_point(world, color, radius=2):
        gx, gy = world_to_grid(*world)
        if 0 <= gx < grid.shape[1] and 0 <= gy < grid.shape[0]:
            cv2.circle(img, (gx, gy), radius, color, -1)

    if obstacles:
        for o in obstacles:
            mark_world_point(o["world"], (255, 0, 0), 2)
    if caps:
        for c in caps:
            mark_world_point(c["world"], (0, 0, 255), 2)
    if grey_box is not None:
        mark_world_point(grey_box["world"], (160, 160, 160), 3)
    mark_world_point((robot_pose["x"], robot_pose["y"]), (0, 255, 255), 3)
    if path:
        pts = [world_to_grid(x, y) for x, y in path]
        for i in range(len(pts)-1):
            cv2.line(img, pts[i], pts[i+1], (255, 255, 255), 1)
    img = cv2.resize(img, (480, 360), interpolation=cv2.INTER_NEAREST)
    return img


def show_map(grid, path=None, caps=None, grey_box=None, obstacles=None):
    img = draw_grid_map(grid, path=path, caps=caps, grey_box=grey_box, obstacles=obstacles)
    map_widget.value = bgr8_to_jpeg(img)
    forbidden = int(np.sum(grid == 1))
    free = int(np.sum(grid == 0))
    log("MAP", "Updated map: free_cells={}, forbidden_cells={}".format(free, forbidden))

# %% Cell 8
# CELL 7 — A* path planning with debug output

def astar(grid, start_w, goal_w):
    start = world_to_grid(*start_w)
    goal = world_to_grid(*goal_w)
    h, w = grid.shape

    def valid(node):
        x, y = node
        return 0 <= x < w and 0 <= y < h and grid[y, x] == 0

    if not valid(start):
        log("PATH", "Start cell blocked/outside: {}".format(start))
        return None
    if not valid(goal):
        log("PATH", "Goal cell blocked/outside: {}".format(goal))
        return None

    def heuristic(a, b):
        return math.hypot(a[0]-b[0], a[1]-b[1])

    neighbors = [(1,0), (-1,0), (0,1), (0,-1), (1,1), (1,-1), (-1,1), (-1,-1)]
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g = {start: 0}
    visited = 0

    while open_set:
        _, current = heapq.heappop(open_set)
        visited += 1
        if current == goal:
            path = []
            while current in came_from:
                path.append(grid_to_world(*current))
                current = came_from[current]
            path.append(grid_to_world(*start))
            path.reverse()
            log("PATH", "Path found: points={}, visited={}".format(len(path), visited))
            return path
        for dx, dy in neighbors:
            nxt = (current[0] + dx, current[1] + dy)
            if not valid(nxt):
                continue
            step_cost = math.hypot(dx, dy)
            tentative = g[current] + step_cost
            if nxt not in g or tentative < g[nxt]:
                came_from[nxt] = current
                g[nxt] = tentative
                f = tentative + heuristic(nxt, goal)
                heapq.heappush(open_set, (f, nxt))
    log("PATH", "No path found, visited={}".format(visited))
    return None


def simplify_path(path, step=3):
    if not path:
        return None
    simple = path[::step]
    if simple[-1] != path[-1]:
        simple.append(path[-1])
    log("PATH", "Simplified path: {} -> {} points".format(len(path), len(simple)))
    return simple

# %% Cell 9
# CELL 8 — Motion control and emergency safety with step-by-step logs

def move_forward(speed=None, duration=0.15):
    spd = speed or CFG["speed_forward"]
    log("MOTION", "Forward speed={}, duration={}".format(spd, duration))
    robot.forward(spd)
    time.sleep(duration)
    hard_stop()


def move_backward(speed=None, duration=0.20):
    spd = speed or CFG["speed_slow"]
    log("MOTION", "Backward speed={}, duration={}".format(spd, duration))
    robot.backward(spd)
    time.sleep(duration)
    hard_stop()


def turn_left(speed=None, duration=0.12):
    spd = speed or CFG["speed_turn"]
    log("MOTION", "Left speed={}, duration={}".format(spd, duration))
    robot.left(spd)
    time.sleep(duration)
    hard_stop()


def turn_right(speed=None, duration=0.12):
    spd = speed or CFG["speed_turn"]
    log("MOTION", "Right speed={}, duration={}".format(spd, duration))
    robot.right(spd)
    time.sleep(duration)
    hard_stop()


def rotate_towards(target):
    global robot_pose
    dx = target[0] - robot_pose["x"]
    dy = target[1] - robot_pose["y"]
    desired = math.atan2(dy, dx)
    error = desired - robot_pose["theta"]
    while error > math.pi:
        error -= 2 * math.pi
    while error < -math.pi:
        error += 2 * math.pi
    if abs(error) < 0.18:
        return True
    if error > 0:
        turn_left(duration=0.08)
        robot_pose["theta"] += 0.12
    else:
        turn_right(duration=0.08)
        robot_pose["theta"] -= 0.12
    log("POSE", "theta={:.2f}, turn_error={:.2f}".format(robot_pose["theta"], error))
    return False


def update_pose_dead_reckoning_forward(duration, speed):
    global robot_pose
    meters_per_second_at_1_speed = 0.45  # tune experimentally
    d = meters_per_second_at_1_speed * speed * duration
    robot_pose["x"] += d * math.cos(robot_pose["theta"])
    robot_pose["y"] += d * math.sin(robot_pose["theta"])
    log("POSE", "x={:.2f}, y={:.2f}, theta={:.2f}".format(robot_pose["x"], robot_pose["y"], robot_pose["theta"]))


def emergency_check(frame, obstacles):
    x = robot_pose["x"]
    y = robot_pose["y"]
    if x < CFG["boundary_margin_m"] or y < CFG["boundary_margin_m"]:
        log("SAFETY", "Robot too close to low boundary")
        return False
    if x > CFG["field_w_m"] - CFG["boundary_margin_m"]:
        log("SAFETY", "Robot too close to right boundary")
        return False
    if y > CFG["field_h_m"] - CFG["boundary_margin_m"]:
        log("SAFETY", "Robot too close to upper boundary")
        return False
    for obs in obstacles:
        d = distance((x, y), obs["world"])
        if d < CFG["emergency_stop_distance_m"]:
            log("SAFETY", "Obstacle too close: {}, d={:.2f}m".format(obs["kind"], d))
            return False
    return True


def safe_step_forward(frame, obstacles, speed=None):
    if not emergency_check(frame, obstacles):
        hard_stop()
        move_backward(duration=0.25)
        return False
    duration = CFG["max_drive_step_s"]
    spd = speed or CFG["speed_forward"]
    robot.forward(spd)
    time.sleep(duration)
    hard_stop()
    update_pose_dead_reckoning_forward(duration, spd)
    return True


def follow_path(path, max_steps_per_target=80):
    if path is None or len(path) == 0:
        log("PATH", "follow_path received empty path")
        return False
    for idx, target in enumerate(path):
        log("PATH", "Following waypoint {}/{}: {:.2f},{:.2f}".format(idx+1, len(path), target[0], target[1]))
        for step in range(max_steps_per_target):
            frame = require_frame("FOLLOW_PATH")
            obstacles = detect_obstacles(frame)
            if not emergency_check(frame, obstacles):
                hard_stop()
                move_backward(duration=0.25)
                return False
            if distance((robot_pose["x"], robot_pose["y"]), target) < 0.08:
                log("PATH", "Waypoint reached")
                break
            aligned = rotate_towards(target)
            if aligned:
                ok = safe_step_forward(frame, obstacles, CFG["speed_slow"])
                if not ok:
                    return False
        else:
            log("PATH", "Waypoint timeout")
            return False
    hard_stop()
    log("PATH", "Path completed")
    return True

# %% Cell 10
# CELL 9 — Claw control using tested Joaquin-Test2 hardware parameters

def servo_delay(seconds=0.25):
    time.sleep(seconds)


def safe_servo_angle(servo_id, angle, speed=1, acc=150, label="servo"):
    log("CLAW", "{} -> servo {}, angle {}".format(label, servo_id, angle))
    TTLServo.servoAngleCtrl(servo_id, angle, speed, acc)
    servo_delay()


def safe_xy(x, y, duration=0.8, label="arm"):
    log("CLAW", "{} -> x={}, y={}, duration={}".format(label, x, y, duration))
    TTLServo.xyInputSmooth(x, y, duration)
    time.sleep(max(duration, 0.8))


def claw_open():
    safe_servo_angle(CLAW_SERVO_ID, CLAW_OPEN_ANGLE, 1, 150, "open claw")


def claw_close():
    safe_servo_angle(CLAW_SERVO_ID, CLAW_CLOSED_ANGLE, 1, 150, "close claw")


def arm_home():
    safe_xy(ARM_HOME_X, ARM_HOME_Y, 0.8, "arm home")


def arm_lower_for_pickup():
    safe_xy(ARM_DOWN_X, ARM_DOWN_Y, 0.8, "arm down to cap")


def arm_lift():
    safe_xy(ARM_UP_X, ARM_UP_Y, 0.8, "arm up/lift")


def arm_drop_position():
    safe_xy(DROP_X, DROP_Y, 0.8, "arm drop position")


def grab_cap():
    log("PICKUP", "Starting tested pickup sequence")
    arm_home()
    time.sleep(1)
    claw_open()
    time.sleep(0.5)
    arm_lower_for_pickup()
    time.sleep(1)
    claw_close()
    time.sleep(1)
    arm_home()
    log("PICKUP", "Pickup sequence complete")


def drop_cap():
    log("DROP", "Starting tested drop sequence")
    arm_home()
    time.sleep(1)
    arm_drop_position()
    time.sleep(1)
    claw_open()
    time.sleep(0.5)
    arm_home()
    log("DROP", "Drop sequence complete")


def test_claw_once():
    """Safe standalone claw test before driving the robot."""
    try:
        hard_stop()
        arm_home()
        claw_open()
        claw_close()
        claw_open()
        arm_lift()
        arm_home()
        log("CLAW TEST", "Complete")
        return True
    except Exception as e:
        log("CLAW TEST", "Failed: {}".format(e))
        traceback.print_exc()
        hard_stop()
        return False

# Uncomment only when the claw area is clear.
# test_claw_once()

# %% Cell 11
# CELL 10 — Debug visualization: camera overlay + map overlay

def draw_label_box(out, det, label, color):
    x, y, w, h = det["bbox"]
    cv2.rectangle(out, (x, y), (x+w, y+h), color, 2)
    text = "{} A{} C{:.2f}".format(label, int(det.get("area", 0)), det.get("circularity", 0))
    cv2.putText(out, text, (x, max(15, y-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1)


def draw_detections(frame, obstacles, caps, spheres, grey_box, path=None):
    out = frame.copy()
    pts = IMAGE_FIELD_CORNERS.astype(np.int32).reshape((-1, 1, 2))
    cv2.polylines(out, [pts], True, (0, 255, 255), 2)

    for obs in obstacles:
        color = (255, 0, 0) if "blue" in obs["kind"] else (0, 255, 0)
        draw_label_box(out, obs, obs["kind"], color)

    for cap in caps:
        draw_label_box(out, cap, "BOTTLE CAP", (0, 0, 255))

    for sph in spheres:
        draw_label_box(out, sph, "IGNORE SPHERE", (255, 0, 255))

    if grey_box is not None:
        draw_label_box(out, grey_box, "DROP BOX", (160, 160, 160))

    if path:
        pts = [world_to_image(x, y) for x, y in path]
        for i in range(len(pts)-1):
            cv2.line(out, pts[i], pts[i+1], (255, 255, 255), 2)

    rx, ry = world_to_image(robot_pose["x"], robot_pose["y"])
    cv2.circle(out, (rx, ry), 6, (0, 255, 255), -1)
    cv2.putText(out, "ROBOT", (rx+5, ry), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    return out


def show_debug(frame, obstacles, caps, spheres, grey_box, path=None, grid=None):
    vis = draw_detections(frame, obstacles, caps, spheres, grey_box, path)
    detection_widget.value = bgr8_to_jpeg(vis)
    if grid is not None:
        show_map(grid, path=path, caps=caps, grey_box=grey_box, obstacles=obstacles)


def live_detection_debug(seconds=20, fps=5):
    """Live detection view: rectangles + object names + changing map."""
    if camera is None:
        log("LIVE DEBUG", "Camera is not started")
        return False
    delay = 1.0 / max(fps, 1)
    end_t = time.time() + seconds
    frames = 0
    while time.time() < end_t:
        try:
            frame = require_frame("LIVE DEBUG")
            obstacles = detect_obstacles(frame)
            grey_box = detect_grey_box(frame)
            spheres = detect_spheres(frame)
            caps = detect_bottle_caps(frame)
            grid = build_local_map(obstacles)
            show_debug(frame, obstacles, caps, spheres, grey_box, grid=grid)
            with status_box:
                clear_output(wait=True)
                print("Detected: caps={}, spheres={}, obstacles={}, grey_box={}".format(len(caps), len(spheres), len(obstacles), grey_box is not None))
                if len(caps) == 0 and len(spheres) == 0 and len(obstacles) == 0 and grey_box is None:
                    print("No object detected")
            frames += 1
            time.sleep(delay)
        except Exception as e:
            log("LIVE DEBUG", "Frame failed: {}".format(e))
            traceback.print_exc()
            hard_stop()
            return False
    log("LIVE DEBUG", "Finished, frames processed={}".format(frames))
    return True

# Uncomment to test detection live before driving.
# live_detection_debug(seconds=30, fps=5)

# %% Cell 12
# CELL 11 — Approach and verification

def choose_nearest_safe_cap(caps, grid):
    safe_caps = []
    for cap in caps:
        gx, gy = world_to_grid(*cap["world"])
        h, w = grid.shape
        if 0 <= gx < w and 0 <= gy < h and grid[gy, gx] == 0:
            d = distance((robot_pose["x"], robot_pose["y"]), cap["world"])
            safe_caps.append((d, cap))
        else:
            log("TARGET", "Cap rejected: blocked/outside grid at {}".format((gx, gy)))
    if not safe_caps:
        log("TARGET", "No safe cap found")
        return None
    safe_caps.sort(key=lambda x: x[0])
    log("TARGET", "Nearest safe cap distance={:.2f}m".format(safe_caps[0][0]))
    return safe_caps[0][1]


def verify_cap_not_sphere(frame, target_world):
    caps = detect_bottle_caps(frame)
    spheres = detect_spheres(frame)
    for s in spheres:
        if distance(s["world"], target_world) < 0.12:
            log("VERIFY", "Target rejected: sphere near target")
            return False
    for c in caps:
        if distance(c["world"], target_world) < 0.12:
            log("VERIFY", "Target verified as bottle cap")
            return True
    log("VERIFY", "Target not visible anymore")
    return False


def approach_object_slowly(target_world):
    for step in range(30):
        frame = require_frame("APPROACH")
        obstacles = detect_obstacles(frame)
        if not emergency_check(frame, obstacles):
            hard_stop()
            move_backward(duration=0.25)
            return False
        d = distance((robot_pose["x"], robot_pose["y"]), target_world)
        log("APPROACH", "step={}, distance={:.2f}m".format(step+1, d))
        if d < 0.12:
            hard_stop()
            log("APPROACH", "Object reached")
            return True
        rotate_towards(target_world)
        ok = safe_step_forward(frame, obstacles, CFG["speed_slow"])
        if not ok:
            return False
    log("APPROACH", "Timeout before reaching object")
    return False

# %% Cell 13
# CELL 12 — Main autonomous loop with detailed failure points

def autonomous_loop(max_cycles=10):
    log("AUTO", "Starting autonomous loop")
    hard_stop()
    run_step("AUTO INIT ARM HOME", arm_home)
    run_step("AUTO INIT CLAW OPEN", claw_open)

    for cycle in range(max_cycles):
        log("AUTO", "===== Cycle {}/{} =====".format(cycle + 1, max_cycles))
        try:
            frame = require_frame("AUTO FRAME")
            boundary_mask, boundary_lines = detect_boundary(frame)
            obstacles = detect_obstacles(frame)
            grey_box = detect_grey_box(frame)
            spheres = detect_spheres(frame)
            caps = detect_bottle_caps(frame)
            grid = build_local_map(obstacles)
            show_debug(frame, obstacles, caps, spheres, grey_box, grid=grid)
            log("AUTO DETECTION", "caps={}, spheres={}, obstacles={}, grey_box={}, boundary_lines={}".format(
                len(caps), len(spheres), len(obstacles), grey_box is not None, 0 if boundary_lines is None else len(boundary_lines)
            ))

            if grey_box is None:
                log("AUTO FAIL", "Grey drop box not detected. Stopping for safety and scanning again.")
                hard_stop()
                time.sleep(1)
                continue

            if len(caps) == 0:
                log("AUTO DONE", "No bottle caps detected. Task complete or cap not visible.")
                hard_stop()
                break

            target_cap = choose_nearest_safe_cap(caps, grid)
            if target_cap is None:
                log("AUTO FAIL", "No safe reachable cap. Replanning after scan.")
                hard_stop()
                time.sleep(1)
                continue

            cap_pos = target_cap["world"]
            drop_pos = grey_box["world"]
            log("AUTO TARGET", "cap_world=({:.2f},{:.2f}), drop_world=({:.2f},{:.2f})".format(cap_pos[0], cap_pos[1], drop_pos[0], drop_pos[1]))

            path_to_cap = simplify_path(astar(grid, (robot_pose["x"], robot_pose["y"]), cap_pos))
            show_debug(frame, obstacles, caps, spheres, grey_box, path_to_cap, grid=grid)
            if path_to_cap is None:
                log("AUTO FAIL", "No safe path to cap")
                hard_stop()
                time.sleep(1)
                continue

            ok = follow_path(path_to_cap)
            if not ok:
                log("AUTO FAIL", "Navigation to cap failed")
                hard_stop()
                continue

            frame = require_frame("VERIFY CAP")
            if not verify_cap_not_sphere(frame, cap_pos):
                log("AUTO FAIL", "Target uncertain or sphere-like. Not picking up.")
                hard_stop()
                move_backward(duration=0.25)
                continue

            ok = approach_object_slowly(cap_pos)
            if not ok:
                log("AUTO FAIL", "Could not safely approach cap")
                hard_stop()
                continue

            run_step("PICKUP", grab_cap)

            frame = require_frame("AFTER PICKUP")
            obstacles = detect_obstacles(frame)
            grey_box = detect_grey_box(frame)
            if grey_box is None:
                log("AUTO FAIL", "Lost grey box after pickup. Holding cap and stopping.")
                hard_stop()
                continue

            grid = build_local_map(obstacles)
            drop_pos = grey_box["world"]
            path_to_box = simplify_path(astar(grid, (robot_pose["x"], robot_pose["y"]), drop_pos))
            show_debug(frame, obstacles, [], [], grey_box, path_to_box, grid=grid)
            if path_to_box is None:
                log("AUTO FAIL", "No safe path to grey box. Holding object and stopping.")
                hard_stop()
                continue

            ok = follow_path(path_to_box)
            if not ok:
                log("AUTO FAIL", "Navigation to drop box failed")
                hard_stop()
                continue

            run_step("DROP", drop_cap)
            move_backward(duration=0.25)
            arm_home()
            log("AUTO", "Cycle completed successfully")

        except KeyboardInterrupt:
            log("AUTO", "Interrupted by user")
            hard_stop()
            break
        except Exception as e:
            log("AUTO ERROR", "Cycle crashed: {}".format(e))
            traceback.print_exc()
            hard_stop()
            time.sleep(1)

    hard_stop()
    log("AUTO", "Autonomous loop finished")

# Safety: do not auto-run. Run manually only after camera, detection, claw, and map are checked.
# autonomous_loop(max_cycles=20)

# %% Cell 14
# CELL 13 — Recommended step-by-step hardware test sequence

# 1) Camera test
# update_raw_camera_feed(seconds=10, fps=8)

# 2) Calibration overlay test
# show_calibration_overlay()

# 3) Live object detection + map test
# live_detection_debug(seconds=30, fps=5)

# 4) Claw-only test
# test_claw_once()

# 5) One detection snapshot with printed object names
# run_detection_once(verbose=True)

# 6) Autonomous loop only after all above tests are safe
# autonomous_loop(max_cycles=20)

log("TEST SEQUENCE", "Uncomment one test at a time. Do not run autonomous_loop before testing camera, detection, map, and claw.")

# %% Cell 15
# CELL 14 — Emergency stop / cleanup

hard_stop()
try:
    if camera is not None:
        camera.stop()
        log("CLEANUP", "Camera stopped")
except Exception as e:
    log("CLEANUP", "Camera stop failed: {}".format(e))
