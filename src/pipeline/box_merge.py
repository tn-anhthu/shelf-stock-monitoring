"""Merge YOLO boxes that are really one physical product sliced into vertically
stacked fragments (see scripts/debug_box_fragments.py) back into a single box,
so downstream quantity counting and gap detection see the real product count.

Deliberately does NOT reuse row_clustering.cluster_rows: two fragments of one
split box often land in different row-clusters (their y-centers differ enough),
so this scans every pair directly instead.

Known limitation, not a bug: two distinct real products stacked close together
with no clear border (e.g. adjacent shelf tiers) could be merged incorrectly if
both happen to look short/flat. The aspect-ratio-anomaly gate reduces this risk
but does not eliminate it.
"""
import statistics
from typing import List

from src.detection.benchmark.metrics import Box


def _x_overlap_ratio(a: Box, b: Box) -> float:
    ax1, _, ax2, _ = a
    bx1, _, bx2, _ = b
    inter = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    narrower = min(ax2 - ax1, bx2 - bx1)
    return inter / narrower if narrower > 0 else 0.0


def _y_gap(a: Box, b: Box) -> float:
    _, ay1, _, ay2 = a
    _, by1, _, by2 = b
    if ay1 <= by1:
        return by1 - ay2
    return ay1 - by2


def _aspect_ratio(box: Box) -> float:
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    return h / w if w > 0 else float("inf")


def _merge_pair(a: Box, b: Box) -> Box:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def merge_adjacent_fragments(
    boxes: List[Box],
    x_overlap_threshold: float = 0.8,
    y_gap_tolerance: float = 5.0,
    aspect_ratio_anomaly_ratio: float = 0.6,
) -> List[Box]:
    if len(boxes) < 2:
        return list(boxes)

    median_aspect = statistics.median(_aspect_ratio(b) for b in boxes)
    anomaly_cutoff = aspect_ratio_anomaly_ratio * median_aspect

    current = list(boxes)
    merged_any = True
    while merged_any:
        merged_any = False
        for i in range(len(current)):
            for j in range(i + 1, len(current)):
                a, b = current[i], current[j]
                if _x_overlap_ratio(a, b) < x_overlap_threshold:
                    continue
                if abs(_y_gap(a, b)) > y_gap_tolerance:
                    continue
                if not (_aspect_ratio(a) < anomaly_cutoff or _aspect_ratio(b) < anomaly_cutoff):
                    continue
                merged = _merge_pair(a, b)
                current = [box for k, box in enumerate(current) if k != i and k != j] + [merged]
                merged_any = True
                break
            if merged_any:
                break

    return current
