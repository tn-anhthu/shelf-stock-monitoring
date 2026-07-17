"""IoU, precision, recall metrics for comparing predicted boxes against ground-truth boxes.

Boxes are (x1, y1, x2, y2) tuples in absolute pixel coordinates.

Note: this module computes precision/recall/F1 at a single fixed IoU threshold
(0.5 by default), matched greedily by descending IoU. It does NOT compute
COCO-style interpolated Average Precision (AP) across confidence thresholds —
do not label these numbers "AP" anywhere they're reported.
"""
from typing import Dict, List, Tuple

Box = Tuple[float, float, float, float]


def compute_iou(box_a: Box, box_b: Box) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union_area = area_a + area_b - inter_area

    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def match_boxes(
    pred_boxes: List[Box], gt_boxes: List[Box], iou_threshold: float = 0.5
) -> Tuple[int, int, int]:
    """Greedy one-to-one matching by descending IoU. Returns (tp, fp, fn)."""
    candidates = []
    for pi, pb in enumerate(pred_boxes):
        for gi, gb in enumerate(gt_boxes):
            iou = compute_iou(pb, gb)
            if iou >= iou_threshold:
                candidates.append((iou, pi, gi))
    candidates.sort(key=lambda c: c[0], reverse=True)

    matched_pred = set()
    matched_gt = set()
    for _iou, pi, gi in candidates:
        if pi in matched_pred or gi in matched_gt:
            continue
        matched_pred.add(pi)
        matched_gt.add(gi)

    tp = len(matched_pred)
    fp = len(pred_boxes) - len(matched_pred)
    fn = len(gt_boxes) - len(matched_gt)
    return tp, fp, fn


def compute_precision_recall(
    pred_boxes: List[Box], gt_boxes: List[Box], iou_threshold: float = 0.5
) -> Dict[str, float]:
    tp, fp, fn = match_boxes(pred_boxes, gt_boxes, iou_threshold)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall}


def aggregate_precision_recall(per_image_results: List[Dict[str, float]]) -> Dict[str, float]:
    """Micro-average tp/fp/fn across images into a single precision/recall."""
    total_tp = sum(r["tp"] for r in per_image_results)
    total_fp = sum(r["fp"] for r in per_image_results)
    total_fn = sum(r["fn"] for r in per_image_results)
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    return {
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_fn,
        "precision": precision,
        "recall": recall,
    }
