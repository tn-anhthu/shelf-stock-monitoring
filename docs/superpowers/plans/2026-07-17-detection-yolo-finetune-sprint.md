# Detection YOLO Fine-tune Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fine-tune YOLOv8 nano on SKU-110K (Phase 1a), then evaluate it on the same 50-image set used to benchmark 1b/1c, to decide whether Phase 1 (Detection) is done or needs further work.

**Architecture:** A new, isolated package (`src/detection/train/`) with 4 responsibilities kept in separate files: converting COCO-style boxes to YOLO label format, materializing a YOLO-format dataset on disk from a streamed Hugging Face dataset, running training, and running/evaluating the trained model. Reuses `src/detection/benchmark/metrics.py` and `data.py` unchanged for evaluation, so 1a's numbers are directly comparable to 1b/1c's.

**Tech Stack:** Python 3.10 (same interpreter as the benchmark package, already installed via Homebrew at `/opt/homebrew/bin/python3.10`), PyTorch (`mps` backend), `ultralytics` (current release, **not** the old `8.0.43` pin used by the benchmark package), Hugging Face `datasets`, Pillow, pytest.

## Global Constraints

- Runs on MacBook Pro M4, 16GB RAM — use `device='mps'`, never assume CUDA.
- Separate virtualenv `.venv-train` — do **not** reuse `.venv-benchmark` (that env pins old `ultralytics==8.0.43`/`torch<2.6`/`setuptools<81` solely for loading the 1b checkpoint; none of those constraints apply here, and training needs a current `ultralytics`).
- Training data: `harryrobert/SKU-110k-reformat` on Hugging Face, `train` and `validation` splits **only**. Never use that repo's `test` split — it's not confirmed to be disjoint from `Voxel51/sku110k_test`, which is the eval set, so using it would risk train/eval leakage.
- Eval set: the same first 50 images of `Voxel51/sku110k_test`, loaded via the existing `src/detection/benchmark/data.py::load_sku110k_subset` — do not write a new eval loader.
- Metrics: reuse `src/detection/benchmark/metrics.py` (`compute_precision_recall`, `aggregate_precision_recall`) unchanged — do not reimplement precision/recall.
- Pass bar: **recall ≥ 0.6** on that 50-image eval set (per `docs/superpowers/specs/2026-07-17-detection-yolo-finetune-design.md` — higher than the 0.45 bar used for 1b/1c, because 1a is trained specifically for this task).
- Must run a small pilot (few hundred images, few epochs) and measure real per-epoch timing **before** committing to a full training run. If the timing-based estimate for the full run exceeds ~4 hours on the M4, **stop and report the estimate to the user** rather than silently reducing scope or attempting to switch to Colab — this agent has no way to execute a Colab notebook itself.
- Every claim about dataset schema must be based on values actually observed from the real Hugging Face repo, not assumed — label any unverified number as such.

---

## Task 1: Environment setup

**Files:**
- Create: `requirements-train.txt`
- Create: `src/detection/train/__init__.py`
- Create: `tests/detection/train/__init__.py`
- Test: none (environment verification only)

**Interfaces:**
- Produces: a working Python environment later tasks import from (`src.detection.train.*`). `src/detection/__init__.py` and `tests/detection/__init__.py` already exist from the earlier benchmark sprint — do not recreate them.

- [ ] **Step 1: Create `requirements-train.txt`**

```text
ultralytics>=8.3
datasets>=2.19
pillow>=10.0
pytest>=8.0
requests>=2.31
ijson>=3.2
huggingface_hub>=0.23
```

Note: `requests`/`ijson`/`huggingface_hub` are needed because Task 6/7 import
`src.detection.benchmark.data.load_sku110k_subset` (the existing eval loader) directly —
reusing it means `.venv-train` needs its dependencies too, even though that module lives
in the benchmark package.

- [ ] **Step 2: Create a dedicated virtualenv and install**

