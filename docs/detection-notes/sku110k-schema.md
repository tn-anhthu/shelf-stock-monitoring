# SKU-110K (Voxel51/sku110k_test) schema — verified 2026-07-17

## Attempt 1: `datasets.load_dataset(..., streaming=True)` — no labels

```python
from datasets import load_dataset
ds = load_dataset('Voxel51/sku110k_test', split='test', streaming=True)
sample = next(iter(ds))
print(sample.keys())
```

Result: `dict_keys(['image'])`. Confirmed via `get_dataset_config_names` (`['default']`),
`get_dataset_split_names` (`['test']`), and `ds.features` (`{'image': Image(...)}`) — there
is no ground-truth field exposed through the plain `datasets` library at all for this repo.
The plan's original assumption (FiftyOne-style detections nested in the `datasets` sample)
does **not** hold for this dataset. Consequence: `data.py` cannot use `datasets.load_dataset`
for ground truth — a different access path is required (see below).

## Attempt 2: `fiftyone.utils.huggingface.load_from_hub(...)` — technically correct, but downloads far more than requested

The repo's own HF dataset card recommends this loading path. It does expose real
`Detection` objects with the expected `bounding_box` format. However, in practice, calling
`load_from_hub('Voxel51/sku110k_test', max_samples=3)` downloaded **over 2.2GB** (still
growing when killed) into `~/fiftyone` and `~/.cache/huggingface`, including two unrelated
embedding models (`BAAI/bge-m3`, `sentence-transformers/all-MiniLM-L6-v2`) needed to
reconstruct the dataset's saved "brain runs" (similarity/visualization index), which have
nothing to do with detection benchmarking. `max_samples` does not bound what gets
downloaded to disk before the local FiftyOne dataset is built. This conflicts with the
plan's Global Constraint ("do not download the full dataset — stream/subset"). Rejected.

## Actual repo structure (via `huggingface_hub.HfApi().dataset_info(..., files_metadata=True)`)

```
.gitattributes
README.md
brain/radio_viz.json      (195 KB  — FiftyOne brain artifact, unused)
data/test_*.jpg           (2936 image files)
fiftyone.yml               (102 B)
metadata.json              (11 KB)
samples.json                (7,731,088,124 bytes ≈ 7.7 GB — all labels, one file)
sku110k.gif                 (41.7 MB)
```

`samples.json` is a single JSON document `{"samples": [ {...}, {...}, ... ]}` with one
object per image. Confirmed structure of one element (fetched via an HTTP Range request,
first ~2KB only — the HF resolve endpoint returned `206 Partial Content`, confirming range
requests are supported):

```json
{
  "filepath": "data/test_0.jpg",
  "ground_truth": {
    "_cls": "Detections",
    "detections": [
      {
        "_cls": "Detection",
        "label": "object",
        "bounding_box": [0.049019607843137254, 0.774203431372549, 0.0428921568627451, 0.07261029411764706]
      },
      ...
    ]
  }
}
```

**Ground-truth box field:** `sample["ground_truth"]["detections"]`, each item's
`bounding_box` = `[x, y, w, h]` **relative to image size (0–1 range)**, top-left origin —
this part of the plan's FiftyOne-convention assumption was correct; only the top-level
field name differs (`ground_truth`, not `detections` as the plan's placeholder code
assumed). `label` is always `"object"` — SKU-110K is class-agnostic (single-class shelf
object localization), matching this project's detection-only use case.

## Chosen approach: stream `samples.json` with `ijson`, fetch only the needed images

Since the HF resolve endpoint supports Range requests and `samples.json` is one JSON array,
`requests.get(url, stream=True)` + `ijson.items(resp.raw, 'samples.item')` lets us read the
first N sample records and stop (closing the connection) without downloading the full
7.7GB file. Verified: fetching the first 5 samples this way took ~13s and required no full
download. For each of the N samples' `filepath`, `huggingface_hub.hf_hub_download(repo_id=...,
repo_type='dataset', filename=sample['filepath'])` downloads exactly that one image (a few
MB each for SKU-110K's ~2448x3264 photos) — nothing else. This avoids both `datasets`
(no labels) and `fiftyone` (uncontrolled bulk download), and keeps total network/disk usage
proportional to `n`, matching the plan's Global Constraint. `data.py` was implemented
against this approach; `DETECTIONS_FIELD`/schema constants updated accordingly.
