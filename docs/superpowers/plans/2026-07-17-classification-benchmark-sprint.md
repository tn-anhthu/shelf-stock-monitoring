# Classification Benchmark Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Benchmark CLIP vs SigLIP2 zero-shot embedding retrieval (crop → nearest-neighbor match against a catalog) on a subset of the RPC (Retail Product Checkout) dataset, using real top-1/top-5 accuracy, to decide which embedding model Phase 2 (Classification) should use.

**Architecture:** A small, isolated benchmark package (`src/classification/benchmark/`) mirroring `src/detection/benchmark/`'s shape: data loading, one wrapper file per embedding model, a catalog builder, a retrieval/ranking module, a metrics module, and a report script tying them together. Metrics and retrieval-ranking logic are unit-tested with synthetic embeddings (no network needed); the data loader and model wrappers are smoke-tested against live Hugging Face calls, since that's the only way to validate them.

**Tech Stack:** Python 3.10, PyTorch (`mps` backend for encode-only inference), Hugging Face `datasets` + `transformers`, Pillow, numpy, pytest.

## Global Constraints

- Runs on MacBook Pro M4, 16GB RAM — use `device='mps'` for inference, never assume CUDA. Encode-only (no backward pass), so memory pressure is much lower than Phase 1's training — but still respect the 16GB unified-memory ceiling (see Phase 1's `docs/detection-notes/2026-07-17-yolo-finetune-results.md` "Improvement attempt" section for what happens when that ceiling is hit).
- Dataset: `benjamintli/retail-product-checkout` on Hugging Face — confirmed live 2026-07-17 (see Task 1). **Do not use `streaming=True` on this dataset** — it was observed to hang for 10+ minutes with zero output on both the default `load_dataset(...)` path and a single-shard `data_files=` path, while a direct `hf_hub_download` of the same shard file completed in seconds. Download specific parquet shard files directly instead (Task 3 shows the exact pattern).
- Metrics computed here are top-1 and top-5 retrieval accuracy — **not** a pass/fail threshold decided in advance (per the design spec, the threshold is chosen after seeing real numbers, unlike Phase 1's pre-set recall≥0.6 bar).
- This benchmark evaluates classification **in isolation** from Phase 1's detector: test crops come from RPC's own ground-truth bounding boxes, not from running the Phase 1 YOLO model (which was trained/evaluated only on SKU-110K, a different domain — see the design spec's "Ngoài phạm vi" section for why).
- Every claim about dataset/model schema in code comments must be based on values actually observed (see Task 1), not assumed.

---

## Task 1: Environment setup + verified RPC schema

**Files:**
- Create: `requirements-classify.txt`
- Create: `src/classification/benchmark/__init__.py`
- Create: `tests/classification/__init__.py`
- Create: `tests/classification/benchmark/__init__.py`
- Create: `docs/classification-notes/rpc-schema.md`
- Test: none (environment + schema verification only)

**Interfaces:**
- Produces: a working Python environment later tasks import from (`src.classification.benchmark.*`), and a written record of the real RPC schema every later task's field names are based on.

- [ ] **Step 1: Create `requirements-classify.txt`**

```text
torch>=2.2
torchvision>=0.17
datasets>=2.19
huggingface_hub>=0.23
transformers>=4.41
pillow>=10.0
numpy>=1.24
pytest>=8.0
```

- [ ] **Step 2: Create a dedicated virtualenv and install**

```bash
cd inventory-lending-signal
python3 -m venv .venv-classify
source .venv-classify/bin/activate
pip install --upgrade pip
pip install -r requirements-classify.txt
```

Expected: install completes with no dependency resolution errors. This is a fresh venv, separate from `.venv-benchmark` (old `ultralytics==8.0.43` pin) and `.venv-train` (training-specific) — classification doesn't need `ultralytics` at all.

- [ ] **Step 3: Verify `mps` backend is available**

```bash
python3 -c "import torch; print(torch.backends.mps.is_available())"
```

Expected: `True` on the M4 MacBook Pro.

- [ ] **Step 4: Verify the real RPC dataset schema and record findings**

```bash
python3 -c "
from huggingface_hub import HfApi
api = HfApi()
files = api.list_repo_files('benjamintli/retail-product-checkout', repo_type='dataset')
print('Total files:', len(files))
print([f for f in files if f.endswith('.parquet')][:5])
"
```

Expected: prints a file count (35 as of 2026-07-17: `.gitattributes`, `README.md`, 19 `train-*.parquet` shards, 11 `test-*.parquet` shards, 3 `validation-*.parquet` shards).

```bash
python3 -c "
from huggingface_hub import hf_hub_download
from datasets import load_dataset
path = hf_hub_download(repo_id='benjamintli/retail-product-checkout', repo_type='dataset', filename='data/train-00000-of-00019.parquet')
ds = load_dataset('parquet', data_files=path, split='train')
print('Keys:', list(ds[0].keys()))
print('First 5 categories:', [ds[i]['objects']['category'] for i in range(5)])
print('First bbox:', ds[0]['objects']['bbox'])
print('Image size:', ds[0]['image'].size)
names = ds.features['objects']['category'].feature.names
print('Category 111 name:', names[111])
print('Total category names:', len(names))
"
```

Expected (confirmed 2026-07-17 on `train-00000-of-00019.parquet`): `Keys: ['image', 'objects']`. `objects` is a struct with `bbox` (list of `[x, y, w, h]`, **absolute pixel, top-left origin** — same convention as Phase 1's `harryrobert/SKU-110k-reformat`) and `category` (a `ClassLabel` int per object, 200 named categories, e.g. index 111 → a name like `"..._dessert"` per the RPC taxonomy embedded in the dataset's `dataset_info` — read the real name your run prints, don't assume the exact string). Train-split images have exactly **one object per image** (single product, clean shot) — this is the "exemplar" catalog source. A quick second check on the test split (`test-00000-of-00011.parquet`, same pattern) shows **8-9 objects per image** (checkout scene, multiple products) — this is the crop-and-classify test source.

Create `docs/classification-notes/rpc-schema.md` with what you actually observed:

```markdown
# benjamintli/retail-product-checkout schema — verified 2026-07-17

Command used: `hf_hub_download` + `load_dataset('parquet', data_files=<shard path>, split='train')`
on `train-00000-of-00019.parquet` and `test-00000-of-00011.parquet`.

Splits: `train` (19 shards), `test` (11 shards), `validation` (3 shards) — no separate
"exemplar" split; **train split serves as the catalog source** (single object per image,
grouped by category) and **test split serves as the classification test source** (8-9
objects per checkout-scene image, with ground-truth bbox + category per object).

Features: `{'image': Image, 'objects': {'bbox': [[float32; 4]], 'category': ClassLabel}}`

`objects.bbox` = list of `(x, y, w, h)` in **absolute pixel coordinates, top-left origin**
(same convention as `harryrobert/SKU-110k-reformat` from Phase 1). `objects.category` = a
`ClassLabel` int per object; 200 named categories total, from the original RPC paper's
taxonomy (e.g. grouped names like "..._puffed_food", "..._dessert" — get the exact name
list via `ds.features['objects']['category'].feature.names`).

**Known issue**: `load_dataset(..., streaming=True)` on this dataset hung for 10+ minutes
with zero output (both the default loader and a single-shard `data_files=` variant) —
a direct `hf_hub_download` of the same shard file completed in seconds. **Do not use
streaming for this dataset** — download specific shard files directly instead.
```

- [ ] **Step 5: Create package `__init__.py` files**

`src/classification/benchmark/__init__.py`:
```python
```

`tests/classification/__init__.py`:
```python
```

`tests/classification/benchmark/__init__.py`:
```python
```

- [ ] **Step 6: Commit**

```bash
git add requirements-classify.txt src/classification/benchmark/__init__.py \
  tests/classification/__init__.py tests/classification/benchmark/__init__.py \
  docs/classification-notes/rpc-schema.md
git commit -m "chore: set up classification benchmark environment, verify RPC schema"
```

---

## Task 2: Metrics module (top-1/top-5 accuracy) — TDD

**Files:**
- Create: `src/classification/benchmark/metrics.py`
- Test: `tests/classification/benchmark/test_metrics.py`

**Interfaces:**
- Produces:
  - `is_correct_at_k(ranked_categories: List[int], true_category: int, k: int) -> bool`
  - `compute_topk_accuracy(per_item_rankings: List[List[int]], true_categories: List[int], k: int) -> float`

- [ ] **Step 1: Write the failing tests**

`tests/classification/benchmark/test_metrics.py`:
```python
from src.classification.benchmark.metrics import is_correct_at_k, compute_topk_accuracy


def test_is_correct_at_k_true_category_in_top_k():
    assert is_correct_at_k([5, 2, 9], true_category=2, k=3) is True


def test_is_correct_at_k_true_category_outside_top_k():
    assert is_correct_at_k([5, 2, 9, 1], true_category=1, k=2) is False


def test_is_correct_at_k_empty_ranking_returns_false():
    assert is_correct_at_k([], true_category=1, k=5) is False


def test_compute_topk_accuracy_all_correct_at_k1():
    rankings = [[3, 1, 2], [7, 8, 9]]
    true_categories = [3, 7]
    assert compute_topk_accuracy(rankings, true_categories, k=1) == 1.0


def test_compute_topk_accuracy_half_correct_at_k1():
    rankings = [[3, 1, 2], [7, 8, 9]]
    true_categories = [3, 9]  # second one is at rank 3, not rank 1
    assert compute_topk_accuracy(rankings, true_categories, k=1) == 0.5


def test_compute_topk_accuracy_correct_when_k5_covers_it():
    rankings = [[1, 2, 3, 4, 9]]
    true_categories = [9]
    assert compute_topk_accuracy(rankings, true_categories, k=5) == 1.0


def test_compute_topk_accuracy_empty_returns_zero():
    assert compute_topk_accuracy([], [], k=1) == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv-classify/bin/activate
pytest tests/classification/benchmark/test_metrics.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.classification.benchmark.metrics'`

- [ ] **Step 3: Implement `src/classification/benchmark/metrics.py`**

```python
"""Top-k retrieval accuracy for comparing predicted category rankings against
ground-truth categories.

A "ranking" is a list of category ids ordered by descending similarity to a query
(the most likely category first). Unlike Phase 1's detection metrics (which compute
precision/recall via IoU-based box matching), this is a pure classification metric:
each test crop has exactly one true category, and we check whether it appears within
the top k of the predicted ranking.
"""
from typing import List


def is_correct_at_k(ranked_categories: List[int], true_category: int, k: int) -> bool:
    return true_category in ranked_categories[:k]


def compute_topk_accuracy(
    per_item_rankings: List[List[int]], true_categories: List[int], k: int
) -> float:
    if not per_item_rankings:
        return 0.0
    correct = sum(
        is_correct_at_k(ranking, true_cat, k)
        for ranking, true_cat in zip(per_item_rankings, true_categories)
    )
    return correct / len(per_item_rankings)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/classification/benchmark/test_metrics.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/classification/benchmark/metrics.py tests/classification/benchmark/test_metrics.py
git commit -m "feat: add top-k retrieval accuracy metrics module with tests"
```

---

## Task 3: Retrieve module (cosine similarity + category ranking) — TDD

**Files:**
- Create: `src/classification/benchmark/retrieve.py`
- Test: `tests/classification/benchmark/test_retrieve.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (works on plain numpy arrays and `(category, embedding)` tuples).
- Produces:
  - `CatalogEntry = Tuple[int, np.ndarray]` — `(category_id, embedding)`.
  - `cosine_similarity(a: np.ndarray, b: np.ndarray) -> float`
  - `rank_categories(query_embedding: np.ndarray, catalog: List[CatalogEntry]) -> List[int]` — for each *distinct* category in the catalog, takes the **max** similarity across that category's catalog embeddings (not an average — a crop only needs to match one good exemplar), then returns category ids sorted by that max similarity, descending.

- [ ] **Step 1: Write the failing tests**

`tests/classification/benchmark/test_retrieve.py`:
```python
import numpy as np

from src.classification.benchmark.retrieve import cosine_similarity, rank_categories


def test_cosine_similarity_identical_vectors_returns_one():
    v = np.array([1.0, 2.0, 3.0])
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-9


def test_cosine_similarity_orthogonal_vectors_returns_zero():
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert abs(cosine_similarity(a, b) - 0.0) < 1e-9


def test_cosine_similarity_opposite_vectors_returns_negative_one():
    a = np.array([1.0, 0.0])
    b = np.array([-1.0, 0.0])
    assert abs(cosine_similarity(a, b) - (-1.0)) < 1e-9


def test_rank_categories_orders_by_descending_similarity():
    query = np.array([1.0, 0.0])
    catalog = [
        (10, np.array([0.0, 1.0])),   # orthogonal -> similarity 0
        (20, np.array([1.0, 0.0])),   # identical -> similarity 1
        (30, np.array([0.9, 0.1])),   # close -> similarity high but < 1
    ]
    ranking = rank_categories(query, catalog)
    assert ranking == [20, 30, 10]


def test_rank_categories_takes_max_similarity_per_category_not_average():
    query = np.array([1.0, 0.0])
    catalog = [
        (10, np.array([1.0, 0.0])),    # category 10, exemplar A: identical -> sim 1
        (10, np.array([0.0, 1.0])),    # category 10, exemplar B: orthogonal -> sim 0
        (20, np.array([0.7, 0.7])),    # category 20, only exemplar: sim ~0.707
    ]
    # category 10's BEST exemplar (sim=1) beats category 20's only exemplar (sim~0.707)
    ranking = rank_categories(query, catalog)
    assert ranking[0] == 10


def test_rank_categories_empty_catalog_returns_empty():
    assert rank_categories(np.array([1.0, 0.0]), []) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/classification/benchmark/test_retrieve.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.classification.benchmark.retrieve'`

- [ ] **Step 3: Implement `src/classification/benchmark/retrieve.py`**

```python
"""Cosine-similarity retrieval: rank catalog categories by similarity to a query embedding.

A catalog entry is (category_id, embedding) — the SAME category can appear multiple times
(once per exemplar image), since a crop matching well against any one exemplar of a
category is what counts, not the average embedding of all its exemplars.
"""
from typing import List, Tuple

import numpy as np

CatalogEntry = Tuple[int, np.ndarray]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def rank_categories(query_embedding: np.ndarray, catalog: List[CatalogEntry]) -> List[int]:
    """Rank distinct categories by their best (max) similarity to the query, descending."""
    best_per_category = {}
    for category_id, embedding in catalog:
        sim = cosine_similarity(query_embedding, embedding)
        if category_id not in best_per_category or sim > best_per_category[category_id]:
            best_per_category[category_id] = sim
    return sorted(best_per_category, key=lambda c: best_per_category[c], reverse=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/classification/benchmark/test_retrieve.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/classification/benchmark/retrieve.py tests/classification/benchmark/test_retrieve.py
git commit -m "feat: add cosine-similarity category ranking module with tests"
```

---

## Task 4: RPC data loader (catalog source + test crops)

**Files:**
- Create: `src/classification/benchmark/data.py`
- Test: manual smoke test (network-dependent, same reasoning as Phase 1's `data.py`)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `load_test_crops(n_images: int = 15) -> List[Dict]` — each dict has `"image"` (`PIL.Image.Image`, already cropped to one object) and `"category"` (`int`). Reads the first `n_images` checkout-scene images from `test-00000-of-00011.parquet` and crops every object's bbox out of each.
  - `build_catalog_source(needed_categories: Set[int], max_per_category: int = 3, max_train_shards: int = 5) -> List[Dict]` — each dict has `"image"` and `"category"`. Scans train shards **in order starting from shard 0**, up to `max_train_shards`, collecting up to `max_per_category` single-object exemplar images per category in `needed_categories`. Stops scanning early once every needed category has `max_per_category` exemplars. Categories not found within `max_train_shards` are simply absent from the result (not an error) — Task 5's smoke test checks for this.
  - `load_category_names() -> List[str]` — loads train shard 0 (cached by `huggingface_hub` after the first call, so cheap on repeat calls) purely to read its `ClassLabel` feature, returns the full 200-name list. Train and test shards share the same category schema, so shard 0 of train is a valid source regardless of which split a caller is naming categories for.

- [ ] **Step 1: Implement `src/classification/benchmark/data.py`**

```python
"""Load a small subset of benjamintli/retail-product-checkout (RPC) for the
classification benchmark: catalog exemplars from the train split, test crops from
the test split. See docs/classification-notes/rpc-schema.md for the verified schema.

IMPORTANT: does NOT use `streaming=True` — that hung for 10+ minutes with zero output
on this dataset (see docs/classification-notes/rpc-schema.md). Downloads specific
parquet shard files directly via `hf_hub_download` instead, which is fast.
"""
from typing import Dict, List, Set

from datasets import load_dataset
from huggingface_hub import hf_hub_download

DATASET_ID = "benjamintli/retail-product-checkout"
TEST_SHARD_0 = "data/test-00000-of-00011.parquet"
TRAIN_SHARD_TEMPLATE = "data/train-{idx:05d}-of-00019.parquet"


def _load_shard(filename: str):
    path = hf_hub_download(repo_id=DATASET_ID, repo_type="dataset", filename=filename)
    return load_dataset("parquet", data_files=path, split="train")


def load_category_names() -> List[str]:
    """Full 200-name category list. Loads train shard 0 (cached after first call) just
    to read its ClassLabel feature -- train and test share the same category schema."""
    ds = _load_shard(TRAIN_SHARD_TEMPLATE.format(idx=0))
    return ds.features["objects"]["category"].feature.names


def load_test_crops(n_images: int = 15) -> List[Dict]:
    """Crop every ground-truth object out of the first n_images checkout-scene images."""
    ds = _load_shard(TEST_SHARD_0)
    crops: List[Dict] = []
    for i in range(min(n_images, len(ds))):
        example = ds[i]
        image = example["image"].convert("RGB")
        bboxes = example["objects"]["bbox"]
        categories = example["objects"]["category"]
        for bbox, category in zip(bboxes, categories):
            x, y, w, h = bbox
            crop = image.crop((x, y, x + w, y + h))
            crops.append({"image": crop, "category": category})
    return crops


def build_catalog_source(
    needed_categories: Set[int], max_per_category: int = 3, max_train_shards: int = 5
) -> List[Dict]:
    """Scan train shards 0..max_train_shards-1 for exemplar images of needed_categories."""
    found: Dict[int, List[Dict]] = {c: [] for c in needed_categories}

    for shard_idx in range(max_train_shards):
        if all(len(v) >= max_per_category for v in found.values()):
            break
        ds = _load_shard(TRAIN_SHARD_TEMPLATE.format(idx=shard_idx))
        for example in ds:
            categories = example["objects"]["category"]
            if len(categories) != 1:
                continue  # train images are single-object; skip any anomaly defensively
            category = categories[0]
            if category in needed_categories and len(found[category]) < max_per_category:
                found[category].append({
                    "image": example["image"].convert("RGB"),
                    "category": category,
                })

    return [item for items in found.values() for item in items]
```

- [ ] **Step 2: Manually smoke-test on the live dataset**

```bash
source .venv-classify/bin/activate
python3 -c "
from src.classification.benchmark.data import load_test_crops, build_catalog_source

test_crops = load_test_crops(n_images=15)
print('Test crops:', len(test_crops))
needed_categories = {c['category'] for c in test_crops}
print('Distinct categories in test crops:', len(needed_categories), sorted(needed_categories))

catalog_source = build_catalog_source(needed_categories, max_per_category=3, max_train_shards=5)
print('Catalog source images:', len(catalog_source))
found_categories = {c['category'] for c in catalog_source}
missing = needed_categories - found_categories
print('Categories with NO exemplar found in first 5 train shards:', missing)
"
```

Expected: `test_crops` has ~100-135 items (15 images x 8-9 objects each), a few dozen distinct categories, and `build_catalog_source` finds most of them within the first 5 train shards (some categories may end up in `missing` — that's expected and handled by Task 6's report script, which should skip any test crop whose category has zero catalog exemplars, and print how many were skipped).

- [ ] **Step 3: Commit**

```bash
git add src/classification/benchmark/data.py
git commit -m "feat: add RPC catalog source + test crop loader (no streaming)"
```

---

## Task 5: CLIP embedding wrapper

**Files:**
- Create: `src/classification/benchmark/embed_clip.py`
- Test: manual smoke test (real model, not unit-testable logic)

**Interfaces:**
- Consumes: `PIL.Image.Image`
- Produces: `load_model_clip() -> Tuple[model, processor]`, `embed_image_clip(model, processor, image: PIL.Image.Image) -> np.ndarray`

- [ ] **Step 1: Implement `src/classification/benchmark/embed_clip.py`**

```python
"""CLIP image embedding wrapper, for zero-shot catalog retrieval (no fine-tuning).

Model confirmed to exist on Hugging Face 2026-07-17: openai/clip-vit-base-patch32.
"""
from typing import Tuple

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

MODEL_ID = "openai/clip-vit-base-patch32"


def load_model_clip() -> Tuple[CLIPModel, CLIPProcessor]:
    model = CLIPModel.from_pretrained(MODEL_ID).to("mps")
    processor = CLIPProcessor.from_pretrained(MODEL_ID)
    return model, processor


def embed_image_clip(model: CLIPModel, processor: CLIPProcessor, image: Image.Image) -> np.ndarray:
    inputs = processor(images=image, return_tensors="pt").to("mps")
    with torch.no_grad():
        features = model.get_image_features(**inputs)
    return features[0].cpu().numpy()
```

- [ ] **Step 2: Smoke-test on one real RPC crop**

```bash
source .venv-classify/bin/activate
python3 -c "
from src.classification.benchmark.data import load_test_crops
from src.classification.benchmark.embed_clip import load_model_clip, embed_image_clip

crops = load_test_crops(n_images=1)
model, processor = load_model_clip()
embedding = embed_image_clip(model, processor, crops[0]['image'])
print('Embedding shape:', embedding.shape)
print('Embedding dtype:', embedding.dtype)
print('First 5 values:', embedding[:5])
"
```

Expected: runs without error, prints a 1-D embedding vector (CLIP ViT-B/32's image embedding is 512-dim) with real (non-NaN, non-all-zero) values. If `device="mps"` errors, fall back to `device="cpu"` and note the fallback in the commit message.

- [ ] **Step 3: Commit**

```bash
git add src/classification/benchmark/embed_clip.py
git commit -m "feat: add CLIP image embedding wrapper"
```

---

## Task 6: SigLIP2 embedding wrapper

**Files:**
- Create: `src/classification/benchmark/embed_siglip2.py`
- Test: manual smoke test (same reasoning as Task 5)

**Interfaces:**
- Consumes: `PIL.Image.Image`
- Produces: `load_model_siglip2() -> Tuple[model, processor]`, `embed_image_siglip2(model, processor, image: PIL.Image.Image) -> np.ndarray`

**Known risk:** SigLIP2 is newer than CLIP; some ops may not be implemented on MPS (same class of issue as Grounding DINO in Phase 1's benchmark sprint). Encode-only (no training), so the risk is lower, but Step 2 below is what catches it if it happens.

- [ ] **Step 1: Implement `src/classification/benchmark/embed_siglip2.py`**

```python
"""SigLIP2 image embedding wrapper, for zero-shot catalog retrieval (no fine-tuning).

Model confirmed to exist on Hugging Face 2026-07-17: google/siglip2-base-patch16-224.
"""
from typing import Tuple

import numpy as np
import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor

MODEL_ID = "google/siglip2-base-patch16-224"


def load_model_siglip2() -> Tuple[AutoModel, AutoProcessor]:
    model = AutoModel.from_pretrained(MODEL_ID).to("mps")
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    return model, processor


def embed_image_siglip2(model: AutoModel, processor: AutoProcessor, image: Image.Image) -> np.ndarray:
    inputs = processor(images=image, return_tensors="pt").to("mps")
    with torch.no_grad():
        features = model.get_image_features(**inputs)
    return features[0].cpu().numpy()
```

- [ ] **Step 2: Smoke-test on the same crop used for CLIP**

```bash
source .venv-classify/bin/activate
python3 -c "
from src.classification.benchmark.data import load_test_crops
from src.classification.benchmark.embed_siglip2 import load_model_siglip2, embed_image_siglip2

crops = load_test_crops(n_images=1)
model, processor = load_model_siglip2()
embedding = embed_image_siglip2(model, processor, crops[0]['image'])
print('Embedding shape:', embedding.shape)
print('Embedding dtype:', embedding.dtype)
print('First 5 values:', embedding[:5])
"
```

Expected: runs without error, prints a real embedding vector. If an MPS "operator not implemented" error occurs, fall back to `device="cpu"` for SigLIP2 specifically and note the fallback in the commit message — do not silently paper over it.

- [ ] **Step 3: Commit**

```bash
git add src/classification/benchmark/embed_siglip2.py
git commit -m "feat: add SigLIP2 image embedding wrapper"
```

---

## Task 7: Catalog builder

**Files:**
- Create: `src/classification/benchmark/catalog.py`
- Test: manual smoke test (composes Task 4 data + Task 5/6 embedding functions)

**Interfaces:**
- Consumes: `data.build_catalog_source`'s output shape (`List[Dict]` with `"image"`/`"category"`), any `embed_fn(image: PIL.Image.Image) -> np.ndarray` (so it works for both CLIP and SigLIP2 without duplicating logic).
- Produces: `build_catalog(catalog_source: List[Dict], embed_fn) -> List[retrieve.CatalogEntry]`

- [ ] **Step 1: Implement `src/classification/benchmark/catalog.py`**

```python
"""Build a (category_id, embedding) catalog from exemplar images, using any embed_fn
that maps a PIL image to a numpy embedding vector — works for CLIP, SigLIP2, or any
future embedding model without duplicating this loop.
"""
from typing import Callable, Dict, List

import numpy as np
from PIL import Image

from src.classification.benchmark.retrieve import CatalogEntry


def build_catalog(
    catalog_source: List[Dict], embed_fn: Callable[[Image.Image], np.ndarray]
) -> List[CatalogEntry]:
    return [(item["category"], embed_fn(item["image"])) for item in catalog_source]
```

- [ ] **Step 2: Smoke-test end-to-end with CLIP on a tiny subset**

```bash
source .venv-classify/bin/activate
python3 -c "
from functools import partial
from src.classification.benchmark.data import load_test_crops, build_catalog_source
from src.classification.benchmark.embed_clip import load_model_clip, embed_image_clip
from src.classification.benchmark.catalog import build_catalog
from src.classification.benchmark.retrieve import rank_categories

test_crops = load_test_crops(n_images=2)
needed = {c['category'] for c in test_crops}
catalog_source = build_catalog_source(needed, max_per_category=2, max_train_shards=5)
print('Catalog source size:', len(catalog_source))

model, processor = load_model_clip()
embed_fn = partial(embed_image_clip, model, processor)
catalog = build_catalog(catalog_source, embed_fn)
print('Catalog entries:', len(catalog))

query_embedding = embed_fn(test_crops[0]['image'])
ranking = rank_categories(query_embedding, catalog)
print('True category:', test_crops[0]['category'])
print('Top-5 predicted:', ranking[:5])
"
```

Expected: runs without error; prints a true category and a top-5 predicted list (they won't necessarily match on this tiny 2-image smoke test — that's fine, Task 8's full report measures real accuracy on a larger subset).

- [ ] **Step 3: Commit**

```bash
git add src/classification/benchmark/catalog.py
git commit -m "feat: add embedding-agnostic catalog builder"
```

---

## Task 8: Benchmark report script

**Files:**
- Create: `src/classification/benchmark/report.py`
- Create: `data/classification_results/` (output directory, gitignored contents except `.gitkeep`)
- Modify: `.gitignore`
- Test: manual run (integration script, composes everything already tested/smoke-tested above)

**Interfaces:**
- Consumes: `data.{load_test_crops, build_catalog_source}`, `embed_clip.{load_model_clip, embed_image_clip}`, `embed_siglip2.{load_model_siglip2, embed_image_siglip2}`, `catalog.build_catalog`, `retrieve.rank_categories`, `metrics.compute_topk_accuracy`.
- Produces: a JSON results file at `data/classification_results/results.json` and a printed summary table comparing CLIP vs SigLIP2 — this sprint's deliverable artifact.

- [ ] **Step 1: Add gitignore entry and create output directory placeholder**

Add to `.gitignore`:
```text
data/classification_results/*
!data/classification_results/.gitkeep
```

```bash
mkdir -p data/classification_results
touch data/classification_results/.gitkeep
```

- [ ] **Step 2: Implement `src/classification/benchmark/report.py`**

```python
"""Run the CLIP vs SigLIP2 classification benchmark on an RPC subset and report results.

Usage: python3 -m src.classification.benchmark.report --n-test-images 15
"""
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
    catalog_source = build_catalog_source(needed_categories, max_per_category=3, max_train_shards=5)

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
              f"avg inference: {r['avg_inference_seconds']:.3f}s/crop")


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
```

- [ ] **Step 3: Run the full benchmark**

```bash
source .venv-classify/bin/activate
python3 -m src.classification.benchmark.report --n-test-images 15
```

Expected: prints a summary for both `clip` and `siglip2` with top-1/top-5 accuracy, evaluated/skipped counts, and inference timing, and writes `data/classification_results/results.json`. This run downloads several parquet shards (1 test shard ~340MB, up to 5 train shards) on first run — expect this to take a few minutes, not seconds; subsequent runs reuse the Hugging Face cache and will be much faster.

- [ ] **Step 4: Commit**

```bash
git add src/classification/benchmark/report.py .gitignore data/classification_results/.gitkeep
git commit -m "feat: add classification benchmark report script tying everything together"
```

---

## Task 9: Visual sanity check

**Files:**
- Create: `src/classification/benchmark/visualize.py`
- Create: `data/classification_results/sample_crops/` (output directory, gitignored contents except `.gitkeep`)

**Interfaces:**
- Consumes: same as Task 8.
- Produces: for a handful of test crops, saves the crop image alongside a text file naming its true category and CLIP's/SigLIP2's top-3 predicted category names — a cheap way to catch a bug (e.g. swapped x/y in the bbox crop, or an off-by-one in category indexing) that accuracy numbers alone would hide.

- [ ] **Step 1: Create output directory placeholder**

```bash
mkdir -p data/classification_results/sample_crops
touch data/classification_results/sample_crops/.gitkeep
```

- [ ] **Step 2: Implement `src/classification/benchmark/visualize.py`**

```python
"""Save a handful of test crops with their true vs predicted category names, for
manual sanity-checking. Usage: python3 -m src.classification.benchmark.visualize --n 5
"""
import argparse
from functools import partial
from pathlib import Path

from src.classification.benchmark.catalog import build_catalog
from src.classification.benchmark.data import build_catalog_source, load_category_names, load_test_crops
from src.classification.benchmark.embed_clip import embed_image_clip, load_model_clip
from src.classification.benchmark.retrieve import rank_categories

OUTPUT_DIR = Path("data/classification_results/sample_crops")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5)
    args = parser.parse_args()

    test_crops = load_test_crops(n_images=3)[: args.n]
    needed_categories = {c["category"] for c in test_crops}
    catalog_source = build_catalog_source(needed_categories, max_per_category=3, max_train_shards=5)
    names = load_category_names()

    model, processor = load_model_clip()
    embed_fn = partial(embed_image_clip, model, processor)
    catalog = build_catalog(catalog_source, embed_fn)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for i, crop in enumerate(test_crops):
        crop["image"].save(OUTPUT_DIR / f"crop_{i}.png")
        ranking = rank_categories(embed_fn(crop["image"]), catalog)[:3]
        true_name = names[crop["category"]]
        pred_names = [names[c] for c in ranking]
        (OUTPUT_DIR / f"crop_{i}.txt").write_text(
            f"true category: {true_name}\ntop-3 predicted (CLIP): {pred_names}\n"
        )

    print(f"Saved {len(test_crops)} crops + predictions to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run and manually inspect the output**

```bash
source .venv-classify/bin/activate
python3 -m src.classification.benchmark.visualize --n 5
cat data/classification_results/sample_crops/crop_0.txt
open data/classification_results/sample_crops/crop_0.png
```

Expected: the saved crop image visibly shows one product (not a whole shelf, not an empty/black image — if it is, the bbox crop logic in `data.py` has a bug). The true category name should describe a plausible product type; if CLIP's top-3 looks wildly unrelated (e.g. true="dessert" but top-3 are all "cleaning_supplies") on most samples, that's a real signal worth flagging in the decision doc, not just a benchmark number to report blindly.

- [ ] **Step 4: Commit**

```bash
git add src/classification/benchmark/visualize.py data/classification_results/sample_crops/.gitkeep
git commit -m "feat: add visual sanity-check script for classification crops"
```

---

## Task 10: Decision write-up and README update

**Files:**
- Create: `docs/classification-notes/2026-XX-XX-classification-benchmark-results.md` (fill in actual run date)
- Modify: `README.md`

**Interfaces:** none — this is documentation based on Task 8's `data/classification_results/results.json`.

- [ ] **Step 1: Write the decision doc**

Fill in the actual numbers from `data/classification_results/results.json` produced in Task 8 — do not estimate them.

```markdown
# Classification Benchmark Results — CLIP vs SigLIP2

**Date run:** <fill in actual date>
**Dataset:** RPC (`benjamintli/retail-product-checkout`) — catalog from train split (single-object
exemplars), test crops from test split ground-truth boxes (checkout scenes).
**Subset size:** <fill in n_test_crops>, <fill in n_distinct_categories_needed> categories,
<fill in n_catalog_images> catalog images.

## Results

| Model | Top-1 accuracy | Top-5 accuracy | Avg inference time/crop | Evaluated | Skipped (no catalog entry) |
|---|---|---|---|---|---|
| CLIP (openai/clip-vit-base-patch32) | <fill in> | <fill in> | <fill in>s | <fill in> | <fill in> |
| SigLIP2 (google/siglip2-base-patch16-224) | <fill in> | <fill in> | <fill in>s | <fill in> | <fill in> |

## Decision

<Write which model was chosen and why, referencing the actual numbers above and the
design spec's decision rule in
docs/superpowers/specs/2026-07-17-classification-benchmark-design.md. Note whether the
visual sanity check (Task 9) surfaced anything the accuracy numbers alone wouldn't show.>

## Next spec

<If a model clearly passes and the numbers look trustworthy: Phase 2 continuation
(integrate the chosen model + full catalog), or Phase 3 (Depth multiplier) if Phase 2 is
considered sufficient for now. If both models perform surprisingly poorly: stop, report
the numbers, and open the "what next" question to the user rather than unilaterally
picking a different approach.>
```

- [ ] **Step 2: Update README Status section**

Find this line in `README.md`:

```markdown
- [ ] Classification: CLIP/SigLIP2 embedding matching + catalog ban đầu
```

Replace with the actual outcome, e.g. if CLIP wins:

```markdown
- [x] Classification benchmark: CLIP vs SigLIP2 zero-shot retrieval trên subset RPC
      (Retail Product Checkout) — CLIP top-1 <fill in>, SigLIP2 top-1 <fill in>. Chọn
      <model đã chọn>. Xem `docs/classification-notes/<actual-date>-classification-benchmark-results.md`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/classification-notes/ README.md
git commit -m "docs: record classification benchmark decision (CLIP vs SigLIP2)"
```

---

## Self-review notes (for the plan author, already applied above)

- **Spec coverage:** environment setup + verified schema (Task 1), metrics (Task 2), retrieval ranking (Task 3), data loader with the streaming-hang workaround (Task 4), CLIP wrapper (Task 5), SigLIP2 wrapper (Task 6), catalog builder (Task 7), report script (Task 8), visual sanity check (Task 9, matches spec's "Testing" section), decision doc + README (Task 10) — all spec sections have a task.
- **Placeholder scan:** the only intentionally-unfilled values are in Task 10's decision doc template (explicitly instructs pulling real numbers from `results.json`) and Task 9's noted interface gap (`category_names` plumbing), which is called out explicitly as a real decision the implementer must make and document, not a silently-skipped detail.
- **Type consistency:** `CatalogEntry = Tuple[int, np.ndarray]` defined once in `retrieve.py`, imported by `catalog.py` — no redefinition. `embed_fn` signature (`Callable[[Image.Image], np.ndarray]`) is consistent across `catalog.build_catalog`, `report.run_one_model`, and `visualize.py`'s usage via `functools.partial`.
