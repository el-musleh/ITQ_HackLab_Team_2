"""
ITQ HackLab Team 2 — Robot Test Suite

Run:  python -m tests.runner
Or:   Open tests/test_runner.ipynb in JupyterLab and run all cells

Each test module is self-contained and reports its own results.
Tests can be run independently or as part of the full suite.
"""

import sys

# Monkey patch jetbot.Camera with MockCamera if it fails to initialize
try:
    import jetbot
    from tests.mock_camera import MockCamera
    try:
        # Try to instantiate camera; if it fails, patch it with MockCamera
        c = jetbot.Camera.instance()
        # If it returned None or raised, we patch it
        if c is None:
            jetbot.Camera = MockCamera
    except Exception:
        jetbot.Camera = MockCamera
except Exception:
    pass

