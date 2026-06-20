# Team Workflow — 6 People, 1 Robot

## Division of Labor

| Pair | Task | Needs Robot? |
|------|------|-------------|
| **Yashveer** | Vision: HSV calibration, cap detection | Yes (camera) |
| **Mohammad + Myron** | Control: state machine, PID, recovery | Eventually |
| **Salawu** | Telemetry/logging, config YAML | No |
| **Mohammed A.** | Test scripts, integration tests | Eventually |
| **Joaquin** | Hardware abstraction, servo mappings | Yes (servos) |

## Robot Time Slots (30 min each)

| Time | Who | What |
|------|-----|------|
| H0:00–0:30 | Joaquin | Test chassis servos, arm range, document safe angles |
| H0:30–1:00 | Yashveer | Camera calibration, HSV threshold tuning for real caps |
| H1:00–1:30 | Mohammad | Test perception → control bridge |
| H1:30–2:00 | Joaquin + Yashveer | Integration: arm picks up cap when robot stops |
| H2:00+ | Full team | End-to-end runs, tune, debug |

> **Rule:** When you don't have robot time, code on your laptop using the dev venv.

## Collaboration Rhythm

### Sync Cycle (Every 30 Minutes)

1. **On laptop:** Code your module → `git add .` → `git commit` → `git push`
2. **On Jetson (Operator):** `git pull origin main` → run tests → report results
3. **If test fails:** Operator pastes error → owner fixes on laptop → push again

### Designated Jetson Operator

**Mohammad El Musleh** (Control Lead) is the operator:
- Pulls latest code onto Jetson
- Runs hardware tests
- Reports results to team chat
- Manages robot time slots

## Jupyter Multi-User Rules

- **Only 1 person edits a notebook at a time.** Jupyter has no merge conflicts handling.
- **Use `.py` files for shared code.** Multiple people can edit different `.py` files simultaneously.
- **Operator restarts kernel** between test sessions to clear RAM.
- **Save before every run.** `Ctrl+S` constantly.

## What to Code on Laptop vs. Jetson

| On Laptop | On Jetson |
|-----------|-----------|
| Module logic | Hardware tests |
| Unit tests | Camera calibration |
| Config files | Servo angle tuning |
| State machine code | End-to-end integration |
| Git commits/pushes | `git pull` + run |
