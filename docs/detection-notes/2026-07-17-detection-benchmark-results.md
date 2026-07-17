# Detection Benchmark Results — 1b vs 1c

**Date run:** 2026-07-17
**Subset size:** 50 images (streamed from `Voxel51/sku110k_test`; see `docs/detection-notes/sku110k-schema.md`)

## Results

| Model | Precision | Recall | Avg inference time/image | Passes threshold (recall >= 0.45)? |
|---|---|---|---|---|
| 1b (foduucom/product-detection-in-shelf-yolov8) | 0.723 | 0.174 | 0.15s | **FAIL** |
| 1c (IDEA-Research/grounding-dino-tiny) | 0.718 | 0.093 | 2.34s | **FAIL** |

Raw counts: 1b tp=1227 fp=469 fn=5823. 1c tp=658 fp=258 fn=6392. Full data in
`data/benchmark_results/results.json` (gitignored — regenerate with
`python3 -m src.detection.benchmark.report --n 50`).

Metrics are simplified precision/recall/F1 at a fixed IoU=0.5 (greedy matching), **not**
COCO-style interpolated AP — see `src/detection/benchmark/metrics.py`.

## Decision

**Fallback to 1a: fine-tune YOLO (nano) on SKU-110K**, per the decision rule in
`docs/superpowers/specs/2026-07-17-detection-benchmark-design.md` ("nếu cả 1b và 1c đều
không đạt ngưỡng, quay lại kế hoạch gốc — tự fine-tune YOLO nano trên SKU-110K").

Both candidates failed the recall >= 0.45 bar by a wide margin — 1b reached 0.174 and 1c
reached 0.093, both far below the pass threshold and well below the 1b model card's
self-reported (not independently verified) mAP@0.5(box)=0.910. Notably, **precision was
similar and reasonably high for both models (~0.72)** — when either model does predict a
box, it usually lands on a real object. The failure mode is under-detection: both models
miss the large majority of objects on these dense, tightly-packed shelf images (SKU-110K
averages ~121–150 objects per image in this sample), not false positives or a
coordinate/metrics bug.

This was visually confirmed (Task 7, `data/benchmark_results/sample_overlays/`):
ground-truth (green) boxes align tightly with real product boundaries in every image
checked, ruling out a parsing bug as the cause of the low recall. 1b's predicted boxes
(red) covered only a visible fraction of the shelf's products. 1c additionally showed a
recurring degenerate failure mode — on some images it returns one box spanning almost the
entire shelf instead of per-product boxes, even after lowering `box_threshold` from the
plan's suggested 0.3 to 0.15 (see `run_zeroshot_1c.py`'s docstring for the threshold
experiment). Both are consistent with these being general-purpose/short-shelf-trained
models applied zero-shot to a much denser scene than they were tuned for, rather than a
bug in this benchmark harness.

1c was also ~15x slower per image than 1b (2.34s vs 0.15s) with worse recall, so there is
no speed/accuracy trade-off argument for preferring it even as a stopgap.

## Next spec

**Phase 1 continuation (1a fine-tuning)** — write the next spec for fine-tuning YOLO nano
on SKU-110K, per the "Bước tiếp theo" section of the design spec. Phase 2 (Classification)
should wait until the detection box-output format is settled by that fine-tuning work.
