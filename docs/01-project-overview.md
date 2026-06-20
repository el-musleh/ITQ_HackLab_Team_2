# ITQ — Project Overview

## Mission
Build an autonomous robot that navigates a parkour course, avoids obstacles, and collects as many bottle caps as possible — all within 5 minutes.

## Challenge Details

| | |
|---|---|
| **Track** | ITQ — Autonomous Detection and Collection of Bottle Caps with Computer Vision |
| **Prize** | 200€ cash |
| **Time Limit** | 5 minutes per run |
| **Scoring** | Caps collected (primary) + completion time + safety penalty |
| **Win Condition** | Most caps with **zero collisions** |

**Strategy:** Safe and steady beats fast and reckless. Every collision costs you.

## Hardware Platform
[Waveshare JETANK](https://github.com/waveshare/JETANK) — open-source tracked robot with 4-DOF arm on NVIDIA Jetson Nano.

## State Machine (Core Loop)

```
SEARCH ──(sees cap)──> APPROACH ──(close enough)──> COLLECT ──(got it)──> RETURN ──> SEARCH
     ^                                                              |
     └────────────────(lost cap / failure)───────────────────────────┘
```

| State | Action |
|-------|--------|
| **SEARCH** | Drive around looking for caps |
| **APPROACH** | Move toward detected cap using PID |
| **COLLECT** | Stop, position arm, grab cap |
| **RETURN** | Resume path, look for next cap |

## Team Roster

| Name | Role | Module |
|------|------|--------|
| **Yashveer Sookun** | Vision Lead | `perception/` |
| **Salawu Wareeth** | Pipeline / Logging | `utils/telemetry.py` |
| **Mohammed Abubakr Khan** | Integration / QA | `robot_tests/` |
| **Joaquín Morillo Soto** | Hardware / Mechanics | `hardware/` |
| **Mohammad El Musleh** | Control Lead | `control/` + Jetson setup |
| **Myron Sydorov** | Navigation / Recovery | `control/recovery.py` |
