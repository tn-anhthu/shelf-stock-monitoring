# Detection Benchmark Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Benchmark two "no-training" detection approaches (1b: community YOLOv8 checkpoint, 1c: Grounding DINO zero-shot) on a SKU-110K subset, using real precision/recall metrics, to decide whether Phase 1 (Detection) can skip training entirely or must fall back to fine-tuning YOLO.

**Architecture:** A small, isolated benchmark package (`src/detection/benchmark/`) with 4 responsibilities kept in separate files: loading data with ground truth, running each candidate model, computing match-based precision/recall, and a report script that ties them together. Metrics logic is unit-tested with synthetic boxes (no network needed); model wrappers are smoke-tested on live network calls (Hugging Face) since that's the only way to validate them.

**Tech Stack:** Python 3.10, PyTorch (`mps` backend), Hugging Face `datasets` + `transformers`, `ultralyticsplus`/`ultralytics` (pinned per 1b model card), Pillow, pytest.

## Global Constraints

- Runs on MacBook Pro M4, 16GB RAM — use `device='mps'` for inference, never assume CUDA.
- Do not download the full SKU-110K dataset (13.6GB) — stream/subset via Hugging Face `datasets`.
- Recall@IoU0.5 ≥ 0.45–0.5 is the pass bar for 1b/1c (per spec `docs/superpowers/specs/2026-07-17-detection-benchmark-design.md`); below that on both → fall back to training (1a).
- Every claim about a third-party model's accuracy in code comments/docs must be labeled with its source (e.g. "self-reported by model author on HF, not independently verified") — no unlabeled numbers.
- Metrics computed here are a simplified precision/recall/F1 at a fixed IoU=0.5, **not** full COCO-style interpolated AP — label all outputs accordingly, don't call them "AP" in code, docs, or output.

---

## Task 1: Environment setup

**Files:**
- Create: `requirements.txt`
- Create: `src/detection/benchmark/__init__.py`
- Create: `src/detection/__init__.py`
- Test: none (environment verification only)

**Interfaces:**
- Produces: a working Python environment later tasks import from (`src.detection.benchmark.*`).

- [ ] **Step 1: Create `requirements.txt`**

```text
torch>=2.2
torchvision>=0.17
datasets>=2.19
huggingface_hub>=0.23
transformers>=4.41
ultralyticsplus==0.0.28
ultralytics==8.0.43
pillow>=10.0
pytest>=8.0
```

Note: `ultralytics==8.0.43` is pinned because the `foduucom/product-detection-in-shelf-yolov8` model card (checked 2026-07-17) requires `ultralyticsplus==0.0.28` which itself requires that exact `ultralytics` version. This is an older release than the "1a fallback / fine-tune" work would use later — keep this benchmark in its own virtualenv so it doesn't collide with a future training environment.

- [ ] **Step 2: Create a dedicated virtualenv and install**

