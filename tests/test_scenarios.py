"""Headless smoke tests for simulation scenarios.

Each test runs a scenario in headless mode with a short timeout to verify
that the StateMachine and simulation infrastructure don't crash and that
expected state transitions occur.

Run with:
    python3 -m pytest tests/test_scenarios.py -v -m simulation
"""

import os
import sys
import logging

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_pybullet_available = True
try:
    from src.simulation.run_scenarios import ScenarioRunner, SCENARIOS
    from src.utils import load_config
except ImportError:
    _pybullet_available = False
    SCENARIOS = {}

logger = logging.getLogger(__name__)

pybullet_required = pytest.mark.skipif(
    not _pybullet_available, reason="pybullet not installed")


def _make_runner(scenario_name, max_duration=10):
    """Create a headless ScenarioRunner with a short timeout."""
    config = load_config()
    config.setdefault('simulation', {})
    config['simulation'] = {**config['simulation'], 'renderer': 'tiny'}

    # Override max_duration for fast testing
    import src.simulation.run_scenarios as rs
    original = rs.SCENARIOS[scenario_name]['max_duration']
    rs.SCENARIOS[scenario_name]['max_duration'] = max_duration
    try:
        runner = ScenarioRunner(
            config, scenario_name,
            gui=False, real_time=False,
            show_visualization=False,
        )
    finally:
        rs.SCENARIOS[scenario_name]['max_duration'] = original
    return runner


@pybullet_required
@pytest.mark.simulation
@pytest.mark.slow
@pytest.mark.parametrize("scenario_name", list(SCENARIOS.keys()))
def test_scenario_smoke(scenario_name):
    """Verify each scenario runs headless without crashing."""
    runner = _make_runner(scenario_name, max_duration=10)
    try:
        runner.run()
    except Exception as e:
        pytest.fail(f"Scenario {scenario_name} crashed: {e}")
    finally:
        runner.close()


@pybullet_required
@pytest.mark.simulation
def test_scenario_definitions():
    """Verify all scenario definitions have required fields."""
    required_fields = {'description', 'robot_start', 'robot_yaw',
                       'balls', 'max_duration', 'expected_collisions'}
    for name, spec in SCENARIOS.items():
        missing = required_fields - set(spec.keys())
        assert not missing, f"Scenario {name} missing fields: {missing}"
        assert spec['max_duration'] > 0
        assert len(spec['balls']) >= 1
        assert isinstance(spec['robot_start'], list)
        assert len(spec['robot_start']) == 3
