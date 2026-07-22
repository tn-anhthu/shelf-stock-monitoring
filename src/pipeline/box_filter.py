"""Drop boxes that are anomalously narrow relative to their row's average width —
a proxy for YOLO false positives on shelf-talkers/price signage rather than real
products, which otherwise pollute both gap detection and classification.
"""
from typing import List

from src.detection.benchmark.metrics import Box
from src.pipeline.row_clustering import cluster_rows


def filter_anomalous_boxes(
    boxes: List[Box],
    row_cluster_tolerance: float = 20.0,
    width_ratio_threshold: float = 0.65,
) -> List[Box]:
    if not boxes:
        return []

    rows = cluster_rows(boxes, row_cluster_tolerance)

    kept: List[Box] = []
    for row in rows:
        if len(row) < 2:
            kept.extend(row)
            continue
        avg_width = sum(b[2] - b[0] for b in row) / len(row)
        kept.extend(b for b in row if (b[2] - b[0]) >= width_ratio_threshold * avg_width)
    return kept