```bash
cd inventory-lending-signal
python3 -m venv .venv-benchmark
source .venv-benchmark/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Expected: install completes with no dependency resolution errors. If `ultralyticsplus==0.0.28` conflicts with `transformers>=4.41`, note the exact conflict message — this is a known coupling risk, not a mistake in these steps.

- [ ] **Step 3: Verify `mps` backend is available**

```bash
python3 -c "import torch; print(torch.backends.mps.is_available())"
```

Expected: `True` on the M4 MacBook Pro.

- [ ] **Step 4: Create package `__init__.py` files**

`src/detection/__init__.py`:
```python
```

`src/detection/benchmark/__init__.py`:
```python
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt src/detection/__init__.py src/detection/benchmark/__init__.py
git commit -m "chore: set up benchmark environment and package skeleton"
```

---

## Task 2: Metrics module (IoU, precision, recall) — TDD

**Files:**
- Create: `src/detection/benchmark/metrics.py`
- Test: `tests/detection/benchmark/test_metrics.py`

**Interfaces:**
- Produces:
  - `compute_iou(box_a: Tuple[float,float,float,float], box_b: Tuple[float,float,float,float]) -> float`
  - `match_boxes(pred_boxes: List[Box], gt_boxes: List[Box], iou_threshold: float = 0.5) -> Tuple[int,int,int]` (returns `tp, fp, fn`)
  - `compute_precision_recall(pred_boxes: List[Box], gt_boxes: List[Box], iou_threshold: float = 0.5) -> Dict[str,float]` (keys: `tp, fp, fn, precision, recall`)
  - `aggregate_precision_recall(per_image_results: List[Dict[str,float]]) -> Dict[str,float]` (micro-average across images, same keys)
  - `Box = Tuple[float, float, float, float]` — always `(x1, y1, x2, y2)` in absolute pixel coordinates.

- [ ] **Step 1: Create test directory and write failing tests**

`tests/detection/benchmark/__init__.py`:
```python
```

`tests/detection/benchmark/test_metrics.py`:
```python
from src.detection.benchmark.metrics import (
    compute_iou,
    match_boxes,
    compute_precision_recall,
    aggregate_precision_recall,
)


def test_compute_iou_identical_boxes_returns_one():
    box = (0.0, 0.0, 10.0, 10.0)
    assert compute_iou(box, box) == 1.0


def test_compute_iou_no_overlap_returns_zero():
    box_a = (0.0, 0.0, 10.0, 10.0)
    box_b = (20.0, 20.0, 30.0, 30.0)
    assert compute_iou(box_a, box_b) == 0.0


def test_compute_iou_partial_overlap():
    box_a = (0.0, 0.0, 10.0, 10.0)
    box_b = (5.0, 0.0, 15.0, 10.0)
    # intersection = 5 x 10 = 50, union = 100 + 100 - 50 = 150
    assert compute_iou(box_a, box_b) == 50.0 / 150.0


def test_match_boxes_all_predictions_match_ground_truth():
    gt = [(0.0, 0.0, 10.0, 10.0), (20.0, 20.0, 30.0, 30.0)]
    pred = [(0.0, 0.0, 10.0, 10.0), (20.0, 20.0, 30.0, 30.0)]
    assert match_boxes(pred, gt, iou_threshold=0.5) == (2, 0, 0)


def test_match_boxes_extra_prediction_counts_as_false_positive():
    gt = [(0.0, 0.0, 10.0, 10.0)]
    pred = [(0.0, 0.0, 10.0, 10.0), (50.0, 50.0, 60.0, 60.0)]
    assert match_boxes(pred, gt, iou_threshold=0.5) == (1, 1, 0)


def test_match_boxes_missed_ground_truth_counts_as_false_negative():
    gt = [(0.0, 0.0, 10.0, 10.0), (20.0, 20.0, 30.0, 30.0)]
    pred = [(0.0, 0.0, 10.0, 10.0)]
    assert match_boxes(pred, gt, iou_threshold=0.5) == (1, 0, 1)


def test_compute_precision_recall_returns_expected_values():
    gt = [(0.0, 0.0, 10.0, 10.0), (20.0, 20.0, 30.0, 30.0)]
    pred = [(0.0, 0.0, 10.0, 10.0), (50.0, 50.0, 60.0, 60.0)]
    result = compute_precision_recall(pred, gt, iou_threshold=0.5)
    assert result["tp"] == 1
    assert result["fp"] == 1
    assert result["fn"] == 1
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5


def test_aggregate_precision_recall_micro_averages_across_images():
    per_image = [
        {"tp": 2, "fp": 1, "fn": 0},
        {"tp": 1, "fp": 0, "fn": 1},
    ]
    result = aggregate_precision_recall(per_image)
    assert result["tp"] == 3
    assert result["fp"] == 1
    assert result["fn"] == 1
    assert result["precision"] == 3 / 4
    assert result["recall"] == 3 / 4
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv-benchmark/bin/activate
pytest tests/detection/benchmark/test_metrics.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.detection.benchmark.metrics'`

