"""
Simulation Hardware Module
Drop-in replacement for hardware module.

This module provides hardware-compatible interfaces for simulation.
Classes have IDENTICAL APIs to real hardware, enabling seamless switching
between simulation and real robot with a single import change.

Usage:
    # In simulation
    from simulation import ChassisController, ArmController, CameraController

    # On real hardware
    from hardware.chassis import ChassisController
    from hardware.arm import ArmController
    from hardware.camera import CameraController

    # Rest of code is identical!
"""

from .sim_core import SimulationCore
from .sim_hardware import (
    ChassisController,
    ArmController,
    CameraController,
    create_sim_hardware
)

__all__ = [
    'SimulationCore',
    'ChassisController',
    'ArmController',
    'CameraController',
    'create_sim_hardware'
]
