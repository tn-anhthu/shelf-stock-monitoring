"""Measure IoU vs. containment ratio for the 3 known "duplicate box on one
physical product" cases, to decide the right fix: adjusting `iou` in
`model.predict()` (src/detection/train/run_trained_1a.py::detect_1a) like
originally planned, or adding a dedicated containment filter (in the spirit of
box_filter.py) that drops any box almost entirely swallowed by another.

No model run here — these are the real post-merge/post-filter box coordinates
from a previous real run, recovered by re-running detect_1a + merge_adjacent_
fragments + filter_anomalous_boxes on the same input photos with the same
weights (runs/detect/runs/train_1a/n_2000/weights/best.pt) that produced
data/scan_viz/test1 and data/scan_viz/test2, then cross-checked against the
already-saved crop_XX_ok.jpg files so the index -> product mapping below is
verified, not guessed:

  - Vinamilk ("case cũ" from docs/specs/2026-07-20-shelfsense-mvp-design.md's
    2026-07-21 entry): data/scan_viz/test2 (kệ sữa), boxes 73/74/86/89 — 4
    overlapping detections on the same "Vinamilk 100% Sữa tươi" 1L carton
    (73/74 catch the top logo half + full carton, 86/89 catch the bottom
    cow-pattern half — confirmed by cropping each box directly from
    data/scan_viz/input/test2.HEIC).
  - crop_38 (2 hộp binggrae): data/scan_viz/test1, boxes 37/38 — box 38 is
    oversized and swallows box 37 (confirmed: crop_37_ok.jpg shows only the
    Melon carton, crop_38_ok.jpg shows both Melon and Strawberry).
  - crop_45 (2 hộp haohao): data/scan_viz/test1, boxes 41/45 — box 45 is
    oversized and swallows box 41 (confirmed: crop_41_ok.jpg shows one Tom
    Chua Cay cup tightly, crop_45_ok.jpg shows that same cup plus another
    cup peeking below it).

Usage:
    python3 scripts/debug_duplicate_boxes.py
"""
import sys
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.benchmark.metrics import Box, compute_iou

# containment >= this and iou below the model's NMS default (0.7) is the
# "high containment, only moderate/low IoU" signature this script checks for.
CONTAINMENT_THRESHOLD = 0.8
NMS_DEFAULT_IOU = 0.7

KNOWN_CASES: Dict[str, Dict[str, Box]] = {
    "Vinamilk 1L carton (case cũ, test2)": {
        "box73_logo_top": (482.6, 2900.3, 688.6, 3113.2),
        "box74_full_carton": (494.2, 2862.0, 692.0, 3310.2),
        "box86_cow_pattern": (501.1, 2977.9, 703.3, 3311.9),
        "box89_bottom_subset": (506.2, 3106.8, 710.9, 3306.3),
    },
    "binggrae (crop_38, test1)": {
        "box37_melon_only": (702.7, 2476.3, 819.0, 2772.5),
        "box38_melon+strawberry": (610.1, 2478.3, 820.7, 2808.7),
    },
    "haohao (crop_45, test1)": {
        "box41_top_cup_only": (1109.0, 2840.4, 1326.8, 3116.4),
        "box45_both_cups": (1116.5, 2843.7, 1326.5, 3254.9),
    },
}


def box_area(box: Box) -> float:
    x1, y1, x2, y2 = box
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def containment_ratio(a: Box, b: Box) -> float:
    """intersection / area(smaller box) — 1.0 means the smaller box is
    entirely swallowed by the larger one, regardless of how much bigger the
    larger box is (unlike IoU, which penalizes a big size mismatch)."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter_area = inter_w * inter_h
    smaller_area = min(box_area(a), box_area(b))
    return inter_area / smaller_area if smaller_area > 0 else 0.0


def main():
    all_rows: List[Tuple[str, str, str, float, float]] = []
    for case_name, boxes_by_label in KNOWN_CASES.items():
        for (label_a, box_a), (label_b, box_b) in combinations(boxes_by_label.items(), 2):
            iou = compute_iou(box_a, box_b)
            containment = containment_ratio(box_a, box_b)
            all_rows.append((case_name, label_a, label_b, iou, containment))

    print(f"{'case':<38} {'pair':<45} {'iou':>6} {'containment':>12}")
    print("-" * 103)
    for case_name, label_a, label_b, iou, containment in all_rows:
        pair = f"{label_a} / {label_b}"
        print(f"{case_name:<38} {pair:<45} {iou:>6.3f} {containment:>12.3f}")

    print()
    print(f"Hypothesis check (containment >= {CONTAINMENT_THRESHOLD}, "
          f"iou < NMS default {NMS_DEFAULT_IOU}):")
    matched_cases = set()
    for case_name, label_a, label_b, iou, containment in all_rows:
        if containment >= CONTAINMENT_THRESHOLD and iou < NMS_DEFAULT_IOU:
            matched_cases.add(case_name)
            print(f"  MATCH   {case_name}: {label_a}/{label_b} "
                  f"(containment={containment:.3f}, iou={iou:.3f})")

    print()
    if matched_cases == set(KNOWN_CASES):
        print(
            "All 3 cases show high containment with IoU below the model's NMS iou "
            f"threshold ({NMS_DEFAULT_IOU}) -> hypothesis confirmed. Lowering `iou` in "
            "detect_1a's model.predict() would have to drop well below these IoU values "
            "to catch them, which would over-suppress legitimately adjacent, non-duplicate "
            "products elsewhere on the shelf. The correct fix is a dedicated containment "
            "filter (alongside box_filter.py's filter_anomalous_boxes): drop any box that "
            "another box (not itself) contains almost entirely."
        )
    else:
        missing = set(KNOWN_CASES) - matched_cases
        print(f"Hypothesis NOT confirmed for: {sorted(missing)} — re-examine before "
              "committing to the containment-filter fix over an iou-param change.")


if __name__ == "__main__":
    main()
