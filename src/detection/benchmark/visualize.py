"""Draw predicted vs ground-truth boxes on sample images for manual sanity-checking.

Usage: python3 -m src.detection.benchmark.visualize --n 5

Run this on the M4 MacBook Pro (needs MPS + network access), after report.py has
been run at least once so you trust the model wrappers work.
"""
import os

# Must be set before torch is imported by any of this module's imports below —
# see report.py's identical comment / run_zeroshot_1c.py's docstring for why.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import argparse
from pathlib import Path

from PIL import ImageDraw

from src.detection.benchmark.data import load_sku110k_subset
from src.detection.benchmark.run_checkpoint_1b import detect_1b, load_model_1b
from src.detection.benchmark.run_zeroshot_1c import detect_1c, load_model_1c

OUTPUT_DIR = Path("data/benchmark_results/sample_overlays")


def draw_overlay(image, gt_boxes, pred_boxes, out_path: Path) -> None:
    canvas = image.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas)
    for box in gt_boxes:
        draw.rectangle(box, outline="green", width=2)
    for box in pred_boxes:
        draw.rectangle(box, outline="red", width=2)
    canvas.save(out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5)
    args = parser.parse_args()

    subset = load_sku110k_subset(n=args.n)
    model_1b = load_model_1b()
    processor_1c, model_1c = load_model_1c()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for i, item in enumerate(subset):
        image = item["image"]
        gt_boxes = item["gt_boxes"]

        preds_1b = detect_1b(model_1b, image)
        draw_overlay(image, gt_boxes, preds_1b, OUTPUT_DIR / f"image_{i}_1b.png")

        preds_1c = detect_1c(processor_1c, model_1c, image)
        draw_overlay(image, gt_boxes, preds_1c, OUTPUT_DIR / f"image_{i}_1c.png")

    print(f"Saved {args.n * 2} overlay images to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
