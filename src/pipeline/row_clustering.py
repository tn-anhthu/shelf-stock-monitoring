"""Group detected boxes into shelf rows by y-center proximity. Shared by
gap_detection.py and box_filter.py, which both need to reason about boxes
row-by-row before comparing widths/spacing within a row.
"""
from typing import List

from src.detection.benchmark.metrics import Box


def box_y_center(box: Box) -> float:
    return (box[1] + box[3]) / 2


def cluster_rows(boxes: List[Box], tolerance: float) -> List[List[Box]]:
    sorted_boxes = sorted(boxes, key=box_y_center)
    rows: List[List[Box]] = []
    for box in sorted_boxes:
        if rows and box_y_center(box) - box_y_center(rows[-1][-1]) <= tolerance:
            rows[-1].append(box)
        else:
            rows.append([box])
    return rows