- [ ] **Step 3: Implement `src/detection/benchmark/metrics.py`**

```python
"""IoU, precision, recall metrics for comparing predicted boxes against ground-truth boxes.

Boxes are (x1, y1, x2, y2) tuples in absolute pixel coordinates.

Note: this module computes precision/recall/F1 at a single fixed IoU threshold
(0.5 by default), matched greedily by descending IoU. It does NOT compute
COCO-style interpolated Average Precision (AP) across confidence thresholds —
do not label these numbers "AP" anywhere they're reported.
"""
from typing import Dict, List, Tuple

Box = Tuple[float, float, float, float]


def compute_iou(box_a: Box, box_b: Box) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union_area = area_a + area_b - inter_area

    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def match_boxes(
    pred_boxes: List[Box], gt_boxes: List[Box], iou_threshold: float = 0.5
) -> Tuple[int, int, int]:
    """Greedy one-to-one matching by descending IoU. Returns (tp, fp, fn)."""
    candidates = []
    for pi, pb in enumerate(pred_boxes):
        for gi, gb in enumerate(gt_boxes):
            iou = compute_iou(pb, gb)
            if iou >= iou_threshold:
                candidates.append((iou, pi, gi))
    candidates.sort(key=lambda c: c[0], reverse=True)

    matched_pred = set()
    matched_gt = set()
    for _iou, pi, gi in candidates:
        if pi in matched_pred or gi in matched_gt:
            continue
        matched_pred.add(pi)
        matched_gt.add(gi)

    tp = len(matched_pred)
    fp = len(pred_boxes) - len(matched_pred)
    fn = len(gt_boxes) - len(matched_gt)
    return tp, fp, fn


def compute_precision_recall(
    pred_boxes: List[Box], gt_boxes: List[Box], iou_threshold: float = 0.5
) -> Dict[str, float]:
    tp, fp, fn = match_boxes(pred_boxes, gt_boxes, iou_threshold)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall}


def aggregate_precision_recall(per_image_results: List[Dict[str, float]]) -> Dict[str, float]:
    """Micro-average tp/fp/fn across images into a single precision/recall."""
    total_tp = sum(r["tp"] for r in per_image_results)
    total_fp = sum(r["fp"] for r in per_image_results)
    total_fn = sum(r["fn"] for r in per_image_results)
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    return {
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_fn,
        "precision": precision,
        "recall": recall,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/detection/benchmark/test_metrics.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/detection/benchmark/metrics.py tests/detection/benchmark/
git commit -m "feat: add IoU/precision/recall metrics module with tests"
```

---

## Task 3: Verify SKU-110K dataset schema, then implement subset loader

**Files:**
- Create: `docs/detection-notes/sku110k-schema.md`
- Create: `src/detection/benchmark/data.py`
- Test: `tests/detection/benchmark/test_data.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `parse_fiftyone_detections(detections: List[dict], image_width: int, image_height: int) -> List[metrics.Box]` — converts FiftyOne-style normalized `[x, y, w, h]` detections into absolute `(x1, y1, x2, y2)` boxes. This is the part covered by a fast, network-free unit test.
  - `load_sku110k_subset(n: int = 50) -> List[Dict]` — each dict has keys `"image"` (`PIL.Image.Image`) and `"gt_boxes"` (`List[metrics.Box]`). This part needs live network access and is verified manually, not by pytest.

**Important — do this step first, don't skip it:** the exact column name for ground-truth boxes in `Voxel51/sku110k_test` is not confirmed yet. The dataset is tagged `fiftyone` on Hugging Face, and FiftyOne's own `Detection` objects store boxes in a `bounding_box` field as `[top-left-x, top-left-y, width, height]` **relative to image size (0–1 range)** — this is FiftyOne's documented convention, not a guess about this specific dataset export. Step 1 below confirms whether that convention holds for this exact HF dataset before any code depends on it.

- [ ] **Step 1: Inspect the real dataset schema and record findings**

```bash
source .venv-benchmark/bin/activate
python3 -c "
from datasets import load_dataset
ds = load_dataset('Voxel51/sku110k_test', split='test', streaming=True)
sample = next(iter(ds))
print('Keys:', list(sample.keys()))
for k, v in sample.items():
    print(k, '->', type(v), str(v)[:300])
