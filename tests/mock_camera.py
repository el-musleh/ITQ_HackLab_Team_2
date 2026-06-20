import numpy as np

class MockCamera:
    _instance = None

    def __init__(self, width=300, height=300):
        self.width = width
        self.height = height
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

    @classmethod
    def instance(cls, *args, **kwargs):
        if cls._instance is None:
            width = kwargs.get('width', 300)
            height = kwargs.get('height', 300)
            cls._instance = cls(width=width, height=height)
        return cls._instance
