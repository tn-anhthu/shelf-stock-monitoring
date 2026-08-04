"""Print merge_adjacent_fragments's exact per-pair condition values (x_overlap_ratio,
y_gap, aspect_ratio vs. the anomaly cutoff) for every raw-YOLO box pair inside a
region of interest, to see WHY specific fragment pairs that look like "one product
split top/bottom" to a human fail to merge -- which of the three gates
(x_overlap_threshold=0.8, y_gap_tolerance=5.0, aspect_ratio_anomaly_ratio=0.6)
rejects them, rather than guessing from coordinates alone.

Reimplements the same three helper checks src/pipeline/box_merge.py uses
internally (not imported, since that module only exposes the final merged list,
not per-pair intermediate values) -- kept numerically identical on purpose so
this script's PASS/FAIL calls match what a real run does.

Usage:
    python3 scripts/debug_merge_conditions.py --image path/to/shelf.jpg \
        --weights runs/detect/runs/train_1a/n_2000/weights/best.pt \
        --region 400,2800,1150,3400
"""
import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pillow_heif
pillow_heif.register_heif_opener()
from PIL import Image

from src.detection.benchmark.metrics import Box
from src.detection.train.run_trained_1a import detect_1a, load_model_1a

X_OVERLAP_THRESHOLD = 0.8
Y_GAP_TOLERANCE = 5.0
ASPECT_RATIO_ANOMALY_RATIO = 0.6


def x_overlap_ratio(a: Box, b: Box) -> float:
    ax1, _, ax2, _ = a
    bx1, _, bx2, _ = b
    inter = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    narrower = min(ax2 - ax1, bx2 - bx1)
    return inter / narrower if narrower > 0 else 0.0


def y_gap(a: Box, b: Box) -> float:
    _, ay1, _, ay2 = a
    _, by1, _, by2 = b
    if ay1 <= by1:
        return by1 - ay2
    return ay1 - by2


def aspect_ratio(box: Box) -> float:
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    return h / w if w > 0 else float("inf")


def box_overlaps_region(box: Box, region: Box) -> bool:
    x1, y1, x2, y2 = box
    rx1, ry1, rx2, ry2 = region
    return not (x2 <= rx1 or x1 >= rx2 or y2 <= ry1 or y1 >= ry2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--weights", type=str, required=True)
    parser.add_argument("--region", type=str, default=None, help="x1,y1,x2,y2; omit to scan the whole image")
    parser.add_argument(
        "--only-close-pairs", action="store_true",
        help="Only print pairs with some x-overlap AND |y_gap| < 60 (candidate "
             "same-product fragments) instead of every pair in the region -- "
             "the full O(n^2) listing gets noisy fast for a busy shelf row.",
    )
    parser.add_argument(
        "--x-aspect-only", action="store_true",
        help="Only print pairs passing x_overlap_ratio >= 0.8 AND the aspect-ratio "
             "anomaly gate -- ignoring y_gap entirely as a filter (still printed, "
             "just not used to include/exclude) -- to see the y_gap distribution "
             "across every adjacent-looking pair regardless of gap size.",
    )
    args = parser.parse_args()

    yolo_model = load_model_1a(Path(args.weights))
    shelf_image = Image.open(args.image)
    boxes = detect_1a(yolo_model, shelf_image)

    region: Box = (
        tuple(float(v) for v in args.region.split(","))
        if args.region else (0.0, 0.0, float(shelf_image.width), float(shelf_image.height))
    )

    median_aspect = statistics.median(aspect_ratio(b) for b in boxes)
    anomaly_cutoff = ASPECT_RATIO_ANOMALY_RATIO * median_aspect
    print(f"Median aspect ratio across all {len(boxes)} raw boxes: {median_aspect:.3f}")
    print(f"Anomaly cutoff (0.6 * median): {anomaly_cutoff:.3f}\n")

    in_region = [b for b in boxes if box_overlaps_region(b, region)]
    in_region.sort(key=lambda b: (b[0], b[1]))
    print(f"{len(in_region)} raw box(es) in region {region}:")
    for b in in_region:
        w, h = b[2] - b[0], b[3] - b[1]
        ar = aspect_ratio(b)
        flag = " [ANOMALOUS/flat]" if ar < anomaly_cutoff else ""
        print(f"  {tuple(round(v, 1) for v in b)}  w={w:.0f} h={h:.0f} aspect={ar:.3f}{flag}")

    print(f"\nPairwise merge-condition trace ({len(in_region)} boxes, "
          f"{len(in_region) * (len(in_region) - 1) // 2} pairs):")
    for i in range(len(in_region)):
        for j in range(i + 1, len(in_region)):
            a, b = in_region[i], in_region[j]
            xo = x_overlap_ratio(a, b)
            yg = y_gap(a, b)
            ar_a, ar_b = aspect_ratio(a), aspect_ratio(b)

            if args.only_close_pairs and (xo <= 0.0 or abs(yg) >= 60):
                continue

            cond_x = xo >= X_OVERLAP_THRESHOLD
            cond_y = abs(yg) <= Y_GAP_TOLERANCE
            cond_ar = ar_a < anomaly_cutoff or ar_b < anomaly_cutoff
            would_merge = cond_x and cond_y and cond_ar

            if args.x_aspect_only and not (cond_x and cond_ar):
                continue

            print(f"\n  pair: {tuple(round(v, 1) for v in a)}  <->  {tuple(round(v, 1) for v in b)}")
            print(f"    x_overlap_ratio={xo:.3f}  (need >= {X_OVERLAP_THRESHOLD})  {'PASS' if cond_x else 'FAIL'}")
            print(f"    y_gap={yg:.1f}  (need |gap| <= {Y_GAP_TOLERANCE})  {'PASS' if cond_y else 'FAIL'}")
            print(f"    aspect_ratio: a={ar_a:.3f} b={ar_b:.3f}  (need one < {anomaly_cutoff:.3f})  {'PASS' if cond_ar else 'FAIL'}")
            print(f"    => {'WOULD MERGE' if would_merge else 'does not merge'}")


if __name__ == "__main__":
    main()