"
```

Run this and read the actual output. Create `docs/detection-notes/sku110k-schema.md` with what you observed:

```markdown
# SKU-110K (Voxel51/sku110k_test) schema — verified 2026-07-17

Command used: `load_dataset('Voxel51/sku110k_test', split='test', streaming=True)`, first sample.

Top-level keys: <paste the actual list from `Keys:` output here>

Ground-truth box field: <name of the field containing boxes, e.g. `detections.detections`>
Box format found: <e.g. "list of dicts, each with a `bounding_box` key = [x, y, w, h] relative 0-1">

If this does NOT match FiftyOne's `[x, y, w, h]` relative convention, write the actual format here instead and update Step 3 of this task accordingly before implementing `parse_fiftyone_detections`.
```

**If the field names differ from what Step 3 assumes below**, adjust the constant names in `data.py` (`DETECTIONS_FIELD`, `LABEL_FIELD`) to match what you actually observed — do not silently keep code that doesn't match the real schema.

- [ ] **Step 2: Write the failing test for the network-free parsing function**

`tests/detection/benchmark/test_data.py`:
```python
from src.detection.benchmark.data import parse_fiftyone_detections


def test_parse_fiftyone_detections_converts_relative_to_absolute_boxes():
    detections = [
        {"bounding_box": [0.1, 0.2, 0.3, 0.4]},  # x, y, w, h relative
    ]
    boxes = parse_fiftyone_detections(detections, image_width=100, image_height=200)
    # x1 = 0.1*100=10, y1=0.2*200=40, x2=(0.1+0.3)*100=40, y2=(0.2+0.4)*200=120
    assert boxes == [(10.0, 40.0, 40.0, 120.0)]


def test_parse_fiftyone_detections_handles_multiple_boxes():
    detections = [
        {"bounding_box": [0.0, 0.0, 0.5, 0.5]},
        {"bounding_box": [0.5, 0.5, 0.5, 0.5]},
    ]
    boxes = parse_fiftyone_detections(detections, image_width=10, image_height=10)
    assert boxes == [(0.0, 0.0, 5.0, 5.0), (5.0, 5.0, 10.0, 10.0)]


def test_parse_fiftyone_detections_empty_list_returns_empty():
    assert parse_fiftyone_detections([], image_width=100, image_height=100) == []
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/detection/benchmark/test_data.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.detection.benchmark.data'`

- [ ] **Step 4: Implement `src/detection/benchmark/data.py`**

Use the field names you actually confirmed in Step 1. This code assumes the FiftyOne convention was confirmed — if Step 1 found something different, edit `DETECTIONS_FIELD` and the loop in `load_sku110k_subset` accordingly before moving on.

