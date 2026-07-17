"""Wrapper around the foduucom/product-detection-in-shelf-yolov8 checkpoint.

Source: https://huggingface.co/foduucom/product-detection-in-shelf-yolov8
Self-reported mAP@0.5(box) = 0.910 by the model author (not independently verified).
Supported labels per the model card: ['Empty Shelves', 'Magical Products'] — we only
care about the product-presence class for localization, not the label text itself.

Requires MPS (Apple Silicon) or CPU — cannot run in a Linux cloud sandbox without a
compatible torch/MPS build. Run this on the M4 MacBook Pro.
"""
from typing import List

from PIL import Image
from ultralyticsplus import YOLO

from src.detection.benchmark.metrics import Box

MODEL_ID = "foduucom/product-detection-in-shelf-yolov8"


def load_model_1b():
    model = YOLO(MODEL_ID)
    model.overrides["conf"] = 0.25
    model.overrides["iou"] = 0.45
    model.overrides["agnostic_nms"] = False
    model.overrides["max_det"] = 1000
    return model


def detect_1b(model, image: Image.Image, conf: float = 0.25) -> List[Box]:
    model.overrides["conf"] = conf
    results = model.predict(image, device="mps", verbose=False)
    boxes: List[Box] = []
    for box in results[0].boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        boxes.append((x1, y1, x2, y2))
    return boxes
