import traitlets
import atexit
import cv2
import threading
import numpy as np
import sys
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
        self._use_v4l2 = False

        try:
            # 1. Try GStreamer first
            self.cap = cv2.VideoCapture(self._gst_str(), cv2.CAP_GSTREAMER)
            re, image = self.cap.read()
            if not re:
                raise RuntimeError('GStreamer read returned False')
            self.value = image
            self.start()
            print("Real GStreamer camera initialized successfully.")
        except Exception as e_gst:
            print("GStreamer camera failed: {}".format(e_gst))
            print("Trying direct V4L2 camera fallback on /dev/video0...")
            try:
                # 2. Try V4L2 fallback on /dev/video0
                self.cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
                re, image = self.cap.read()
                if not re:
                    raise RuntimeError('V4L2 read returned False')
                self._use_v4l2 = True
                self.value = cv2.resize(image, (self.width, self.height))
                self.start()
                print("Direct V4L2 camera fallback initialized successfully.")
            except Exception as e_v4l2:
                print("V4L2 direct camera fallback failed: {}".format(e_v4l2))
                self.stop()
                raise RuntimeError('Could not initialize camera via GStreamer or V4L2.')

        atexit.register(self.stop)

    def _capture_frames(self):
        while True:
            re, image = self.cap.read()
            if re:
                if self._use_v4l2:
                    image = cv2.resize(image, (self.width, self.height))
                self.value = image
            else:
                break
                
    def _gst_str(self):
        return 'nvarguscamerasrc sensor-mode=3 ! video/x-raw(memory:NVMM), width=%d, height=%d, format=(string)NV12, framerate=(fraction)%d/1 ! nvvidconv ! video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! videoconvert ! appsink' % (
                self.capture_width, self.capture_height, self.fps, self.width, self.height)
    
    def start(self):
        if not self.cap.isOpened():
            if self._use_v4l2:
                self.cap.open(0, cv2.CAP_V4L2)
            else:
                self.cap.open(self._gst_str(), cv2.CAP_GSTREAMER)
        if not hasattr(self, 'thread') or not self.thread.isAlive():
            self.thread = threading.Thread(target=self._capture_frames)
            self.thread.start()

    def stop(self):
        if hasattr(self, 'cap'):
            self.cap.release()
        if hasattr(self, 'thread'):
            self.thread.join(timeout=1.0)
            
    def restart(self):
        self.stop()
        self.start()
        
    @staticmethod
    def instance(*args, **kwargs):
        try:
            return OpenCvGstCamera(*args, **kwargs)
        except Exception as e:
            print("Could not initialize real GStreamer or V4L2 camera. Falling back to MockCamera.")
            return MockCamera.instance(*args, **kwargs)
