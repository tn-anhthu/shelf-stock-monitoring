"""Diagnose candidate "one physical product detected as two boxes" cases: pairs
of YOLO boxes that overlap heavily in x but are stacked/touching in y, which
silently break row-based logic (gap_detection.py, box_filter.py) that assumes
one box per product per row. Only runs YOLO — no fix applied here, measurement
only. For each candidate pair, prints:

  - full coordinates of both boxes
  - IoU (src/detection/benchmark/metrics.py::compute_iou, not reimplemented)
  - x-range overlap ratio (relative to the narrower box's width)
  - aspect ratio (h/w) of each box vs the image's median aspect ratio, to see
    if either fragment is abnormally flat/tall compared to normal products

Usage:
    python3 scripts/debug_box_fragments.py --image path/to/shelf.jpg \
        --weights runs/detect/runs/train_1a/n_2000/weights/best.pt
"""
import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from src.detection.benchmark.metrics import compute_iou
from src.detection.train.run_trained_1a import detect_1a, load_model_1a


def x_overlap_ratio(a, b) -> float:
    ax1, _, ax2, _ = a
    bx1, _, bx2, _ = b
    inter = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    narrower = min(ax2 - ax1, bx2 - bx1)
    return inter / narrower if narrower > 0 else 0.0


def y_gap(a, b) -> float:
    # Vertical gap between the two boxes; negative means they overlap in y.
    _, ay1, _, ay2 = a
    _, by1, _, by2 = b
    if ay1 <= by1:
        return by1 - ay2
    return ay1 - by2


def aspect_ratio(box) -> float:
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    return h / w if w > 0 else float("inf")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--weights", type=str, required=True)
    parser.add_argument("--x-overlap-min", type=float, default=0.85)
    parser.add_argument("--y-gap-min", type=float, default=-5.0)
    parser.add_argument("--y-gap-max", type=float, default=3.0)
    parser.add_argument("--iou-max", type=float, default=0.3,
                         help="Above this, the pair is likely a duplicate/near-identical "
                              "detection rather than two distinct touching fragments.")
    args = parser.parse_args()

    yolo_model = load_model_1a(Path(args.weights))
    shelf_image = Image.open(args.image)
    boxes = detect_1a(yolo_model, shelf_image)
    print(f"YOLO detected {len(boxes)} boxes total")

    median_aspect = statistics.median(aspect_ratio(b) for b in boxes)
    print(f"Median aspect ratio (h/w) across all boxes: {median_aspect:.2f}\n")

    candidates = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            xo = x_overlap_ratio(a, b)
            yg = y_gap(a, b)
            iou = compute_iou(a, b)
            if xo >= args.x_overlap_min and args.y_gap_min <= yg <= args.y_gap_max and iou <= args.iou_max:
                candidates.append((a, b, xo, yg))

    print(f"Found {len(candidates)} candidate split-fragment pair(s) "
          f"(x_overlap_ratio >= {args.x_overlap_min}, "
          f"{args.y_gap_min} <= y_gap <= {args.y_gap_max}, iou <= {args.iou_max}):\n")

    for idx, (a, b, xo, yg) in enumerate(candidates):
        iou = compute_iou(a, b)
        ar_a, ar_b = aspect_ratio(a), aspect_ratio(b)
        print(f"Candidate {idx}:")
        print(f"  box A: {tuple(round(v, 1) for v in a)}  aspect_ratio={ar_a:.2f} (median={median_aspect:.2f})")
        print(f"  box B: {tuple(round(v, 1) for v in b)}  aspect_ratio={ar_b:.2f} (median={median_aspect:.2f})")
        print(f"  IoU={iou:.3f}  x_overlap_ratio={xo:.2f}  y_gap={yg:.1f}")
        print()


if __name__ == "__main__":
    main()
