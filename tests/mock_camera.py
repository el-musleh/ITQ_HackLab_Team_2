import numpy as np
import threading
import time

class MockCamera:
    _instance = None

    def __init__(self, width=320, height=240, fps=10):
        self.width = width
        self.height = height
        self.fps = fps
        self.callbacks = []
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

    @property
    def value(self):
        return self._frame

    def observe(self, callback, names='value'):
        if callback not in self.callbacks:
            self.callbacks.append(callback)
        if not self._running:
            self._start_simulation()

    def unobserve_all(self):
        self.callbacks = []
        self.stop()

    def stop(self):
        self._running = False
        if self._thread is not None:
            # Do not join to avoid blocking jupyter notebook cell execution
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
            # Create a change dict similar to traitlets/jetbot Camera
            change = {
                'new': self._frame,
                'name': 'value',
                'type': 'change',
                'owner': self
            }
            # Call all observers safely
            for cb in list(self.callbacks):
                try:
                    cb(change)
                except Exception:
                    pass

    @classmethod
    def instance(cls, *args, **kwargs):
        if cls._instance is None:
            width = kwargs.get('width', 320)
            height = kwargs.get('height', 240)
            cls._instance = cls(width=width, height=height)
        return cls._instance