```python
"""Load a small SKU-110K subset (via Hugging Face `datasets`, streaming — never
downloads the full 13.6GB dataset) with ground-truth boxes for benchmarking.
"""
from typing import Dict, List

from datasets import load_dataset

from src.detection.benchmark.metrics import Box

DATASET_ID = "Voxel51/sku110k_test"
DETECTIONS_FIELD = "detections"  # confirmed in docs/detection-notes/sku110k-schema.md — update if different


def parse_fiftyone_detections(
    detections: List[dict], image_width: int, image_height: int
) -> List[Box]:
    """Convert FiftyOne-style detections (relative [x, y, w, h]) to absolute (x1, y1, x2, y2)."""
    boxes: List[Box] = []
    for det in detections:
        x, y, w, h = det["bounding_box"]
        x1 = x * image_width
        y1 = y * image_height
        x2 = (x + w) * image_width
        y2 = (y + h) * image_height
        boxes.append((x1, y1, x2, y2))
    return boxes


def load_sku110k_subset(n: int = 50) -> List[Dict]:
    """Stream the first `n` examples of the SKU-110K test split with parsed ground-truth boxes."""
    ds = load_dataset(DATASET_ID, split="test", streaming=True)
    subset = []
    for i, example in enumerate(ds):
        if i >= n:
            break
        image = example["image"]
        raw_detections = example[DETECTIONS_FIELD]["detections"]
        gt_boxes = parse_fiftyone_detections(raw_detections, image.width, image.height)
        subset.append({"image": image, "gt_boxes": gt_boxes})
    return subset
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/detection/benchmark/test_data.py -v
```

Expected: all 3 tests PASS. (These test only `parse_fiftyone_detections`, not `load_sku110k_subset`, so no network call happens here.)

- [ ] **Step 6: Manually smoke-test `load_sku110k_subset` against the live dataset**

```bash
python3 -c "
from src.detection.benchmark.data import load_sku110k_subset
subset = load_sku110k_subset(n=3)
for item in subset:
    print(item['image'].size, 'gt_boxes:', len(item['gt_boxes']), item['gt_boxes'][:2])
"
```

