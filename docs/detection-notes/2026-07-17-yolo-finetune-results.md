# YOLO Fine-tune (1a) Results

**Date run:** 2026-07-17
**Training data:** 800 images / 10 epochs (`harryrobert/SKU-110k-reformat` `train` split), 100 images from the `validation` split for in-training monitoring. Reduced from the original plan's proposal of 8219 images / 30 epochs — see decision below.
**Eval set:** same 50 images as 1b/1c (`Voxel51/sku110k_test`), loaded via the existing `src/detection/benchmark/data.py::load_sku110k_subset` — never touched during training.

## Results

| Model | Precision | Recall | Passes threshold (recall >= 0.6)? |
|---|---|---|---|
| 1a (this sprint's fine-tune) | 0.745 | **0.782** | **PASS** |
| 1b (foduucom/product-detection-in-shelf-yolov8, for reference) | 0.723 | 0.174 | FAIL |
| 1c (IDEA-Research/grounding-dino-tiny, for reference) | 0.718 | 0.093 | FAIL |

Raw counts: tp=5513 fp=1891 fn=1537. Full data in `data/benchmark_results/results_1a.json`
(gitignored — regenerate with
`python3 -m src.detection.train.evaluate --weights runs/detect/runs/train_1a/full/weights/best.pt`).

## Training-scale decision

The plan's Task 5 called for estimating full-scale training (8219 images, 30 epochs) from
the pilot's per-epoch timing and stopping if it exceeded ~4h. The pilot run's own timing
was contaminated by an operator error (a duplicate `resume=True` process briefly trained
against the same output directory as the original, undying pilot process — see the
`feat: add YOLO training script...` commit) and, separately, by the MacBook sleeping during
transit. Estimates from that contaminated data ranged 65–195h, far over budget.

Rather than trust either number, a fresh, single-process, uncontaminated timing was taken
from epoch 1 of the next run (0.347s/epoch/image) — this pointed to ~24h for the original
8219/30 proposal (still over budget, but ~3-8x faster than the pilot data suggested,
confirming the contamination was the dominant cause of the earlier bad estimates, not an
inherent pipeline slowness).

Per the user's direction, ran a **reduced scope** (800 train / 100 val images, 10 epochs)
instead of the full proposal — comfortably within budget. Actual: **10 epochs completed in
0.651h** (39 min), confirming the clean estimate.

## Decision

**1a passes** (recall 0.782 >= 0.6 threshold), by a wide margin, using only ~10% of the
available training images and a third of the originally proposed epoch count. Both
precision and recall are now far ahead of 1b/1c — recall improved by roughly 4.5x over 1b's
0.174, at a comparable precision (0.745 vs 0.723).

Per the decision rule in `docs/superpowers/specs/2026-07-17-detection-yolo-finetune-design.md`,
**Phase 1 (Detection) is done.**

## Improvement attempt (not adopted)

After passing, tried one further improvement: both the pilot and `full` runs had
`close_mosaic=10` (ultralytics' default) with total epochs <= 10, which disables mosaic
augmentation for almost the entire run (confirmed via `args.yaml` and the "Closing
dataloader mosaic" log line appearing at start). `train.py` gained a `--close-mosaic` CLI
arg (default unchanged at 10, so no behavior change unless passed) to allow re-enabling it.

A follow-up run (1500 train / 150 val images, 15 epochs, `--close-mosaic 5` so mosaic is
active for epochs 1-10) was killed partway through epoch 1: per-iteration time grew from
~3s/it to ~34s/it over the epoch, with `RuntimeWarning`s (divide-by-zero/overflow in
`ultralytics/data/augment.py`'s affine transform) appearing partway through. Root cause:
the MacBook has only 16GB **unified** memory (shared between CPU and GPU on Apple
Silicon) — mosaic combines 4 SKU-110K images (each already very dense, ~1000+ instances)
into one batch, and GPU_mem climbed toward the 16GB ceiling, triggering swap. The
progressive slowdown within a single epoch (rather than a flat, constant per-batch cost)
is the signature of swapping, not of mosaic being inherently expensive. No checkpoint was
produced by the killed run (epoch 1 never completed), so nothing was lost by abandoning it.

**Decision: not pursued further** — 1a already passes by a wide margin (0.782 vs 0.6), and
squeezing out more accuracy isn't worth the cost/risk here. If a future need does want to
try mosaic again, use a smaller `--batch` (currently defaults to ultralytics' 16) to keep
memory under the 16GB ceiling, rather than assuming more epochs/data alone will help.

## Next spec

Phase 2 (Classification) can now proceed, using this fine-tuned YOLO nano
(`runs/detect/runs/train_1a/full/weights/best.pt`) as the detection stage. Note the
model was trained on only ~10% of the available `harryrobert/SKU-110k-reformat` train
split — if Phase 2 or later evaluation surfaces detection quality issues on other imagery,
training on more of the remaining ~7400 images (confirmed cheap, ~0.65h per 800/10-epoch
increment, **as long as mosaic stays off / `close_mosaic >= epochs`**) is a low-cost first
thing to try before other fixes. A cheaper, zero-retraining lever worth trying first:
lowering `detect_1a`'s `conf` threshold below its 0.25 default, since these are dense
scenes with many small, low-confidence true objects.
