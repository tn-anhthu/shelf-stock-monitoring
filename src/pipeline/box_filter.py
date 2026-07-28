"""Drop boxes that are anomalously narrow relative to their row's average width —
a proxy for YOLO false positives on shelf-talkers/price signage rather than real
products, which otherwise pollute both gap detection and classification.
"""
from typing import List, Tuple

from src.detection.benchmark.metrics import Box, compute_iou, containment_ratio
from src.pipeline.row_clustering import cluster_rows

# Same signature scripts/debug_duplicate_boxes.py used to confirm the 3 known
# duplicate-detection cases: high containment (one box almost entirely inside
# another) but IoU below the model's NMS default (0.7), so NMS itself never
# catches these - the two boxes are too different in size for IoU to look
# like a duplicate even though one is a near-total subset of the other.
CONTAINMENT_THRESHOLD = 0.8
NMS_DEFAULT_IOU = 0.7

# Bar for "does another box already independently cover the leftover region
# of B (beyond what its swallowed child covers)". Deliberately well below
# CONTAINMENT_THRESHOLD: the two known real cases show a wide gap between
# "genuinely independent coverage" (0.6, Haohao crop_45's box48, the bottom
# cup's own detection) and "no coverage at all" (0.0, Binggrae crop_38's
# strawberry side - no other box touches it), so this doesn't need to sit
# near either boundary.
LEFTOVER_COVERAGE_THRESHOLD = 0.3


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


def filter_contained_boxes(
    boxes: List[Box],
    containment_threshold: float = CONTAINMENT_THRESHOLD,
    iou_threshold: float = NMS_DEFAULT_IOU,
    leftover_coverage_threshold: float = LEFTOVER_COVERAGE_THRESHOLD,
) -> Tuple[List[Box], List[Box]]:
    """Drop an oversized box B only when every region it swallows already has
    independent coverage from another surviving box - otherwise B is the only
    box representing part of the shelf, so it's kept and flagged instead of
    silently dropped (which would under-count) or silently kept unflagged
    (which would double-count against its swallowed child).

    Returns (kept_boxes, flagged_boxes), where flagged_boxes is always a
    subset of kept_boxes - never a third disjoint list, and nothing is ever
    silently dropped except a B whose swallowed regions are all independently
    covered elsewhere.
    """
    if not boxes:
        return [], []

    def area(box: Box) -> float:
        x1, y1, x2, y2 = box
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)

    kept: List[Box] = []
    flagged: List[Box] = []
    for i, b in enumerate(boxes):
        others = [boxes[j] for j in range(len(boxes)) if j != i]

        # containment_ratio is symmetric (intersection / area of whichever box
        # is smaller) - it can't tell you which box is "the container" on its
        # own, so that direction has to be enforced here: b only ever swallows
        # a smaller box, never the other way around.
        children = [
            a for a in others
            if area(a) < area(b)
            and containment_ratio(a, b) >= containment_threshold
            and compute_iou(a, b) < iou_threshold
        ]
        if not children:
            kept.append(b)
            continue

        # Every child already exists independently in `boxes` by construction
        # (it's a real detected box); the open question is only whether B's
        # leftover area - the part of B beyond what its children cover - is
        # *also* independently covered by some other surviving box.
        non_children = [c for c in others if c not in children]
        leftover_covered = any(containment_ratio(c, b) >= leftover_coverage_threshold for c in non_children)
        if leftover_covered:
            continue  # B is redundant - drop it, its children stay in `boxes`

        kept.append(b)
        flagged.append(b)

    return kept, flagged
