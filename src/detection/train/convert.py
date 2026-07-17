"""Convert COCO-style bounding boxes (harryrobert/SKU-110k-reformat's `objects.bbox`
format) to YOLO training label lines.

COCO-style box: (x, y, w, h) in absolute pixel coordinates, top-left origin.
YOLO label line: "class cx cy w h" — cx/cy/w/h normalized to [0, 1] relative to
image size; cx/cy are the box CENTER (not top-left), unlike the COCO input.
"""
from typing import List, Tuple

CocoBox = Tuple[float, float, float, float]


def coco_bbox_to_yolo_line(
    bbox: CocoBox, image_width: int, image_height: int, class_id: int = 0
) -> str:
    x, y, w, h = bbox
    cx = (x + w / 2) / image_width
    cy = (y + h / 2) / image_height
    nw = w / image_width
    nh = h / image_height
    return f"{class_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}"


def coco_objects_to_yolo_lines(
    bboxes: List[CocoBox], image_width: int, image_height: int, class_id: int = 0
) -> List[str]:
    return [coco_bbox_to_yolo_line(b, image_width, image_height, class_id) for b in bboxes]
