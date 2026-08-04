"""Crop a detected box region out of the full shelf image before embedding it —
called directly by src/pipeline/scan.py::run_scan for each detected box.
"""
from typing import Optional

from PIL import Image

from src.detection.benchmark.metrics import Box


def crop_box(image: Image.Image, box: Box, padding_ratio: float = 0.0) -> Optional[Image.Image]:
    x1, y1, x2, y2 = box
    pad_x = (x2 - x1) * padding_ratio
    pad_y = (y2 - y1) * padding_ratio
    x1 -= pad_x
    y1 -= pad_y
    x2 += pad_x
    y2 += pad_y

    x1 = max(0.0, min(x1, image.width))
    y1 = max(0.0, min(y1, image.height))
    x2 = max(0.0, min(x2, image.width))
    y2 = max(0.0, min(y2, image.height))

    if x2 - x1 <= 0 or y2 - y1 <= 0:
        return None

    return image.crop((int(x1), int(y1), int(x2), int(y2)))
