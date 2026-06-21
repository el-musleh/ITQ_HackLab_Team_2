# State Machine Testing - Quick Start Guide

**Quick reference for running and writing tests**

---

## Run Existing Tests

### Unit Tests (15 tests available)

```bash
# Run all unit tests
./venv/bin/python -m pytest tests/test_state_machine.py -v

# Run specific test class
./venv/bin/python -m pytest tests/test_state_machine.py::TestStateInitialization -v

# Run single test
./venv/bin/python -m pytest tests/test_state_machine.py::TestStateInitialization::test_init_default_config -v
```

### Simulation Test (1 scenario available)

```bash
# Run happy path scenario
./venv/bin/python src/simulation/tests/test_scenario_happy_path.py

# Save output to file
./venv/bin/python src/simulation/tests/test_scenario_happy_path.py 2>&1 | tee test_output.log
```

---

## Write New Tests

### Unit Test Template

```python
# Add to tests/test_state_machine.py

def test_my_new_test(self):
    """Test description."""
    # Create state machine with mocks
    sm, mocks = create_test_state_machine()
    
    # Set up test conditions
    sm.state = WANDERING
    mocks['ball_detector'].set_test_balls([
        simulate_ball_detection('silver', 160, 120, 50, 500)
    ])
    
    # Run state machine
    run_n_ticks(sm, 10)
    
    # Assert expected behavior
    assert sm.state == CHECK_FOR_BALL
```

### Simulation Test Template

```python
# Create new file: simulation/tests/test_scenario_NAME.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.simulation.sim_core import SimulationCore
from src.simulation import create_sim_hardware
from src.control.state_machine import StateMachine
# ... other imports

def main():
    # Initialize simulation
    sim = SimulationCore(gui=True, real_time=True)
    sim.initialize()
    
    # Load robot and spawn balls
    robot_id = sim.load_robot(start_pos=[0, 0, 0.15])
    sim.spawn_balls(num_balls=5)
    
    # Create state machine
    # ... (see test_scenario_happy_path.py for full example)
    
    # Run state machine loop
    while tick_count < max_ticks:
        running = state_machine.tick()
        for _ in range(12):
            sim.step()
        if not running:
            break
    
    # Verify results
    if state_machine.balls_collected >= 3:
        return 0  # Success
    else:
        return 1  # Failure

if __name__ == '__main__':
    sys.exit(main())
```

---

## Mock Object Usage

### Set Test Conditions

```python
from tests.test_utils import create_test_state_machine, simulate_ball_detection

# Create state machine
sm, mocks = create_test_state_machine()

# Simulate ball detection
ball = simulate_ball_detection('silver', cx=160, cy=120, distance=50, area=500)
mocks['ball_detector'].set_test_balls([ball])

# Simulate basket detection
basket = {'detected': True, 'center_x': 160, 'distance_px': 100}
mocks['basket_detector'].set_test_basket(basket)

# Simulate boundary detection
mocks['obstacle_detector'].set_test_boundary(True)

# Add ball to world map
mocks['world_map'].register_ball(0.5, 0.5, source='test')

# Set robot pose
mocks['pose'][0] = 0.3  # x
mocks['pose'][1] = 0.2  # y
mocks['pose'][2] = 0.0  # yaw
```

### Check Results

```python
# Check state
assert sm.state == COLLECT_BALL

# Check motor values
left, right = mocks['chassis'].get_motor_values()
assert left > 0 and right > 0  # Moving forward

# Check arm pose
pose = mocks['arm'].get_current_pose()
assert pose == [0, -35, -55, -25]  # Pickup pose

# Check gripper state
assert mocks['arm'].gripper_state == 'closed'

# Check camera pan
assert mocks['camera'].get_pan() == 0  # Centered

# Check world map
assert mocks['world_map'].has_known_balls() == True
```

---

## Test Utilities

### Run Until State

```python
from tests.test_utils import run_until_state

# Run until WANDERING state reached
success = run_until_state(sm, WANDERING, max_ticks=200)
assert success, f"Failed to reach WANDERING, stuck in {sm.state}"
```

### Run N Ticks

```python
from tests.test_utils import run_n_ticks

# Run for 10 ticks
still_running = run_n_ticks(sm, 10)
assert still_running  # State machine still active
```

### Assert Transition

