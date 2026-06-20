"""
Test Suite Runner — command line entry point.

Usage:
    python -m tests.runner          # run all tests
    python -m tests.test_camera       # run only camera tests
    python -m tests.test_motors       # run only motor tests
    python -m tests.test_servos       # run only servo tests
    python -m tests.test_perception   # run only perception tests
    python -m tests.test_state_machine # run only logic tests
    python -m tests.test_integration  # run only integration tests

Or open tests/test_runner.ipynb in JupyterLab for interactive testing.
"""
import sys

from tests import test_results
from tests.test_camera import run_all as run_camera
from tests.test_motors import run_all as run_motors
from tests.test_servos import run_all as run_servos
from tests.test_perception import run_all as run_perception
from tests.test_state_machine import run_all as run_state_machine
from tests.test_integration import run_all as run_integration


def run_all():
    """Execute the full test suite and print summary."""
    test_results.reset()
    print("=" * 60)
    print("  ITQ HACKLAB TEAM 2 — ROBOT TEST SUITE")
    print("=" * 60)
    print()

    # 1. Logic tests (no hardware)
    run_state_machine()

    # 2. Hardware tests
    camera, source = run_camera()
    robot = run_motors()
    servo = run_servos()

    # 3. Perception (needs camera)
    run_perception(camera, source)

    # 4. Integration
    run_integration()

    # Summary
    print()
    return test_results.summary()


def run_subset(modules):
    """Run only specified test modules."""
    test_results.reset()
    for name, func in modules:
        print(f"\n>>> Running {name}")
        func()
    print()
    return test_results.summary()


if __name__ == "__main__":
    args = sys.argv[1:]

    if len(args) == 0 or "all" in args:
        run_all()
    else:
        mapping = {
            "camera":      ("Camera",      run_camera),
            "motors":      ("Motors",      run_motors),
            "servos":      ("Servos",      run_servos),
            "perception":  ("Perception",  run_perception),
            "state":       ("State Machine", run_state_machine),
            "logic":       ("State Machine", run_state_machine),
            "integration": ("Integration", run_integration),
        }
        selected = []
        for arg in args:
            key = arg.lower()
            if key in mapping:
                selected.append(mapping[key])
            else:
                print(f"Unknown module: {arg}")
                print(f"Valid: {', '.join(mapping.keys())}")
                sys.exit(1)
        run_subset(selected)
