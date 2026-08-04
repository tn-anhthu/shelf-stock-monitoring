"""Measure the real IoU distribution between raw-YOLO box pairs across the demo
shelf photos, to check whether tightening model.predict()'s NMS iou parameter
(currently the Ultralytics default, 0.7 -- never set explicitly in
src/detection/train/run_trained_1a.py::detect_1a) would catch same-physical-
product duplicate detections without also suppressing genuinely distinct
adjacent products.

Only reports pairs whose IoU falls in --iou-min..--iou-max (default 0.3-0.8,
spanning the zone a stricter NMS threshold would newly start suppressing) --
pairs with near-zero IoU (touching-but-not-overlapping fragments, handled by
merge_adjacent_fragments) or very high IoU (already suppressed by the current
0.7 default) aren't the question here.

Usage:
    python3 scripts/debug_iou_distribution.py --image path/to/shelf.jpg \
        --weights runs/detect/runs/train_1a/n_2000/weights/best.pt \
        --iou-min 0.3 --iou-max 0.8
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pillow_heif
pillow_heif.register_heif_opener()
from PIL import Image

from src.detection.benchmark.metrics import Box, compute_iou, containment_ratio
from src.detection.train.run_trained_1a import detect_1a, load_model_1a


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--weights", type=str, required=True)
    parser.add_argument("--iou-min", type=float, default=0.3)
    parser.add_argument("--iou-max", type=float, default=0.8)
    args = parser.parse_args()

    yolo_model = load_model_1a(Path(args.weights))
    shelf_image = Image.open(args.image)
    boxes = detect_1a(yolo_model, shelf_image)
    print(f"{len(boxes)} raw box(es) detected in {args.image}\n")

    pairs = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            iou = compute_iou(a, b)
            if args.iou_min <= iou <= args.iou_max:
                cont = containment_ratio(a, b)
                pairs.append((iou, cont, a, b))

    pairs.sort(key=lambda p: p[0])
    print(f"{len(pairs)} pair(s) with IoU in [{args.iou_min}, {args.iou_max}]:")
    for iou, cont, a, b in pairs:
        print(f"  IoU={iou:.3f}  containment={cont:.3f}  "
              f"{tuple(round(v, 1) for v in a)}  <->  {tuple(round(v, 1) for v in b)}")


if __name__ == "__main__":
    main()
