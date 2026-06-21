# YOLOv8 Ball Detection — Future Enhancement

**Status:** Not implemented — documented for future consideration  
**Date:** June 21, 2026

---

## Overview

The current ball detection uses HSV color segmentation with shape filtering (circularity, aspect ratio, size). This works well in controlled lighting but is sensitive to lighting changes and reflections. YOLOv8n (nano) is a possible drop-in replacement that would improve robustness using learned features.

## Feasibility on Jetson Nano

| Factor | Details |
|--------|---------|
| **Model** | YOLOv8n (nano) — 3.2M params, smallest variant |
| **Speed** | 10-15 FPS with TensorRT FP16 engine |
| **Memory** | ~500MB GPU (fits in 4GB shared RAM) |
| **Input size** | 320×320 or 416×416 (matches 320×240 camera) |
| **ultralytics** | Already installed in project venv |
| **TensorRT** | Team has experience (ResNet18 collision avoidance notebooks) |

## HSV vs YOLOv8 Comparison

| Aspect | HSV (current) | YOLOv8n |
|--------|---------------|---------|
| **Speed** | 30+ FPS | 10-15 FPS (TensorRT) |
| **Accuracy** | Good for known colors | Better for varied lighting |
| **False positives** | Possible from reflections | Lower (learned features) |
| **Training needed** | None | 200+ annotated images |
| **Robustness** | Sensitive to lighting | More robust |
| **Obstacle vs ball** | Relies on color separation | Can train "not ball" classes |
| **Memory** | Minimal | ~500MB GPU |
| **Setup time** | Done | 4-6 hours |

## What Would Be Needed

### Phase 1: Data Collection & Training (2-4 hours)
1. Capture 200-500 images of bottle caps (blue, red, silver) in various arena positions
2. Annotate with bounding boxes (Roboflow or CVAT)
3. Train YOLOv8n on a PC/laptop with GPU (not on Jetson — too slow)
4. Export to ONNX → TensorRT engine

### Phase 2: Integration (1-2 hours)
1. Create `src/perception/yolo_ball_detector.py` with same API as `BallDetector`
2. Load TensorRT engine, run inference per frame
3. Map YOLO bounding boxes → `(color, centroid, distance, area)` format
4. Config flag to switch between HSV and YOLO detectors

### Phase 3: Testing & Tuning (1 hour)
1. Compare detection accuracy vs HSV
2. Tune confidence threshold (0.5+ recommended)
3. Verify FPS on Jetson

## Integration Approach

The YOLO detector would be a **drop-in replacement** for `BallDetector`:

```python
# config.yaml
ball_detector_type: hsv  # 'hsv' or 'yolo'

yolo:
  model_path: models/ball_detector_v8n.pt  # or .engine for TensorRT
  confidence_threshold: 0.5
  input_size: 320
  class_names:
    0: blue
    1: red
    2: silver
  known_ball_diameter_cm: 3.5
  focal_length_px: 300
```

```python
# src/perception/yolo_ball_detector.py (conceptual)
class YOLOBallDetector:
    def __init__(self, config):
        from ultralytics import YOLO
        self.model = YOLO(config['model_path'])
        self.confidence = config.get('confidence_threshold', 0.5)
        # ... same distance estimation params as BallDetector

    def detect(self, frame):
        results = self.model(frame, conf=self.confidence)
        # Convert YOLO boxes to (color, centroid, distance, area) format
        return detections  # Same format as BallDetector.detect()
```

The state machine would select the detector based on config:
```python
if config.get('ball_detector_type') == 'yolo':
    from src.perception.yolo_ball_detector import YOLOBallDetector
    self.ball_detector = YOLOBallDetector(config)
else:
    from src.perception.ball_detector import BallDetector
    self.ball_detector = BallDetector(config)
```

## Current Assets

- **ultralytics** package installed in venv
- **Roboflow cloud model** exists (`notebooks/detection/use_model.ipynb`) — trained but requires internet
- **ResNet18 collision avoidance** notebooks show team's PyTorch/CUDA/TensorRT experience
- **TensorRT export notebooks** in `notebooks/collison_aviodance/`

## Recommendation

The current HSV detector with the robustness improvements (multi-frame validation, size/aspect ratio checks, obstacle cross-validation, tightened silver HSV) is sufficient for the competition. YOLOv8 would be a post-competition enhancement for more challenging lighting conditions.

**Priority:** Low — only pursue if HSV detection proves inadequate during on-site testing.
