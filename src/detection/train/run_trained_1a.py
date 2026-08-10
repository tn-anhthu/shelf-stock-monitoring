"""Wrapper around the YOLO26n nano checkpoint fine-tuned on the full SKU-110K
dataset (sku110k_yolo26n_results/weights/best.pt), matching the detect_1b/detect_1c
interface used by src/detection/benchmark/report.py so it plugs into the existing
eval/metrics code.

device="mps" is confirmed safe for YOLO26n (no CPU fallback needed) — see Task 1
of docs/superpowers/plans/2026-08-10-yolo26n-migration.md for the smoke test.
"""
from pathlib import Path
from typing import List

from PIL import Image
from ultralytics import YOLO

from src.detection.benchmark.metrics import Box


def load_model_1a(weights_path: Path):
    return YOLO(str(weights_path))


def detect_1a(model, image: Image.Image, conf: float = 0.25) -> List[Box]:
    results = model.predict(image, device="mps", conf=conf, verbose=False)
    boxes: List[Box] = []
    for box in results[0].boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        boxes.append((x1, y1, x2, y2))
    return boxes
