"""Run the 1b vs 1c detection benchmark on a SKU-110K subset and report results.

Usage: python3 -m src.detection.benchmark.report --n 50

Run this on the M4 MacBook Pro (needs MPS + real network access to download
model weights and stream the SKU-110K subset) — not in a cloud sandbox.
"""
import os

# Must be set before torch is imported by any of this module's imports below —
# torch reads this once at its own import time, not per-op. See
# run_zeroshot_1c.py's docstring for why 1c needs this (aten::_cummax_helper
# has no MPS kernel). run_checkpoint_1b is imported first here and pulls in
# torch transitively, so setting this later (e.g. only inside run_zeroshot_1c)
# would be too late.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import argparse
import json
import time
from pathlib import Path

from src.detection.benchmark.data import load_sku110k_subset
from src.detection.benchmark.metrics import aggregate_precision_recall, compute_precision_recall
from src.detection.benchmark.run_checkpoint_1b import detect_1b, load_model_1b
from src.detection.benchmark.run_zeroshot_1c import detect_1c, load_model_1c

RESULTS_PATH = Path("data/benchmark_results/results.json")
RECALL_PASS_THRESHOLD = 0.45  # per docs/superpowers/specs/2026-07-17-detection-benchmark-design.md


def run_benchmark(n: int = 50) -> dict:
    subset = load_sku110k_subset(n=n)

    model_1b = load_model_1b()
    processor_1c, model_1c = load_model_1c()

    per_image_1b = []
    per_image_1c = []
    time_1b_total = 0.0
    time_1c_total = 0.0

    for item in subset:
        image = item["image"]
        gt_boxes = item["gt_boxes"]

        start = time.time()
        preds_1b = detect_1b(model_1b, image)
        time_1b_total += time.time() - start
        per_image_1b.append(compute_precision_recall(preds_1b, gt_boxes, iou_threshold=0.5))

        start = time.time()
        preds_1c = detect_1c(processor_1c, model_1c, image)
        time_1c_total += time.time() - start
        per_image_1c.append(compute_precision_recall(preds_1c, gt_boxes, iou_threshold=0.5))

    result_1b = aggregate_precision_recall(per_image_1b)
    result_1c = aggregate_precision_recall(per_image_1c)

    report = {
        "n_images": n,
        "recall_pass_threshold": RECALL_PASS_THRESHOLD,
        "1b": {
            "model_id": "foduucom/product-detection-in-shelf-yolov8",
            **result_1b,
            "avg_inference_seconds": time_1b_total / n,
            "passes_threshold": result_1b["recall"] >= RECALL_PASS_THRESHOLD,
        },
        "1c": {
            "model_id": "IDEA-Research/grounding-dino-tiny",
            **result_1c,
            "avg_inference_seconds": time_1c_total / n,
            "passes_threshold": result_1c["recall"] >= RECALL_PASS_THRESHOLD,
        },
    }
    return report


def print_summary(report: dict) -> None:
    print(f"\nBenchmark on {report['n_images']} SKU-110K images "
          f"(pass threshold: recall >= {report['recall_pass_threshold']})\n")
    for key in ("1b", "1c"):
        r = report[key]
        status = "PASS" if r["passes_threshold"] else "FAIL"
        print(f"[{key}] {r['model_id']}")
        print(f"  precision={r['precision']:.3f}  recall={r['recall']:.3f}  "
              f"tp={r['tp']} fp={r['fp']} fn={r['fn']}")
        print(f"  avg inference time: {r['avg_inference_seconds']:.2f}s/image  -> {status}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=50)
    args = parser.parse_args()

    report = run_benchmark(n=args.n)
    print_summary(report)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved full results to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