```bash
cd inventory-lending-signal
/opt/homebrew/bin/python3.10 -m venv .venv-train
source .venv-train/bin/activate
pip install --upgrade pip
pip install -r requirements-train.txt
```

Expected: install completes with no dependency resolution errors.

- [ ] **Step 3: Verify `mps` backend is available**

```bash
python3 -c "import torch; print(torch.backends.mps.is_available())"
```

Expected: `True` on the M4 MacBook Pro.

- [ ] **Step 4: Create package `__init__.py` files**

`src/detection/train/__init__.py`:
```python
```

`tests/detection/train/__init__.py`:
```python
```

- [ ] **Step 5: Commit**

```bash
git add requirements-train.txt src/detection/train/__init__.py tests/detection/train/__init__.py
git commit -m "chore: set up YOLO fine-tune environment and package skeleton"
```

---

## Task 2: COCO-to-YOLO box conversion — TDD

**Files:**
- Create: `src/detection/train/convert.py`
- Test: `tests/detection/train/test_convert.py`

**Interfaces:**
- Produces:
  - `CocoBox = Tuple[float, float, float, float]` — `(x, y, w, h)` absolute pixel, top-left origin (this is `harryrobert/SKU-110k-reformat`'s `objects.bbox` format).
  - `coco_bbox_to_yolo_line(bbox: CocoBox, image_width: int, image_height: int, class_id: int = 0) -> str` — returns a single YOLO label line `"class cx cy w h"`, all of `cx/cy/w/h` normalized to `[0, 1]`, `cx/cy` the box **center** (not top-left).
  - `coco_objects_to_yolo_lines(bboxes: List[CocoBox], image_width: int, image_height: int, class_id: int = 0) -> List[str]`

- [ ] **Step 1: Write the failing tests**

`tests/detection/train/test_convert.py`:
```python
from src.detection.train.convert import coco_bbox_to_yolo_line, coco_objects_to_yolo_lines


def test_coco_bbox_to_yolo_line_converts_center_and_normalizes():
    # box at (10, 20) size 30x40 in a 100x200 image
    # center = (10+15, 20+20) = (25, 40) -> normalized (0.25, 0.2)
    # size normalized = (30/100, 40/200) = (0.3, 0.2)
    line = coco_bbox_to_yolo_line((10.0, 20.0, 30.0, 40.0), image_width=100, image_height=200)
    assert line == "0 0.250000 0.200000 0.300000 0.200000"


def test_coco_bbox_to_yolo_line_uses_given_class_id():
    line = coco_bbox_to_yolo_line((0.0, 0.0, 10.0, 10.0), image_width=10, image_height=10, class_id=3)
    assert line.startswith("3 ")


def test_coco_objects_to_yolo_lines_handles_multiple_boxes():
    bboxes = [(0.0, 0.0, 10.0, 10.0), (5.0, 5.0, 10.0, 10.0)]
    lines = coco_objects_to_yolo_lines(bboxes, image_width=20, image_height=20)
    assert len(lines) == 2
    assert lines[0] == "0 0.250000 0.250000 0.500000 0.500000"
    assert lines[1] == "0 0.500000 0.500000 0.500000 0.500000"


def test_coco_objects_to_yolo_lines_empty_returns_empty():
    assert coco_objects_to_yolo_lines([], image_width=100, image_height=100) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv-train/bin/activate
pytest tests/detection/train/test_convert.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.detection.train.convert'`

- [ ] **Step 3: Implement `src/detection/train/convert.py`**

```python
"""Convert COCO-style bounding boxes (harryrobert/SKU-110k-reformat's `objects.bbox`
format) to YOLO training label lines.

COCO-style box: (x, y, w, h) in absolute pixel coordinates, top-left origin.
YOLO label line: "class cx cy w h" — cx/cy/w/h normalized to [0, 1] relative to
image size; cx/cy are the box CENTER (not top-left), unlike the COCO input.
"""
from typing import List, Tuple

CocoBox = Tuple[float, float, float, float]


def coco_bbox_to_yolo_line(
    bbox: CocoBox, image_width: int, image_height: int, class_id: int = 0
) -> str:
    x, y, w, h = bbox
    cx = (x + w / 2) / image_width
    cy = (y + h / 2) / image_height
    nw = w / image_width
    nh = h / image_height
    return f"{class_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}"


def coco_objects_to_yolo_lines(
    bboxes: List[CocoBox], image_width: int, image_height: int, class_id: int = 0
) -> List[str]:
    return [coco_bbox_to_yolo_line(b, image_width, image_height, class_id) for b in bboxes]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/detection/train/test_convert.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/detection/train/convert.py tests/detection/train/test_convert.py
git commit -m "feat: add COCO-to-YOLO bbox conversion with tests"
```

---

## Task 3: Materialize a YOLO-format dataset from harryrobert/SKU-110k-reformat

**Files:**
- Create: `docs/detection-notes/sku110k-train-schema.md`
- Create: `src/detection/train/data.py`
- Test: manual smoke test (network-dependent, same reasoning as the benchmark package's `data.py`)

**Interfaces:**
- Consumes: `src.detection.train.convert.coco_objects_to_yolo_lines`
- Produces: `materialize_yolo_dataset(n_train: int, n_val: int, output_dir: Path) -> Path` — streams `n_train`/`n_val` examples from the `train`/`validation` splits, writes `output_dir/images/{train,val}/*.jpg` + `output_dir/labels/{train,val}/*.txt` + `output_dir/data.yaml`, returns the path to `data.yaml`.

- [ ] **Step 1: Record the verified schema**

Real schema of `harryrobert/SKU-110k-reformat` was already confirmed live (2026-07-17) via
`datasets.get_dataset_split_names` and `datasets.load_dataset(..., streaming=True)`. Create
`docs/detection-notes/sku110k-train-schema.md`:

```markdown
# harryrobert/SKU-110k-reformat schema — verified 2026-07-17

Command used: `get_dataset_split_names('harryrobert/SKU-110k-reformat')`, then
`load_dataset('harryrobert/SKU-110k-reformat', split='train', streaming=True)`, first sample.

Splits: `train` (8219 examples), `validation` (588 examples), `test` (2936 examples) — these
counts match the official SKU-110K dataset's known split sizes exactly.

Features:
```
{'image': Image, 'image_id': int64, 'width': int32, 'height': int32,
 'objects': {'id': [int64], 'bbox': [[float32; 4]], 'category': [int64], 'area': [float32]}}
```

`objects.bbox` = list of `(x, y, w, h)` in **absolute pixel coordinates, top-left origin**
(COCO-style — confirmed distinct from `Voxel51/sku110k_test`'s FiftyOne-style *relative*
`[x, y, w, h]` used in the benchmark sprint; do not reuse `parse_fiftyone_detections` for
this data). `category` is a single constant value across all objects — SKU-110K is
class-agnostic ("object"), same as the benchmark sprint's dataset.

**Not used for eval**: this repo's own `test` split (2936 examples, same count as
`Voxel51/sku110k_test`) is not confirmed to contain different images than the eval set —
only `train`/`validation` are used here; eval stays on `Voxel51/sku110k_test` via the
existing `src/detection/benchmark/data.py` loader.
```

- [ ] **Step 2: Implement `src/detection/train/data.py`**

```python
"""Materialize a YOLO-format training dataset on disk from harryrobert/SKU-110k-reformat.

Streams only the first n_train/n_val examples of the train/validation splits via
Hugging Face `datasets` (streaming=True) — never downloads the full dataset. Schema
verified in docs/detection-notes/sku110k-train-schema.md.
"""
from pathlib import Path

from datasets import load_dataset

from src.detection.train.convert import coco_objects_to_yolo_lines

DATASET_ID = "harryrobert/SKU-110k-reformat"


def _write_split(hf_split: str, yolo_split: str, n: int, output_dir: Path) -> int:
    images_dir = output_dir / "images" / yolo_split
    labels_dir = output_dir / "labels" / yolo_split
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    ds = load_dataset(DATASET_ID, split=hf_split, streaming=True)
    count = 0
    for i, example in enumerate(ds):
        if i >= n:
            break
        image = example["image"].convert("RGB")
        width, height = example["width"], example["height"]
        bboxes = [tuple(b) for b in example["objects"]["bbox"]]
        lines = coco_objects_to_yolo_lines(bboxes, width, height)

        image.save(images_dir / f"{i}.jpg")
        (labels_dir / f"{i}.txt").write_text("\n".join(lines))
        count += 1
    return count


def materialize_yolo_dataset(n_train: int, n_val: int, output_dir: Path) -> Path:
    """Stream n_train/n_val examples and write a YOLO-format dataset + data.yaml.

    Returns the path to the written data.yaml.
    """
    output_dir = Path(output_dir)
    _write_split("train", "train", n_train, output_dir)
    _write_split("validation", "val", n_val, output_dir)

    yaml_path = output_dir / "data.yaml"
    yaml_path.write_text(
        f"path: {output_dir.resolve()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "nc: 1\n"
        "names: ['object']\n"
    )
    return yaml_path
```

- [ ] **Step 3: Manually smoke-test on a small n**

```bash
source .venv-train/bin/activate
python3 -c "
from pathlib import Path
from src.detection.train.data import materialize_yolo_dataset

data_yaml = materialize_yolo_dataset(n_train=5, n_val=2, output_dir=Path('data/yolo_train_smoketest'))
print('data.yaml at:', data_yaml)
print(data_yaml.read_text())

import os
train_imgs = os.listdir('data/yolo_train_smoketest/images/train')
train_labels = os.listdir('data/yolo_train_smoketest/labels/train')
print('train images:', len(train_imgs), 'train labels:', len(train_labels))
print(open(f'data/yolo_train_smoketest/labels/train/{train_labels[0]}').read()[:300])
"
```

Expected: 5 images + 5 label files in `images/train`/`labels/train`, 2+2 in the `val`
counterparts, `data.yaml` printed with `nc: 1` and the two split paths, and a label file
containing one or more well-formed `"0 <float> <float> <float> <float>"` lines. Clean up
the smoketest directory afterward: `rm -rf data/yolo_train_smoketest`.

- [ ] **Step 4: Commit**

```bash
git add docs/detection-notes/sku110k-train-schema.md src/detection/train/data.py
git commit -m "feat: add YOLO-format dataset materializer for harryrobert/SKU-110k-reformat"
```

---

## Task 4: Training script + pilot run

**Files:**
- Create: `src/detection/train/train.py`
- Test: manual run (this task's real "test" is the pilot run itself — an integration smoke test of the whole pipeline)

**Interfaces:**
- Consumes: `src.detection.train.data.materialize_yolo_dataset`
- Produces: a CLI (`python3 -m src.detection.train.train ...`) that trains `yolov8n.pt` and saves weights to `runs/train_1a/<name>/weights/best.pt`.

- [ ] **Step 1: Implement `src/detection/train/train.py`**

```python
"""Train YOLOv8 nano on a materialized SKU-110K subset.

Usage: python3 -m src.detection.train.train --n-train 400 --n-val 50 --epochs 8 --name pilot
"""
import argparse
import time
from pathlib import Path

from ultralytics import YOLO

from src.detection.train.data import materialize_yolo_dataset

DATA_DIR = Path("data/yolo_train")
RUNS_DIR = Path("runs/train_1a")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-train", type=int, default=400)
    parser.add_argument("--n-val", type=int, default=50)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", type=str, default="mps")
    parser.add_argument("--name", type=str, default="pilot")
    args = parser.parse_args()

    print(f"Materializing {args.n_train} train / {args.n_val} val images...")
    data_yaml = materialize_yolo_dataset(args.n_train, args.n_val, DATA_DIR)

    model = YOLO("yolov8n.pt")
    start = time.time()
    model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        device=args.device,
        project=str(RUNS_DIR),
        name=args.name,
    )
    elapsed = time.time() - start
    per_epoch = elapsed / args.epochs
    print(f"\nTraining finished in {elapsed:.1f}s ({per_epoch:.1f}s/epoch, "
          f"{per_epoch / args.n_train:.4f}s/epoch/image)")
    best_path = RUNS_DIR / args.name / "weights" / "best.pt"
    print(f"Best weights: {best_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the pilot**

```bash
source .venv-train/bin/activate
python3 -m src.detection.train.train --n-train 400 --n-val 50 --epochs 8 --name pilot
```

Expected: runs to completion without error, prints the elapsed time, per-epoch time, and
per-epoch-per-image time, and reports `runs/train_1a/pilot/weights/best.pt`. This is not
expected to produce a good model (400 images/8 epochs is far too little) — the only thing
this step validates is that data materialization + training + MPS all work end-to-end. If
an MPS "operator not implemented" error occurs (same class of issue hit during the
benchmark sprint with Grounding DINO), record the exact op name and try `device="cpu"`
for the pilot, noting the fallback in the commit message — do not silently paper over it.

- [ ] **Step 3: Commit**

```bash
git add src/detection/train/train.py
git commit -m "feat: add YOLO training script, run pilot to validate the pipeline"
```

---

## Task 5: Decide training scale, run the full training

**Files:**
- Modify: none (uses `src/detection/train/train.py` from Task 4)
- Test: none (this is a decision + a long-running manual execution)

**Interfaces:** none — this task only decides parameters and runs Task 4's script again with them.

- [ ] **Step 1: Compute the time estimate from the pilot**

Using the per-epoch-per-image time `t` printed at the end of Task 4's pilot run, compute:

```
estimated_hours = t * n_train_full * epochs_full / 3600
```

Start from `n_train_full = 8219` (the full `train` split) and `epochs_full = 30` (a
standard fine-tune epoch count for YOLO transfer learning) as the starting proposal.

- [ ] **Step 2: Apply the decision rule**

- If `estimated_hours <= 4`: proceed to Step 3 below with `n_train_full`/`epochs_full` as
  computed (or the full values if the estimate comfortably fits).
- If `estimated_hours > 4`: **stop here.** Do not reduce `n_train_full`/`epochs_full` to
  force a smaller number, and do not attempt to run anything on Colab (this agent cannot
  execute a Colab notebook). Report the estimate to the user and wait for direction —
  they may choose to run a reduced local job, run it themselves on Colab using this same
  `src/detection/train/` package, or accept a longer local run anyway.

- [ ] **Step 3: Run the full training** (only if Step 2's estimate was within budget)

```bash
source .venv-train/bin/activate
python3 -m src.detection.train.train --n-train <n_train_full> --n-val 588 --epochs <epochs_full> --name full
```

Expected: completes without error (barring the same class of MPS-op issues as the pilot —
apply the same troubleshooting as Task 4 Step 2 if so), reports
`runs/train_1a/full/weights/best.pt`.

- [ ] **Step 4: Commit the timing decision as a note**

Record the actual numbers observed (do not estimate) in the commit message.

```bash
git commit --allow-empty -m "$(cat <<'EOF'
chore: record full-training-run timing decision

Pilot: <n_train> images, <epochs> epochs, <per_epoch_per_image_seconds>s/epoch/image.
Estimate for full run (<n_train_full> images, <epochs_full> epochs): <estimated_hours>h.
Decision: <ran locally on M4 / stopped and reported to user>.
Actual full run time: <actual_hours>h (fill in after Step 3 completes).
EOF
)"
```

---

## Task 6: Evaluation wrapper

**Files:**
- Create: `src/detection/train/run_trained_1a.py`
- Test: manual smoke test (same reasoning as `run_checkpoint_1b.py` in the benchmark package — this wraps a real model, not unit-testable logic)

**Interfaces:**
- Consumes: `PIL.Image.Image` (from `src.detection.benchmark.data.load_sku110k_subset`), `pathlib.Path` to trained weights.
- Produces: `load_model_1a(weights_path: Path) -> Any`, `detect_1a(model, image: PIL.Image.Image, conf: float = 0.25) -> List[metrics.Box]` — same shape as `run_checkpoint_1b.py`'s `load_model_1b`/`detect_1b`, so it plugs into the existing benchmark metrics unchanged.

- [ ] **Step 1: Implement `src/detection/train/run_trained_1a.py`**

```python
"""Wrapper around the YOLOv8 nano checkpoint fine-tuned in this sprint (Task 5's
runs/train_1a/full/weights/best.pt), matching the detect_1b/detect_1c interface used
by src/detection/benchmark/report.py so it plugs into the existing eval/metrics code.
"""
from pathlib import Path
from typing import List

from PIL import Image
from ultralytics import YOLO

from src.detection.benchmark.metrics import Box


def load_model_1a(weights_path: Path):
    return YOLO(str(weights_path))


def detect_1a(model, image: Image.Image, conf: float = 0.25) -> List[Box]:
    results = model.predict(image, device="mps", conf=conf, verbose=False)
    boxes: List[Box] = []
    for box in results[0].boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        boxes.append((x1, y1, x2, y2))
    return boxes
```

- [ ] **Step 2: Smoke-test on one real image with the trained weights**

```bash
source .venv-train/bin/activate
python3 -c "
from pathlib import Path
from src.detection.benchmark.data import load_sku110k_subset
from src.detection.train.run_trained_1a import load_model_1a, detect_1a

subset = load_sku110k_subset(n=1)
model = load_model_1a(Path('runs/train_1a/full/weights/best.pt'))
preds = detect_1a(model, subset[0]['image'])
print('Predicted boxes:', len(preds))
print('Ground-truth boxes:', len(subset[0]['gt_boxes']))
"
```

Expected: runs without error, non-zero predicted box count (Task 5's model may still be
imperfect — the point here is only confirming the wrapper works, not that it passes the
recall bar; Task 7 measures that properly on all 50 images).

- [ ] **Step 3: Commit**

```bash
git add src/detection/train/run_trained_1a.py
git commit -m "feat: add evaluation wrapper for the fine-tuned 1a model"
```

---

## Task 7: Run the real evaluation, write the decision doc

**Files:**
- Create: `src/detection/train/evaluate.py`
- Create: `docs/detection-notes/2026-XX-XX-yolo-finetune-results.md` (fill in actual run date)
- Modify: `README.md`

**Interfaces:**
- Consumes: `src.detection.benchmark.data.load_sku110k_subset`, `src.detection.benchmark.metrics.{compute_precision_recall, aggregate_precision_recall}`, `src.detection.train.run_trained_1a.{load_model_1a, detect_1a}`.
- Produces: `data/benchmark_results/results_1a.json`, printed summary — this sprint's deliverable.

- [ ] **Step 1: Implement `src/detection/train/evaluate.py`**

```python
"""Evaluate the fine-tuned 1a model on the same 50-image SKU-110K eval set used for
1b/1c, for a direct, apples-to-apples comparison.

Usage: python3 -m src.detection.train.evaluate --weights runs/train_1a/full/weights/best.pt
"""
import argparse
import json
from pathlib import Path

from src.detection.benchmark.data import load_sku110k_subset
from src.detection.benchmark.metrics import aggregate_precision_recall, compute_precision_recall
from src.detection.train.run_trained_1a import detect_1a, load_model_1a

RESULTS_PATH = Path("data/benchmark_results/results_1a.json")
RECALL_PASS_THRESHOLD = 0.6  # per docs/superpowers/specs/2026-07-17-detection-yolo-finetune-design.md


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
```

- [ ] **Step 2: Run the evaluation**

```bash
source .venv-train/bin/activate
python3 -m src.detection.train.evaluate --weights runs/train_1a/full/weights/best.pt
```

Expected: prints precision/recall/PASS-or-FAIL, writes `data/benchmark_results/results_1a.json`.

- [ ] **Step 3: Write the decision doc**

Fill in the actual numbers from `data/benchmark_results/results_1a.json` — do not estimate.

```markdown
# YOLO Fine-tune (1a) Results

**Date run:** <fill in actual date>
**Training data:** <n_train> images / <epochs> epochs (harryrobert/SKU-110k-reformat train split)
**Eval set:** same 50 images as 1b/1c (Voxel51/sku110k_test)

## Results

| Model | Precision | Recall | Passes threshold (recall >= 0.6)? |
|---|---|---|---|
| 1a (this sprint's fine-tune) | <fill in> | <fill in> | <fill in> |
| 1b (foduucom/product-detection-in-shelf-yolov8, for reference) | 0.723 | 0.174 | FAIL |
| 1c (IDEA-Research/grounding-dino-tiny, for reference) | 0.718 | 0.093 | FAIL |

## Decision

<Write whether 1a passes recall>=0.6, referencing the actual numbers above and the
decision rule in docs/superpowers/specs/2026-07-17-detection-yolo-finetune-design.md.>

## Next spec

<If 1a passes: Phase 1 is done, next spec is Phase 2 (Classification). If not: write up
the numbers and open the "what next" question to the user per the design spec's
"Bước tiếp theo" section — do not unilaterally decide to try another approach.>
```

- [ ] **Step 4: Update README Status section**

Find this line in `README.md` (added at the end of the previous sprint):

```markdown
- [ ] Detection: fine-tune YOLO nano trên subset SKU-110K (1a, theo quyết định ở trên)
```

Replace with the actual outcome, e.g. if it passed:

```markdown
- [x] Detection: fine-tune YOLO nano trên SKU-110K (1a) — recall <fill in> trên 50 ảnh
      eval, đạt ngưỡng 0.6. Xem `docs/detection-notes/<actual-date>-yolo-finetune-results.md`.
      Phase 1 (Detection) hoàn tất.
```

or, if it did not pass:

```markdown
- [ ] Detection: fine-tune YOLO nano trên SKU-110K (1a) — recall <fill in> trên 50 ảnh
      eval, KHÔNG đạt ngưỡng 0.6. Xem `docs/detection-notes/<actual-date>-yolo-finetune-results.md`
      — cần quyết định hướng tiếp theo trước khi sang Phase 2.
```

- [ ] **Step 5: Commit**

```bash
git add src/detection/train/evaluate.py docs/detection-notes/ README.md
git commit -m "feat: evaluate fine-tuned 1a model, record decision"
```

---

## Self-review notes (for the plan author, already applied above)

- **Spec coverage:** environment setup (Task 1), bbox conversion + tests (Task 2), data materialization + verified schema (Task 3), training script + pilot (Task 4), scale decision + full run (Task 5), eval wrapper (Task 6), real eval + decision doc + README (Task 7) — all spec sections have a task.
- **Placeholder scan:** the only intentionally-unfilled values are in Task 5's timing commit message and Task 7's decision doc template, both of which explicitly instruct pulling real numbers from actual runs rather than guessing.
- **Type consistency:** `Box` (from `src.detection.benchmark.metrics`) is reused as the return type for `detect_1a`, matching `detect_1b`/`detect_1c`'s signatures exactly — no redefinition. `CocoBox` (Task 2) is a distinct type for the training data path only, never mixed with `Box`.
- **No Colab automation:** the plan is explicit (Task 5) that this agent cannot execute Colab — the decision rule stops and asks the user rather than pretending to hand off to Colab automatically.
