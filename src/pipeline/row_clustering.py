"""Group detected boxes into shelf rows by y-center proximity. Shared by
gap_detection.py and box_filter.py, which both need to reason about boxes
row-by-row before comparing widths/spacing within a row.
"""
from typing import List

from src.detection.benchmark.metrics import Box


def box_y_center(box: Box) -> float:
    return (box[1] + box[3]) / 2


def cluster_rows(
    boxes: List[Box],
    tolerance: float,
    max_span_multiplier: float = 2.0,
) -> List[List[Box]]:
    """Group boxes into rows by comparing each new box to the CURRENT row's
    running mean y-center, with a hard cap on the row's total y-center span
    (tolerance * max_span_multiplier). Both conditions must hold to join a
    row.

    Fixes a confirmed chaining bug (docs/detection-notes/detection-log.md,
    "04/08/2026" entry): the previous version compared each new box only to
    the last box appended to the row, letting a row drift arbitrarily far
    from its starting point as long as each consecutive step stayed within
    tolerance -- a single-linkage-style failure mode. Comparing to the row
    mean alone weakens this (one bridging box only shifts the mean by 1/n)
    but does not fully bound it in the adversarial case where the mean
    itself drifts gradually across many boxes -- see
    test_cluster_rows_span_cap_catches_drift_mean_check_alone_would_miss in
    tests/pipeline/test_row_clustering.py for a concrete example. The span
    cap closes that gap directly.
    """
    sorted_boxes = sorted(boxes, key=box_y_center)
    rows: List[List[Box]] = []
    for box in sorted_boxes:
        yc = box_y_center(box)
        if rows:
            row_centers = [box_y_center(b) for b in rows[-1]]
            row_mean = sum(row_centers) / len(row_centers)
            # sorted ascending -> yc is always >= every center already in the
            # row, so the span if this box joins is yc - the row's smallest
            # center (row_centers[0]).
            span_if_added = yc - row_centers[0]
            fits_mean = (yc - row_mean) <= tolerance
            fits_span = span_if_added <= tolerance * max_span_multiplier
            if fits_mean and fits_span:
                rows[-1].append(box)
                continue
        rows.append([box])
    return rows