```python
from tests.test_utils import assert_state_transition

# Verify transition from IDLE to WANDERING
success = assert_state_transition(sm, IDLE, WANDERING, max_ticks=100)
assert success
```

### Wait for Condition

```python
from tests.test_utils import wait_for_condition

# Wait for motors to stop
success = wait_for_condition(
    lambda: mocks['chassis'].stopped == True,
    timeout=5.0
)
assert success
```

---

## Common Test Patterns

### Test State Transition

```python
def test_state_transition(self):
    sm, mocks = create_test_state_machine()
    
    # Start in state A
    sm.state = STATE_A
    sm.state_start_time = time.time()
    
    # Set up conditions for transition
    # ... configure mocks ...
    
    # Run until state B
    success = run_until_state(sm, STATE_B, max_ticks=100)
    assert success
```

### Test Timeout

```python
def test_timeout(self):
    config = {'state_machine': {'timeouts': {IDLE: 0.1}}}
    sm, mocks = create_test_state_machine(config)
    
    # Wait for timeout
    time.sleep(0.15)
    sm.tick()
    
    # Should have transitioned
    assert sm.state != IDLE
```

### Test Safety Override

```python
def test_safety(self):
    sm, mocks = create_test_state_machine()
    sm.state = WANDERING
    
    # Trigger boundary
    mocks['obstacle_detector'].set_test_boundary(True)
    
    # Run a few ticks
    run_n_ticks(sm, 5)
    
    # Motors should stop or reverse
    left, right = mocks['chassis'].get_motor_values()
    assert left <= 0 or right <= 0
```

### Test Sub-State

```python
def test_sub_state(self):
    sm, mocks = create_test_state_machine()
    
    # Start in COLLECT_BALL
    sm.state = COLLECT_BALL
    sm.current_ball = {'color': 'silver', 'cx': 160}
    
    # Run one tick
    sm.tick()
    
    # Should be in APPROACH sub-state
    assert sm.collect_sub_state == CS_APPROACH
```

---

## Debugging Tests

### Print State Info

```python
print(f"State: {sm.state}")
print(f"Sub-state: {sm.collect_sub_state}")
print(f"Elapsed: {sm._elapsed():.2f}s")
print(f"Motors: {mocks['chassis'].get_motor_values()}")
print(f"Arm pose: {mocks['arm'].get_current_pose()}")
print(f"Camera pan: {mocks['camera'].get_pan()}°")
```

### Add Logging

```python
import logging

logger = logging.getLogger('test')
logger.setLevel(logging.DEBUG)

sm, mocks = create_test_state_machine(logger=logger)
```

### Step Through Manually

```python
# Run one tick at a time
for i in range(10):
    print(f"Tick {i}: State = {sm.state}")
    sm.tick()
    time.sleep(0.1)
```

---

## File Locations

```
tests/
├── __init__.py              # Test package
├── mocks.py                 # Mock hardware objects
├── test_utils.py            # Test utilities
└── test_state_machine.py    # Unit tests (15 tests)

simulation/tests/
├── __init__.py
└── test_scenario_happy_path.py  # Simulation test (1 scenario)

docs/
├── state-machine-complete.md    # Full documentation
├── state-machine-coverage.md    # Coverage tracking
└── state-machine-usage.md       # Usage guide (pending)

pytest.ini                   # Pytest configuration
```

---

## Quick Commands

```bash
# Install pytest
./venv/bin/pip install pytest

# Run all tests with verbose output
./venv/bin/python -m pytest tests/ -v

# Run tests with coverage (requires pytest-cov)
./venv/bin/pip install pytest-cov
./venv/bin/python -m pytest tests/ --cov=control --cov-report=term

# Run simulation test
./venv/bin/python src/simulation/tests/test_scenario_happy_path.py

# View documentation
cat docs/state-machine-complete.md
cat docs/state-machine-coverage.md
```

---

## Next Steps

1. **Run existing tests** to verify they work
2. **Review documentation** to understand state machine
3. **Write new tests** using templates above
4. **Run simulation tests** to see state machine in action
5. **Check coverage** to find gaps

---

**Quick Links**:
- Full Plan: `/home/steve/.windsurf/plans/state-machine-full-coverage-54037a.md`
- Complete Docs: `docs/state-machine-complete.md`
- Coverage Tracking: `docs/state-machine-coverage.md`
- Summary: `STATE-MACHINE-COVERAGE-SUMMARY.md`
