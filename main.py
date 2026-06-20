#!/usr/bin/env python3
"""Entry point for ITQ Bottle Cap Collector.

Run on NVIDIA Jetson Nano via Jupyter or command line.
"""

import sys
import time
from perception.detector import CapDetector
from hardware.chassis import Chassis
from hardware.arm import Arm
from control.state_machine import StateMachine

def main():
    print("=" * 50)
    print("ITQ Bottle Cap Collector — Team 2")
    print("=" * 50)
    
    # Initialize hardware
    detector = CapDetector()
    chassis = Chassis()
    arm = Arm()
    state_machine = StateMachine(detector, chassis, arm)
    
    print("Hardware initialized. Starting state machine...")
    print("Press Ctrl+C to stop.\n")
    
    try:
        while True:
            state_machine.tick()
            time.sleep(0.05)  # 20 Hz control loop
    except KeyboardInterrupt:
        print("\nShutting down...")
        chassis.stop()
        arm.reset()
        sys.exit(0)

if __name__ == "__main__":
    main()
