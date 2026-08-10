"""Evaluate the fine-tuned 1a model (any era/checkpoint passed via --weights) on
the same 50-image SKU-110K eval set used for 1b/1c, for a direct, apples-to-apples
comparison.

Usage: python3 -m src.detection.train.evaluate --weights sku110k_yolo26n_results/weights/best.pt

WARNING: RESULTS_PATH below (data/benchmark_results/results_1a.json) is a single
fixed, gitignored file, not versioned per checkpoint — whatever --weights you pass
is what ends up in it, with no prompt and no backup. The historical YOLOv8n/n_2000
baseline (precision=0.758, recall=0.818 — cited in docs/detection-notes/detection-log.md
and docs/reports/model-research-summary.md) has already been preserved separately as
data/benchmark_results/results_1a_n2000.json for exactly this reason. If
results_1a.json holds something you want to keep, copy/rename it (same pattern)
before re-running this script with different weights.
"""
import argparse
import json
from pathlib import Path

from src.detection.benchmark.data import load_sku110k_subset
from src.detection.benchmark.metrics import aggregate_precision_recall, compute_precision_recall
from src.detection.train.run_trained_1a import detect_1a, load_model_1a

RESULTS_PATH = Path("data/benchmark_results/results_1a.json")
RECALL_PASS_THRESHOLD = 0.6  # per design decision (see docs/detection-notes/2026-07-17-yolo-finetune-results.md)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=str, required=True)
    parser.add_argument("--n", type=int, default=50)
    args = parser.parse_args()

    subset = load_sku110k_subset(n=args.n)
    model = load_model_1a(Path(args.weights))

    per_image = []
    for item in subset:
        preds = detect_1a(model, item["image"])
        per_image.append(compute_precision_recall(preds, item["gt_boxes"], iou_threshold=0.5))

    result = aggregate_precision_recall(per_image)
    passes = result["recall"] >= RECALL_PASS_THRESHOLD
    report = {
        "n_images": args.n,
        "weights": args.weights,
        "recall_pass_threshold": RECALL_PASS_THRESHOLD,
        **result,
        "passes_threshold": passes,
    }
    print(f"\n1a eval on {args.n} images (pass threshold: recall >= {RECALL_PASS_THRESHOLD})")
    print(f"  precision={result['precision']:.3f}  recall={result['recall']:.3f}  "
          f"tp={result['tp']} fp={result['fp']} fn={result['fn']}")
    print(f"  -> {'PASS' if passes else 'FAIL'}")

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