Expected: 3 items printed, each with a real image size and a non-empty `gt_boxes` list (SKU-110K images average ~147 objects each, so `len(gt_boxes)` should be well above 0 — if it's 0 for all 3, the field name from Step 1 is wrong and needs fixing before continuing).

- [ ] **Step 7: Commit**

```bash
git add docs/detection-notes/sku110k-schema.md src/detection/benchmark/data.py tests/detection/benchmark/test_data.py
git commit -m "feat: add SKU-110K subset loader with verified schema"
```

---

## Task 4: 1b — community YOLOv8 checkpoint wrapper

**Files:**
- Create: `src/detection/benchmark/run_checkpoint_1b.py`
- Test: manual smoke test (no pytest — this task is "does the real model produce real boxes", not unit-testable logic)

**Interfaces:**
- Consumes: `PIL.Image.Image` (from `data.load_sku110k_subset`)
- Produces: `load_model_1b() -> Any` (the loaded `ultralyticsplus.YOLO` model), `detect_1b(model, image: PIL.Image.Image, conf: float = 0.25) -> List[metrics.Box]`

**Known risk (from HF model card review, 2026-07-17):** `foduucom/product-detection-in-shelf-yolov8`'s own usage snippet has an error — it imports `from ultralytics import YOLOvv8` (not a real class) in one place, then separately uses `from ultralyticsplus import YOLO` with a *different* repo id string (`foduucom/shelf-object-detection-yolov8`) in another. The correct approach is `ultralyticsplus.YOLO` with **this exact repo id** (`foduucom/product-detection-in-shelf-yolov8`, matching the actual HF page). The model's `mAP@0.5(box) = 0.910` is **self-reported by the model author**, not independently verified by us or by Hugging Face — treat it as a starting hypothesis to test, not a fact.

- [ ] **Step 1: Implement `src/detection/benchmark/run_checkpoint_1b.py`**

```python
"""Wrapper around the foduucom/product-detection-in-shelf-yolov8 checkpoint.

Source: https://huggingface.co/foduucom/product-detection-in-shelf-yolov8
Self-reported mAP@0.5(box) = 0.910 by the model author (not independently verified).
Supported labels per the model card: ['Empty Shelves', 'Magical Products'] — we only
care about the product-presence class for localization, not the label text itself.
"""
from typing import List

from PIL import Image
from ultralyticsplus import YOLO

from src.detection.benchmark.metrics import Box

MODEL_ID = "foduucom/product-detection-in-shelf-yolov8"


def load_model_1b():
    model = YOLO(MODEL_ID)
    model.overrides["conf"] = 0.25
    model.overrides["iou"] = 0.45
    model.overrides["agnostic_nms"] = False
    model.overrides["max_det"] = 1000
    return model


def detect_1b(model, image: Image.Image, conf: float = 0.25) -> List[Box]:
    model.overrides["conf"] = conf
    results = model.predict(image, device="mps", verbose=False)
    boxes: List[Box] = []
    for box in results[0].boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        boxes.append((x1, y1, x2, y2))
    return boxes
```

- [ ] **Step 2: Smoke-test on one real SKU-110K image**

```bash
python3 -c "
from src.detection.benchmark.data import load_sku110k_subset
from src.detection.benchmark.run_checkpoint_1b import load_model_1b, detect_1b

subset = load_sku110k_subset(n=1)
model = load_model_1b()
preds = detect_1b(model, subset[0]['image'])
print('Predicted boxes:', len(preds))
print('Ground-truth boxes:', len(subset[0]['gt_boxes']))
print('Sample predicted box:', preds[0] if preds else None)
"
```

Expected: runs without error, prints a non-zero predicted box count. If `device="mps"` errors out (some `ultralytics==8.0.43` builds have incomplete `mps` support), fall back to `device="cpu"` for this specific model and note the fallback in the commit message — this is a real, previously-unverified compatibility risk, not something to paper over.

- [ ] **Step 3: Commit**

```bash
git add src/detection/benchmark/run_checkpoint_1b.py
git commit -m "feat: add 1b YOLOv8 checkpoint inference wrapper"
```

---

## Task 5: 1c — Grounding DINO zero-shot wrapper

**Files:**
- Create: `src/detection/benchmark/run_zeroshot_1c.py`
- Test: manual smoke test (same reasoning as Task 4)

**Interfaces:**
- Consumes: `PIL.Image.Image`
- Produces: `load_model_1c() -> Tuple[processor, model]`, `detect_1c(processor, model, image: PIL.Image.Image, text_prompt: str = "product.", box_threshold: float = 0.3, text_threshold: float = 0.25) -> List[metrics.Box]`

**Known risk:** no benchmark for Grounding DINO on dense/overlapping retail shelves was found during spec research (see `docs/superpowers/specs/2026-07-17-detection-benchmark-design.md`) — this task's smoke test is genuinely the first data point, not a confirmation of published results.

- [ ] **Step 1: Implement `src/detection/benchmark/run_zeroshot_1c.py`**

```python
"""Zero-shot open-vocabulary detection via Grounding DINO (transformers integration).

Model: IDEA-Research/grounding-dino-tiny (smallest variant, best fit for local M4 inference).
No training, no checkpoint download beyond the base model weights.
"""
from typing import List, Tuple

import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection

from src.detection.benchmark.metrics import Box

MODEL_ID = "IDEA-Research/grounding-dino-tiny"


def load_model_1c() -> Tuple[AutoProcessor, AutoModelForZeroShotObjectDetection]:
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(MODEL_ID).to("mps")
    return processor, model


def detect_1c(
    processor,
    model,
    image: Image.Image,
    text_prompt: str = "product.",
    box_threshold: float = 0.3,
    text_threshold: float = 0.25,
) -> List[Box]:
    inputs = processor(images=image, text=text_prompt, return_tensors="pt").to("mps")
    with torch.no_grad():
        outputs = model(**inputs)

    results = processor.post_process_grounded_object_detection(
        outputs,
        inputs["input_ids"],
        box_threshold=box_threshold,
        text_threshold=text_threshold,
        target_sizes=[image.size[::-1]],
    )[0]

    boxes: List[Box] = [tuple(box.tolist()) for box in results["boxes"]]
    return boxes
```

- [ ] **Step 2: Smoke-test on the same image used for 1b**

```bash
python3 -c "
from src.detection.benchmark.data import load_sku110k_subset
from src.detection.benchmark.run_zeroshot_1c import load_model_1c, detect_1c

subset = load_sku110k_subset(n=1)
processor, model = load_model_1c()
preds = detect_1c(processor, model, subset[0]['image'])
print('Predicted boxes:', len(preds))
print('Ground-truth boxes:', len(subset[0]['gt_boxes']))
print('Sample predicted box:', preds[0] if preds else None)
"
```

Expected: runs without error. Record wall-clock time manually (`time python3 -c "..."`) — this matters for the "which is faster on M4" tie-breaker in the spec's decision criteria. If zero boxes come back, try prompts `"item."`, `"product on shelf."`, or lowering `box_threshold` before concluding the model can't handle this — Grounding DINO's post-processing is prompt-sensitive.

- [ ] **Step 3: Commit**

```bash
git add src/detection/benchmark/run_zeroshot_1c.py
git commit -m "feat: add 1c Grounding DINO zero-shot inference wrapper"
```

---

## Task 6: Benchmark report script

**Files:**
- Create: `src/detection/benchmark/report.py`
- Create: `data/benchmark_results/` (output directory, gitignored contents except `.gitkeep`)
- Test: manual run (integration script, not unit-testable — it's the composition of everything already tested/smoke-tested above)

**Interfaces:**
- Consumes: `data.load_sku110k_subset`, `run_checkpoint_1b.{load_model_1b, detect_1b}`, `run_zeroshot_1c.{load_model_1c, detect_1c}`, `metrics.{compute_precision_recall, aggregate_precision_recall}`
- Produces: a JSON results file at `data/benchmark_results/results.json` and a printed summary table. This is the sprint's deliverable artifact per the spec.

- [ ] **Step 1: Create output directory placeholder**

```bash
mkdir -p data/benchmark_results
touch data/benchmark_results/.gitkeep
```

- [ ] **Step 2: Implement `src/detection/benchmark/report.py`**

```python
"""Run the 1b vs 1c detection benchmark on a SKU-110K subset and report results.

Usage: python3 -m src.detection.benchmark.report --n 50
"""
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
```

- [ ] **Step 3: Run the full benchmark**

```bash
python3 -m src.detection.benchmark.report --n 50
```

Expected: prints a summary for both 1b and 1c with precision/recall/timing, and writes `data/benchmark_results/results.json`. This run can take several minutes on M4 CPU/MPS for 50 images through two models — that's expected, not a bug.

- [ ] **Step 4: Commit**

```bash
git add src/detection/benchmark/report.py data/benchmark_results/.gitkeep
git commit -m "feat: add benchmark report script tying 1b/1c/metrics together"
```

---

## Task 7: Visual sanity check

**Files:**
- Create: `src/detection/benchmark/visualize.py`
- Create: `data/benchmark_results/sample_overlays/` (output directory, gitignored contents except `.gitkeep`)

**Interfaces:**
- Consumes: same as Task 6.
- Produces: PNG files with predicted (red) and ground-truth (green) boxes drawn on sample images — a cheap way to catch a metric bug that numbers alone would hide (e.g., swapped x/y in `parse_fiftyone_detections`).

- [ ] **Step 1: Create output directory placeholder**

```bash
mkdir -p data/benchmark_results/sample_overlays
touch data/benchmark_results/sample_overlays/.gitkeep
```

- [ ] **Step 2: Implement `src/detection/benchmark/visualize.py`**

```python
"""Draw predicted vs ground-truth boxes on sample images for manual sanity-checking.

Usage: python3 -m src.detection.benchmark.visualize --n 5
"""
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
```

- [ ] **Step 3: Run and manually inspect the output images**

```bash
python3 -m src.detection.benchmark.visualize --n 5
open data/benchmark_results/sample_overlays/image_0_1b.png
```

Expected: green (ground truth) boxes visibly align with real product boundaries in the image. If green boxes look shifted/scaled wrong across most images, the schema assumption from Task 3 is wrong — go back and fix `parse_fiftyone_detections` or the field mapping before trusting any benchmark numbers.

- [ ] **Step 4: Commit**

```bash
git add src/detection/benchmark/visualize.py data/benchmark_results/sample_overlays/.gitkeep
git commit -m "feat: add visual overlay sanity-check script"
```

---

## Task 8: Decision write-up and README correction

**Files:**
- Create: `docs/detection-notes/2026-XX-XX-detection-benchmark-results.md` (fill in actual run date)
- Modify: `README.md` (fix Autodistill role description)

**Interfaces:** none — this is documentation based on Task 6's `data/benchmark_results/results.json`.

- [ ] **Step 1: Write the decision doc**

Fill in the actual numbers from `data/benchmark_results/results.json` produced in Task 6 — do not estimate them.

```markdown
# Detection Benchmark Results — 1b vs 1c

**Date run:** <fill in actual date>
**Subset size:** <fill in `n_images` from results.json>

## Results

| Model | Precision | Recall | Avg inference time/image | Passes threshold (recall >= 0.45)? |
|---|---|---|---|---|
| 1b (foduucom/product-detection-in-shelf-yolov8) | <fill in> | <fill in> | <fill in>s | <fill in> |
| 1c (IDEA-Research/grounding-dino-tiny) | <fill in> | <fill in> | <fill in>s | <fill in> |

## Decision

<Write which of 1a/1b/1c was chosen and why, referencing the actual numbers above
and the decision rule in docs/superpowers/specs/2026-07-17-detection-benchmark-design.md.>

## Next spec

<State whether the next spec is "Phase 1 continuation (1a fine-tuning)" or
"Phase 2 (Classification)", per the "Bước tiếp theo" section of the design spec.>
```

- [ ] **Step 2: Fix the Autodistill description in README.md**

Find this line in `README.md`:

```markdown
1. **Detection (localization)** — fine-tune YOLO (nano, transfer learning) trên tập SKU-110K
   (dense/overlapping shelf objects), chạy local trên M4 (`device='mps'`) hoặc Colab.
   Auto-labeling hỗ trợ bằng Autodistill (Grounding DINO + SAM).
```

Replace with:

```markdown
1. **Detection (localization)** — trên tập SKU-110K (dense/overlapping shelf objects),
   chạy local trên M4 (`device='mps'`) hoặc Colab. SKU-110K đã có sẵn ground-truth
   bounding boxes nên không cần Autodistill để label chính dataset này — trước khi
   fine-tune riêng, benchmark xem checkpoint có sẵn (YOLOv8 community) hoặc detector
   zero-shot (Grounding DINO) có đủ dùng không (xem
   `docs/superpowers/specs/2026-07-17-detection-benchmark-design.md`). Autodistill
   (Grounding DINO + SAM) chỉ cần thiết sau này nếu tự chụp ảnh kệ hàng Việt Nam để
   fine-tune thêm (ảnh đó chưa có label sẵn).
```

- [ ] **Step 3: Commit**

```bash
git add docs/detection-notes/ README.md
git commit -m "docs: record detection benchmark decision, fix Autodistill role in README"
```

---

## Self-review notes (for the plan author, already applied above)

- **Spec coverage:** benchmark setup (Task 1), data + verified schema (Task 3), 1b (Task 4), 1c (Task 5), metrics/decision threshold (Task 2, Task 6), visual sanity check (Task 7, matches spec's "Testing" section), README fix (Task 8) — all spec sections have a task.
- **Placeholder scan:** the only intentionally-unfilled values are in Task 8's decision doc template, which explicitly instructs pulling real numbers from `results.json` rather than guessing — this is a data-entry step, not a "TBD" left for someone to figure out later.
- **Type consistency:** `Box = Tuple[float, float, float, float]` defined once in `metrics.py`, imported everywhere else (`data.py`, `run_checkpoint_1b.py`, `run_zeroshot_1c.py`) — no redefinition.
