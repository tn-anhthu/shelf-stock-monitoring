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
