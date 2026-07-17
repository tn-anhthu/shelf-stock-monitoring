"""Run the CLIP vs SigLIP2 classification benchmark on an RPC subset and report results.

Usage: python3 -m src.classification.benchmark.report --n-test-images 15
"""
import os

# Must be set before torch is imported by any of this module's imports below —
# torch reads this once at its own import time, not per-op. SigLIP2 is newer
# and some ops may not have native MPS kernels, so this lets them fall back
# to CPU instead of hard-crashing. See src/detection/benchmark/report.py for
# the same pattern.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import argparse
import json
import time
from functools import partial
from pathlib import Path

from src.classification.benchmark.catalog import build_catalog
from src.classification.benchmark.data import build_catalog_source, load_test_crops
from src.classification.benchmark.embed_clip import embed_image_clip, load_model_clip
from src.classification.benchmark.embed_siglip2 import embed_image_siglip2, load_model_siglip2
from src.classification.benchmark.metrics import compute_topk_accuracy
from src.classification.benchmark.retrieve import rank_categories

RESULTS_PATH = Path("data/classification_results/results.json")


def run_one_model(model_name: str, embed_fn, test_crops, catalog_source) -> dict:
    catalog = build_catalog(catalog_source, embed_fn)
    catalog_categories = {c for c, _ in catalog}

    rankings = []
    true_categories = []
    skipped = 0
    start = time.time()
    for crop in test_crops:
        if crop["category"] not in catalog_categories:
            skipped += 1
            continue
        query_embedding = embed_fn(crop["image"])
        rankings.append(rank_categories(query_embedding, catalog))
        true_categories.append(crop["category"])
    elapsed = time.time() - start

    n_evaluated = len(true_categories)
    return {
        "model_name": model_name,
        "n_evaluated": n_evaluated,
        "n_skipped_no_catalog_entry": skipped,
        "top1_accuracy": compute_topk_accuracy(rankings, true_categories, k=1),
        "top5_accuracy": compute_topk_accuracy(rankings, true_categories, k=5),
        "avg_inference_seconds": elapsed / n_evaluated if n_evaluated else 0.0,
    }


def run_benchmark(n_test_images: int = 15) -> dict:
    test_crops = load_test_crops(n_images=n_test_images)
    needed_categories = {c["category"] for c in test_crops}
    catalog_source = build_catalog_source(needed_categories, max_per_category=3)

    clip_model, clip_processor = load_model_clip()
    clip_embed_fn = partial(embed_image_clip, clip_model, clip_processor)
    clip_result = run_one_model("clip", clip_embed_fn, test_crops, catalog_source)

    siglip2_model, siglip2_processor = load_model_siglip2()
    siglip2_embed_fn = partial(embed_image_siglip2, siglip2_model, siglip2_processor)
    siglip2_result = run_one_model("siglip2", siglip2_embed_fn, test_crops, catalog_source)

    return {
        "n_test_images": n_test_images,
        "n_test_crops": len(test_crops),
        "n_distinct_categories_needed": len(needed_categories),
        "n_catalog_images": len(catalog_source),
        "clip": clip_result,
        "siglip2": siglip2_result,
    }


def print_summary(report: dict) -> None:
    print(f"\nClassification benchmark on {report['n_test_crops']} RPC test crops "
          f"({report['n_distinct_categories_needed']} distinct categories, "
          f"{report['n_catalog_images']} catalog images)\n")
    for key in ("clip", "siglip2"):
        r = report[key]
        print(f"[{r['model_name']}] top1={r['top1_accuracy']:.3f}  top5={r['top5_accuracy']:.3f}  "
              f"evaluated={r['n_evaluated']} skipped={r['n_skipped_no_catalog_entry']}  "
              f"avg time/crop (embed+rank): {r['avg_inference_seconds']:.3f}s/crop")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-test-images", type=int, default=15)
    args = parser.parse_args()

    report = run_benchmark(n_test_images=args.n_test_images)
    print_summary(report)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved full results to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
