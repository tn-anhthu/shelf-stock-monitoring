"""Load a small subset of benjamintli/retail-product-checkout (RPC) for the
classification benchmark: catalog exemplars from the train split, test crops from
the test split. See docs/classification-notes/rpc-schema.md for the verified schema.

IMPORTANT: does NOT use `streaming=True` -- that hung for 10+ minutes with zero output
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
    needed_categories: Set[int], max_per_category: int = 3, max_train_shards: int = 19
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
