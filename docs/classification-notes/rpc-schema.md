# benjamintli/retail-product-checkout schema — verified 2026-07-18

Command used: `hf_hub_download` + `load_dataset('parquet', data_files=<shard path>, split='train')`
on `train-00000-of-00019.parquet` and `test-00000-of-00011.parquet`.

Splits: `train` (19 shards), `test` (11 shards), `validation` (3 shards) — no separate
"exemplar" split; **train split serves as the catalog source** (single object per image,
grouped by category) and **test split serves as the classification test source** (8-9
objects per checkout-scene image, with ground-truth bbox + category per object).

Features: `{'image': Image, 'objects': {'bbox': [[float32; 4]], 'category': ClassLabel}}`

`objects.bbox` = list of `(x, y, w, h)` in **absolute pixel coordinates, top-left origin**
(same convention as `harryrobert/SKU-110k-reformat` from Phase 1). Example from train-00000:
`[1171.6800537109375, 1047.5999755859375, 399.8500061035156, 284.1000061035156]`.

`objects.category` = a `ClassLabel` int per object; 200 named categories total, from the original
RPC paper's taxonomy. Example: category index 111 maps to `"112_canned_food"`. Get the complete
name list via `ds.features['objects']['category'].feature.names`.

**Train split characteristics** (verified on first 5 images of train-00000-of-00019):
- Exactly 1 object per image (single product, clean shot)
- Image size example: (2592, 1944)
- All images in sample used category 111 (112_canned_food)

**Test split characteristics** (verified on first 5 images of test-00000-of-00011):
- 8-9 objects per image (checkout scene, multiple products)
- Ground-truth bbox and category per object
- Represents real checkout scenarios with multiple SKUs in frame

**Known issue**: `load_dataset(..., streaming=True)` on this dataset hung for 10+ minutes
with zero output (both the default loader and a single-shard `data_files=` variant) —
a direct `hf_hub_download` of the same shard file completed in seconds. **Do not use
streaming for this dataset** — download specific shard files directly instead.

**Total files in repo**: 35 (`.gitattributes`, `README.md`, 19 `train-*.parquet` shards,
11 `test-*.parquet` shards, 3 `validation-*.parquet` shards).
