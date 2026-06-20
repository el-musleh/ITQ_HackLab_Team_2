import traitlets
import atexit
import cv2
import threading
import numpy as np
from .camera_base import CameraBase

class MockCamera(traitlets.HasTraits):
    _instance = None
    value = traitlets.Any()
    
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.width = kwargs.get('width', 320)
        self.height = kwargs.get('height', 240)
        self.fps = kwargs.get('fps', 10)
        self._running = False
        self._thread = None
        self._frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Add yellow tape representation
        y_start = int(self.height * 0.75)
        y_end = int(self.height * 0.90)
        self._frame[y_start:y_end, :] = [0, 255, 255]
        
        # Add obstacle representation
        o_start = int(self.height * 0.3)
        o_end = int(self.height * 0.5)
        self._frame[o_start:o_end, int(self.width*0.25):int(self.width*0.75)] = [128, 128, 128]
        
        self.value = self._frame
        self.start()

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._run_simulation)
            self._thread.daemon = True
            self._thread.start()

    def stop(self):
        self._running = False
        self._thread = None

    def _run_simulation(self):
        import time
        dt = 1.0 / self.fps
        while self._running:
            time.sleep(dt)
            self.value = self._frame.copy()

    @classmethod
    def instance(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = cls(*args, **kwargs)
        return cls._instance

class OpenCvGstCamera(CameraBase):
    
    value = traitlets.Any()
    
    # config
    width = traitlets.Integer(default_value=224).tag(config=True)
    height = traitlets.Integer(default_value=224).tag(config=True)
    fps = traitlets.Integer(default_value=30).tag(config=True)
    capture_width = traitlets.Integer(default_value=816).tag(config=True)
    capture_height = traitlets.Integer(default_value=616).tag(config=True)

    def __init__(self, *args, **kwargs):
        self.value = np.empty((self.height, self.width, 3), dtype=np.uint8)
        super().__init__(self, *args, **kwargs)

        try:
            self.cap = cv2.VideoCapture(self._gst_str(), cv2.CAP_GSTREAMER)

            re, image = self.cap.read()

            if not re:
                raise RuntimeError('Could not read image from camera.')

            self.value = image
            self.start()
        except:
            self.stop()
            raise RuntimeError(
                'Could not initialize camera.  Please see error trace.')

        atexit.register(self.stop)

    def _capture_frames(self):
        while True:
            re, image = self.cap.read()
            if re:
                self.value = image
            else:
                break
                
    def _gst_str(self):
        return 'nvarguscamerasrc sensor-mode=3 ! video/x-raw(memory:NVMM), width=%d, height=%d, format=(string)NV12, framerate=(fraction)%d/1 ! nvvidconv ! video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! videoconvert ! appsink' % (
                self.capture_width, self.capture_height, self.fps, self.width, self.height)
    
    def start(self):
        if not self.cap.isOpened():
            self.cap.open(self._gst_str(), cv2.CAP_GSTREAMER)
        if not hasattr(self, 'thread') or not self.thread.isAlive():
            self.thread = threading.Thread(target=self._capture_frames)
            self.thread.start()

    def stop(self):
        if hasattr(self, 'cap'):
            self.cap.release()
        if hasattr(self, 'thread'):
            self.thread.join()
            
    def restart(self):
        self.stop()
        self.start()
        
    @staticmethod
    def instance(*args, **kwargs):
        try:
            return OpenCvGstCamera(*args, **kwargs)
        except Exception as e:
            print("Could not initialize real camera. Falling back to MockCamera.")
            return MockCamera.instance(*args, **kwargs)
