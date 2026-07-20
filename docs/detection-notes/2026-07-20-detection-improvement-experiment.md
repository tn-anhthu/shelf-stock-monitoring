# Detection Improvement Experiment — n_train 800→2000, model variant

**Date run:** 2026-07-20
**Motivation:** baseline recall (0.782, see `2026-07-20-yolo-retrain-results.md`) already
passes the 0.6 threshold, but was worth testing whether cheap levers could push it toward
0.8 without derailing the 5-week schedule.

## Experiment 1: YOLOv8s (small), 2000 train images, 15 epochs — abandoned

Attempted increasing both training data (800→2000) and model capacity (nano→small)
simultaneously. Training exhibited severe, erratic per-iteration slowdown (3.7s/it to
60s/it, wildly inconsistent) starting from epoch 1. Root cause: memory usage reported by
the training loop (`GPU_mem` column) reached 15-17G, i.e. near the machine's full 16GB
unified RAM (MacBook Pro M4) — causing swap/thrashing rather than a proportional
compute slowdown. At the observed rate, 15 epochs would have taken 15-20+ hours.
**Abandoned** — not a viable configuration on this hardware without further tuning
(e.g. smaller batch size), which wasn't pursued given the schedule.

## Experiment 2: YOLOv8n (nano), 2000 train images, 10 epochs — adopted

Same architecture as the validated baseline, only the training set size increased
(800→2000 images, same 100-image validation split, same 10 epochs). Training completed
cleanly: 3443.4s (~57 min total, 344.3s/epoch), no memory pressure observed (stable
per-iteration speed throughout, unlike Experiment 1).

**Eval** (same 50-image `Voxel51/sku110k_test` set, IoU 0.5, via
`src.detection.train.evaluate` — same methodology as the baseline, so directly
comparable):

| Metric | Baseline (800 train, nano) | This run (2000 train, nano) | Change |
|---|---|---|---|
| Precision | 0.745 | 0.758 | +0.013 |
| Recall | 0.782 | **0.818** | **+0.036** |
| tp / fp / fn | 5513 / 1891 / 1537 | 5765 / 1837 / 1285 | tp↑, fp↓, fn↓ |

Both precision and recall improved with no trade-off — more training data alone was
sufficient, no need for a larger model. Recall now exceeds 0.8.

Note: ultralytics' own training-time validation metrics for this run (mAP50=0.835,
mAP50-95=0.49, precision=0.868, recall=0.778, computed on the 100-image training-time
validation split) are **not** directly comparable to the table above — different eval
set, different metric definitions. The table above uses only the `evaluate.py`-based
numbers, matching the baseline's methodology, to avoid an apples-to-oranges comparison.

## Decision

**Adopt `runs/train_1a/n_2000/weights/best.pt` as the checkpoint for pipeline
integration** (Week 3-4 UI wiring), replacing `runs/train_1a/full/weights/best.pt`.
No code changes needed elsewhere — `src/pipeline/scan.py` takes `detect_fn` as an
injected dependency and was never hard-coded to a specific checkpoint path.

`data/detection/train/data.py` was also updated in this session to skip
re-downloading materialized training images that already exist on disk, so future
experiments on the same `n_train`/`n_val` sizes won't repeat the ~20-30 min network
download step.
