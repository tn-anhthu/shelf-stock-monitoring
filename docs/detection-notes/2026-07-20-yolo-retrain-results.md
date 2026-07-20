# YOLO Retrain (1a) — Checkpoint Regeneration Results

**Date run:** 2026-07-20
**Reason for retrain:** the original fine-tuned checkpoint from 2026-07-17
(`runs/train_1a/full/weights/best.pt`, see `2026-07-17-yolo-finetune-results.md`) was
never persisted on disk — confirmed missing when starting Task 1 of
`docs/superpowers/plans/2026-07-20-shelfsense-foundation.md`. Retrained from scratch
using the same command/config as the original run.

## Environment issue hit and fixed

First attempt crashed immediately: `ultralytics==8.0.43` (the version pinned in
`.venv-benchmark`, used for Phase 1's detector comparison) is incompatible with
MPS + newer torch on this run (`Cannot convert MPS Tensor to float64`). Root cause:
`.venv-train` — the venv meant for training, with `ultralytics>=8.3` per
`requirements-train.txt` — was missing from the machine (never persisted, same as
the checkpoint itself). Recreated `.venv-train` with `ultralytics 8.4.102`; training
then ran cleanly with no crash.

## Results

**Training:** 800 images / 10 epochs (`harryrobert/SKU-110k-reformat` train split),
100 validation images — same config as the original run. Took ~16 minutes this time
(vs. ~39 minutes originally; both are well within the training-scale budget decided
in the original run's notes).

**Eval** (same 50-image `Voxel51/sku110k_test` set, IoU 0.5, via
`src.detection.train.evaluate`):

| Metric | This run (2026-07-20) | Original run (2026-07-17) |
|---|---|---|
| Precision | 0.745 | 0.745 |
| Recall | **0.782** | 0.782 |
| tp / fp / fn | 5513 / 1891 / 1537 | 5513 / 1891 / 1537 |
| Passes threshold (recall ≥ 0.6)? | **PASS** | PASS |

Numbers match the original run exactly — the retrain reproduces the original
result, not a different model. Weights saved at
`runs/detect/runs/train_1a/full/weights/best.pt` (the `runs/detect/` nesting is a
known ultralytics quirk, already noted in the original run's docs — not new).
`runs/` is gitignored, so nothing from training is committed; this doc and
`data/benchmark_results/results_1a.json` are the durable record.

## Reading the training plots (precision-confidence curve, confusion matrix)

Two auto-generated plots looked concerning at first glance and were checked against
the raw tp/fp/fn counts above before concluding they're not bugs:

**Precision-confidence curve — dip around confidence 0.9–0.95, then a spike back up
near 1.0.** This is small-sample tail noise, not a modeling problem. The curve is
computed on only 100 validation images; very few predicted boxes reach confidence
above ~0.85, so in that narrow region the precision estimate is based on a handful
of boxes — one wrong box swings it sharply. This region is **not** the pipeline's
real operating point: `detect_1a` uses `conf=0.25` by default, which sits on the
stable part of the curve (~0.75–0.8 precision), consistent with the measured
precision=0.745 above.

**Confusion matrix (normalized) — cell (Predicted=object, True=background) = 1.00.**
This looks alarming read as "100% of background got misclassified as object," but
it's a normalization artifact specific to detection confusion matrices: there is no
"true negative" (true background) case to count in single-class detection, so the
background *column* has exactly one nonzero cell — the 1891 false positives — and
normalizing a column against itself always yields 1.00, regardless of whether fp is
1891 or 1. It carries no information beyond what's already known from the raw counts.
The other diagonal, (Predicted=object, True=object) = 0.80, does carry real signal
and is consistent with recall=0.782 measured independently by `evaluate.py`.

**Conclusion:** both plots are standard ultralytics rendering artifacts for a
single-class, moderate-recall detector on a small eval set — not evidence of a
bug or data leakage. The checkpoint is validated and ready for the pipeline
(`src/pipeline/scan.py`) built in Tasks 2–10 of the foundation plan.
