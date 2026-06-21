# Robot State Machine

This document describes the high-level control flow used by the ITQ Bottle Cap Collector.

## Overview

The robot runs a single `StateMachine` class (`control/state_machine.py`) driven by a `tick()` loop. The state machine is shared between the real robot (`main.py`) and the PyBullet simulation (`simulation/demo_pickup_deposit_safe.py`).

The seven main states are:

1. `IDLE` — initialize sensors and report errors.
2. `WANDERING` — scan the arena for balls, boundaries, and obstacles.
3. `CHECK_FOR_BALL` — decide if a ball is available to collect.
4. `COLLECT_BALL` — approach, pick up, carry to basket, and deposit.
5. `BALLS_LEFT` — consult the world map and pick the next known ball.
6. `BLIND_SPOT` — explore candidate viewpoints to find hidden balls.
7. `END` — return to the starting corner and stop.

A dedicated `RECOVERY` state handles transient failures.

## State Diagram

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> WANDERING : ready
    WANDERING --> CHECK_FOR_BALL : sweep complete
    CHECK_FOR_BALL --> COLLECT_BALL : ball in view
    CHECK_FOR_BALL --> BALLS_LEFT : no ball in view
    COLLECT_BALL --> CHECK_FOR_BALL : success
    COLLECT_BALL --> RECOVERY : failure
    RECOVERY --> COLLECT_BALL : retry
    RECOVERY --> BALLS_LEFT : retries exhausted
    BALLS_LEFT --> COLLECT_BALL : known balls remain
    BALLS_LEFT --> BLIND_SPOT : no known balls
    BLIND_SPOT --> CHECK_FOR_BALL : viewpoint reached
    BLIND_SPOT --> END : no blind spots
    END --> [*] : at start corner
```

## State Details

### IDLE
- Initialize the camera and arm.
- Retry each failing component up to 3 times.
- If initialization still fails, print a fatal error and stop.

### WANDERING
- Sweep the camera from -90° to +90°.
- If no ball is found, rotate 180° and sweep again to cover 360°.
- Register every ball detected into the `WorldMap`.
- Calibrate the basket detector when the basket is first reliably seen.

### CHECK_FOR_BALL
- If a ball is currently visible, start collecting it.
- Otherwise, check the world map for known balls.
- If no known balls remain, explore blind spots.
- If all blind spots are visited, end the mission.

### COLLECT_BALL
Internal sub-states:

1. `APPROACH` — track the ball with PID and drive forward until close enough.
2. `PICKUP` — open claw, lower arm, close claw, lift to carry pose.
3. `GOTO_BASKET` — rotate/search for the basket and approach it.
4. `DEPOSIT` — open claw to drop the ball, then return arm to home.

On failure, the state transitions to `RECOVERY`.

### BALLS_LEFT
- Select the nearest known ball from the world map.
- Return to `CHECK_FOR_BALL` with that ball as the target.
- If no reachable balls remain, go to `BLIND_SPOT`.

### BLIND_SPOT
- Navigate to the nearest unvisited candidate cell in the arena.
- Perform a camera sweep at the viewpoint to look for hidden balls.
- If all candidate viewpoints are visited, go to `END`.

### RECOVERY
- Stop, reverse, and turn to escape from the failure condition.
- Return to the originating state to retry.
- After 3 retries, mark the current ball as unreachable and try the next ball.

### END
- Navigate back to the starting corner.
- Stop all motors.

## Safety Override

A yellow boundary always has priority:

- If a yellow border is detected, the robot immediately stops forward motion and reverses/turns away.
- If an obstacle is detected, the robot turns away.
- Balls are not obstacles; the robot may drive over them.
- A ball estimated to be outside the yellow boundary is ignored.

## Tuning Parameters

Default timeout values are in `control/state_machine.py`:

| State | Timeout |
|---|---|
| IDLE | 5 s per attempt |
| WANDERING | 30 s |
| CHECK_FOR_BALL | 2 s |
| COLLECT_BALL | 60 s |
| BALLS_LEFT | 2 s |
| BLIND_SPOT | 30 s |
| END | 30 s |
| RECOVERY | 3 s |

Motor speeds and PID gains come from `config.yaml`.

## Running the State Machine

### Simulation
```bash
python simulation/demo_pickup_deposit_safe.py
```

### Real Robot
```bash
python main.py
```

## Files

- `control/state_machine.py` — state machine implementation
- `control/world_map.py` — ball registry and blind-spot grid
- `control/odometry.py` — simple dead-reckoning pose estimator (real robot)
- `main.py` — real robot entry point
- `simulation/demo_pickup_deposit_safe.py` — simulation entry point
