import traitlets
import numpy as np
import threading
import time

class MockCamera(traitlets.HasTraits):
    _instance = None
    value = traitlets.Any()

    def __init__(self, width=320, height=240, fps=10):
        super().__init__()
        self.width = width
        self.height = height
        self.fps = fps
        self._running = False
        self._thread = None
        
        # Generate a simulated frame
        self._frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Add some "yellow tape" in the bottom region (BGR yellow: 0, 255, 255)
        # Yellow detection looks at: frame[int(h * 0.70):, :]
        y_start = int(height * 0.75)
        y_end = int(height * 0.90)
        self._frame[y_start:y_end, :] = [0, 255, 255]
        
        # Add some obstacles (e.g., white block) in the middle region for edge detection
        # Obstacle detection looks at: frame[int(h * 0.15):int(h * 0.65), :]
        o_start = int(height * 0.3)
        o_end = int(height * 0.5)
        self._frame[o_start:o_end, int(width*0.25):int(width*0.75)] = [128, 128, 128]
        
        # Set initial value and start thread
        self.value = self._frame
        self._start_simulation()

    def start(self):
        if not self._running:
            self._start_simulation()

    def stop(self):
        self._running = False
        self._thread = None

    def _start_simulation(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_simulation)
        self._thread.daemon = True
        self._thread.start()

    def _run_simulation(self):
        dt = 1.0 / self.fps
        while self._running:
            time.sleep(dt)
            # Re-assign to trigger traitlet observation
            self.value = self._frame.copy()

    @classmethod
    def instance(cls, *args, **kwargs):
        if cls._instance is None:
            width = kwargs.get('width', 320)
            height = kwargs.get('height', 240)
            cls._instance = cls(width=width, height=height)
        return cls._instance
