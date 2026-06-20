try:
    import tensorrt as trt
    from jetbot.ssd_tensorrt import load_plugins, parse_boxes, TRT_INPUT_NAME, TRT_OUTPUT_NAME
    from .tensorrt_model import TRTModel
    import numpy as np
    import cv2
    HAS_TRT = True
except Exception:
    import numpy as np
    import cv2
    HAS_TRT = False

mean = 255.0 * np.array([0.5, 0.5, 0.5])
stdev = 255.0 * np.array([0.5, 0.5, 0.5])


def bgr8_to_ssd_input(camera_value):
    x = camera_value
    x = cv2.cvtColor(x, cv2.COLOR_BGR2RGB)
    x = cv2.resize(x, (300, 300))
    x = x.transpose((2, 0, 1)).astype(np.float32)
    x -= mean[:, None, None]
    x /= stdev[:, None, None]
    return x[None, ...]


class ObjectDetector(object):
    
    def __init__(self, engine_path, preprocess_fn=bgr8_to_ssd_input):
        self.preprocess_fn = preprocess_fn
        self.mock_mode = False
        
        if HAS_TRT:
            try:
                logger = trt.Logger()
                trt.init_libnvinfer_plugins(logger, '')
                load_plugins()
                self.trt_model = TRTModel(engine_path, input_names=[TRT_INPUT_NAME],
                                          output_names=[TRT_OUTPUT_NAME, TRT_OUTPUT_NAME + '_1'])
            except Exception as e:
                print("Failed to initialize TensorRT TRTModel: {}. Falling back to mock ObjectDetector.".format(e))
                self.mock_mode = True
        else:
            print("TensorRT not available. Falling back to mock ObjectDetector.")
            self.mock_mode = True
        
    def execute(self, *inputs):
        if self.mock_mode:
            # Return a mock detection list (e.g. a cup or person in the center)
            # Detections structure is: [[{'label': 1, 'confidence': 0.95, 'bbox': [0.4, 0.4, 0.6, 0.6]}]]
            return [[
                {
                    'label': 1,  # track label
                    'confidence': 0.95,
                    'bbox': [0.4, 0.4, 0.6, 0.6]
                }
            ]]
        else:
            trt_outputs = self.trt_model(self.preprocess_fn(*inputs))
            return parse_boxes(trt_outputs)
    
    def __call__(self, *inputs):
        return self.execute(*inputs)
