# CLAUDE.md

## Project: Bottle Cap Collector Simulation

We are building a simulation for the robotics challenge:

**Track:** Autonomous Detection and Collection of Bottle Caps with Computer Vision

The original robot is a Waveshare JETANK AI Kit, but we no longer have access to the physical robot. Therefore, this project should simulate the full challenge and provide two controller versions:

1. **Classical Robotics Controller**
2. **Self-Learning Reinforcement Learning Agent**

The goal is to create an impressive simulation that demonstrates autonomous navigation, cap detection, obstacle avoidance, cap collection, and delivery to a basket.

---

## Challenge Specifications

### Arena

* Competition area: **175 cm × 180 cm**
* Boundary: yellow tape
* Surface: flat indoor floor
* Time limit: **5 minutes per run**

Use meters internally:

* Arena width: `1.75 m`
* Arena height: `1.80 m`
* Time limit: `300 seconds`

---

## Robot Platform

Simulate the Waveshare JETANK AI Kit.

### Robot Dimensions

* Body width including tracks: `0.19 m`
* Body length: `0.17 m`
* Body height: `0.25 m`
* Tracked differential drive
* Camera only
* No ultrasonic/LiDAR/encoders

### Camera

* CSI IMX219
* Field of view: `160 degrees`
* Operational resolution: `320 × 240`
* Use simulated vision cone in 2D
* Detection should depend on whether objects are inside the camera FOV

### Robotic Arm

Simplified arm simulation is acceptable.

* DOF: 4
* Maximum forward reach: `0.18 m`
* Maximum vertical reach: `0.16 m`
* Gripper opening: `0.055 m`
* Payload: `0.05 kg`
* Bottle cap is collectible if it is within front reach distance

---

## Objects

### Bottle Caps

* Quantity: random between `15` and `25`
* Default: `22`
* Diameter: random between `0.03 m` and `0.04 m`
* Colors:

  * blue
  * red
  * silver

Each cap should have:

```python
{
    "id": int,
    "x": float,
    "y": float,
    "color": str,
    "collected": bool,
    "delivered": bool
}
```

### Obstacles

There are two static crates near the gray basket.

Obstacle 1:

* Width: `0.20 m`
* Length: `0.30 m`
* Height: `0.25 m`

Obstacle 2:

* Width: `0.30 m`
* Length: `0.40 m`
* Height: `0.30 m`

Use rectangular 2D obstacles with collision detection.

### Basket

* Gray collection basket
* Fixed position
* Caps must be delivered here
* Obstacles should be placed on two sides of the basket

---

## Required Simulation Versions

## Version 1: Classical Robotics Controller

Implement a baseline controller using:

* color/vision-based cap detection
* finite state machine
* nearest-cap selection
* A* or grid-based path planning
* obstacle avoidance
* basket return behavior

Suggested FSM states:

```text
SEARCH_CAP
MOVE_TO_CAP
ALIGN_TO_CAP
PICK_CAP
MOVE_TO_BASKET
DROP_CAP
RECOVER_FROM_OBSTACLE
FINISHED
```

The classical controller should be predictable and should work without training.

---

## Version 2: Reinforcement Learning Agent

Implement a self-learning agent using:

* Gymnasium custom environment
* Stable-Baselines3 PPO
* repeated training episodes
* reward-based learning

The RL agent should learn to:

* collect caps
* avoid obstacles
* return caps to basket
* maximize score within the time limit

Observation space can start simple:

```text
robot_x
robot_y
robot_theta
nearest_visible_cap_dx
nearest_visible_cap_dy
basket_dx
basket_dy
front_obstacle_distance
has_cap
time_remaining
```

Action space:

```text
0 = move_forward
1 = move_backward
2 = turn_left
3 = turn_right
4 = pick
5 = drop
```

Reward example:

```text
+10  pick up cap
+25  deliver cap to basket
-10  collision
-1   invalid pick/drop
-0.01 per step
+5   moving closer to target
```

---

## Project Structure

Create this structure:

```text
bottle-cap-sim/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── src/
│   ├── main.py
│   ├── config.py
│   ├── geometry.py
│   ├── arena.py
│   ├── robot.py
│   ├── objects.py
│   ├── scoring.py
│   ├── render.py
│   ├── controllers/
│   │   ├── classical_controller.py
│   │   ├── path_planner.py
│   │   └── fsm.py
│   ├── rl/
│   │   ├── cap_collection_env.py
│   │   ├── train.py
│   │   ├── evaluate.py
│   │   └── rewards.py
│   └── experiments/
│       ├── compare_controllers.py
│       └── plot_results.py
├── models/
├── logs/
└── assets/
```

---

## Implementation Requirements

Use Python.

Recommended libraries:

```text
mujoco
gymnasium
stable-baselines3
numpy
matplotlib
opencv-python
scipy
```

### Library Purpose

- mujoco → physics simulation and digital twin environment
- gymnasium → RL environment interface
- stable-baselines3 → PPO training and evaluation
- numpy → math and state representation
- matplotlib → training curves and performance comparison
- opencv-python → simulated vision pipeline and cap detection
- scipy → geometry, transforms, and utility functions

### Simulation Philosophy

This project should be implemented as a robotics simulation, not as a game.

Use MuJoCo as the primary simulation environment.

The simulator should model:

- JETANK tracked robot
- camera field of view (160°)
- bottle caps
- obstacles
- collection basket
- collision physics
- robot arm pickup zone

The simulation should support both:

1. Classical robotics controller
2. Reinforcement learning controller

The same MuJoCo environment must be used for both controllers to ensure fair comparison.

### RL Framework

Use:

```python
MuJoCo Environment
        ↓
Gymnasium Wrapper
        ↓
Stable-Baselines3 PPO
        ↓
Trained Agent
```

---

## Important Design Decisions

Use 2D simulation first.

Do not start with complicated 3D physics. The first working version should be simple, fast, and visually clear.

The project should show:

1. Arena with yellow boundary
2. Robot with camera FOV cone
3. Bottle caps in blue/red/silver
4. Two obstacles
5. Gray basket
6. Timer
7. Current score
8. Number of collected/delivered caps
9. Collision counter

---

## Scoring

Use this scoring model:

```text
score = delivered_caps * 100
      + picked_caps * 20
      - collisions * 50
      - time_penalty
```

Also track:

```text
caps_delivered
caps_collected
collisions
time_elapsed
completion_status
distance_traveled
```

---

## Final Demo Goals

The final demo should show a comparison:

```text
Classical Controller:
- Caps delivered
- Collisions
- Time used
- Final score

RL Agent:
- Caps delivered
- Collisions
- Time used
- Final score
```

Create a plot showing RL training progress:

```text
episode number → total reward
```

Create another comparison plot:

```text
controller → average score
```

---

## Commands We Want

The project should support these commands:

```bash
python -m src.main --controller classical
python -m src.rl.train
python -m src.rl.evaluate
python -m src.experiments.compare_controllers
```

---

## README Requirements

The README should explain:

1. Challenge background
2. Why simulation was chosen
3. Arena and robot specifications
4. Classical controller approach
5. Reinforcement learning approach
6. How to run the simulation
7. Results comparison
8. Future work: real robot transfer

---

## Coding Style

Write clean, modular Python code.

Use:

* type hints
* dataclasses where useful
* clear comments
* small functions
* no unnecessary complexity

Do not hardcode everything inside one file.

