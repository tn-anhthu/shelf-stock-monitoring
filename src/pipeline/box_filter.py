"""Drop boxes that are anomalously narrow relative to their row's average width —
a proxy for YOLO false positives on shelf-talkers/price signage rather than real
products, which otherwise pollute both gap detection and classification.
"""
from typing import List, Tuple

from src.detection.benchmark.metrics import Box, compute_iou, containment_ratio
from src.pipeline.row_clustering import cluster_rows

# Same signature scripts/archive/debug_duplicate_boxes.py used to confirm the 3 known
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
) -> Tuple[List[Box], List[Box], List[Tuple[Box, Box]]]:
    """Drop an oversized box B only when every region it swallows already has
    independent coverage from another surviving box - otherwise B is the only
    box representing part of the shelf, so it's kept and flagged instead of
    silently dropped (which would under-count) or silently kept unflagged
    (which would double-count against its swallowed child).

    Returns (kept_boxes, flagged_boxes, flagged_pairs), where flagged_boxes is
    always a subset of kept_boxes - never a third disjoint list, and nothing
    is ever silently dropped except a B whose swallowed regions are all
    independently covered elsewhere.

    flagged_pairs is a (parent, child) tuple for every child box "swallowed"
    by a flagged parent - one tuple per child, so a parent with multiple
    children produces multiple pairs. This function doesn't decide which of
    the two is correct - that requires classify confidence, which doesn't
    exist yet at this geometry-only stage - it just hands the candidate pairs
    to the caller (scan.py) to resolve after classification.
    """
    if not boxes:
        return [], [], []

    def area(box: Box) -> float:
        x1, y1, x2, y2 = box
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)

    kept: List[Box] = []
    flagged: List[Box] = []
    flagged_pairs: List[Tuple[Box, Box]] = []
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
        for child in children:
            flagged_pairs.append((b, child))

    # A child recorded above can still end up independently dropped by its
    # OWN loop iteration: a 3+ level nesting chain (grandparent contains
    # middle contains small) always makes `middle`'s leftover trivially
    # "covered" by `grandparent` alone (containment_ratio(grandparent,
    # middle) == 1.0, since middle sits fully inside it) - regardless of
    # whether middle's own leftover is genuinely covered elsewhere too - so
    # middle gets dropped as redundant in its own iteration even though
    # grandparent's (separately computed) children list still names it. Only
    # kept boxes are real, current detections; scan.py resolves flagged_pairs
    # by confidence, which requires both boxes to actually still exist.
    kept_set = set(kept)
    flagged_pairs = [(parent, child) for parent, child in flagged_pairs if child in kept_set]

    return kept, flagged, flagged_pairs
