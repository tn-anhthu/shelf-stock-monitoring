"""Flag suspiciously wide horizontal spacing between adjacent detected products in
the same shelf row, as a proxy for an out-of-stock gap on the physical shelf.
"""
import statistics
from typing import List

from src.detection.benchmark.metrics import Box
from src.pipeline.row_clustering import cluster_rows


def detect_gaps(
    boxes: List[Box],
    row_cluster_tolerance: float = 20.0,
    width_multiplier: float = 0.9,
) -> List[Box]:
    if len(boxes) < 2:
        return []

    global_median_width = statistics.median(box[2] - box[0] for box in boxes)
    rows = cluster_rows(boxes, row_cluster_tolerance)

    gaps: List[Box] = []
    for row in rows:
        row = sorted(row, key=lambda b: b[0])
        if len(row) < 2:
            avg_width = global_median_width  # no adjacent pair to apply it to
            continue
        avg_width = sum(b[2] - b[0] for b in row) / len(row)

        for i in range(len(row) - 1):
            current, nxt = row[i], row[i + 1]
            gap_width = nxt[0] - current[2]
            if gap_width > width_multiplier * avg_width:
                gaps.append((current[2], min(current[1], nxt[1]), nxt[0], max(current[3], nxt[3])))

    return gaps
