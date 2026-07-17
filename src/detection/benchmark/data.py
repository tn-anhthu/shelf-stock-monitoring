"""Load a small SKU-110K subset with ground-truth boxes for benchmarking.

Real schema verified in docs/detection-notes/sku110k-schema.md (2026-07-17). Two
approaches were rejected there: `datasets.load_dataset` exposes no labels at all for
this repo, and `fiftyone.utils.huggingface.load_from_hub` downloads several GB of
unrelated data (the full image set plus embedding models for unused "brain" runs)
regardless of `max_samples`.

Instead: `samples.json` (the repo's single 7.7GB label file) is read via an HTTP
Range-request stream and parsed incrementally with `ijson`, stopping after the first
`n` records — never downloading the full file. Each selected sample's image is then
fetched individually via `huggingface_hub.hf_hub_download`, so network/disk usage
stays proportional to `n`.
"""
from typing import Dict, List

import ijson
import requests
from huggingface_hub import hf_hub_download, hf_hub_url
from PIL import Image

from src.detection.benchmark.metrics import Box

DATASET_ID = "Voxel51/sku110k_test"
SAMPLES_FILE = "samples.json"
# Confirmed in docs/detection-notes/sku110k-schema.md: top-level field is
# "ground_truth", nested "detections" list, each with a "bounding_box" key.
DETECTIONS_FIELD = "ground_truth"


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


def _stream_first_n_samples(n: int) -> List[dict]:
    """Read samples.json as a stream, stopping after the first n records.

    Uses an HTTP Range-capable streaming GET + incremental JSON parsing so the
    7.7GB file is never downloaded in full.
    """
    url = hf_hub_url(DATASET_ID, SAMPLES_FILE, repo_type="dataset")
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    samples = []
    try:
        for item in ijson.items(resp.raw, "samples.item", use_float=True):
            samples.append(item)
            if len(samples) >= n:
                break
    finally:
        resp.close()
    return samples


def load_sku110k_subset(n: int = 50) -> List[Dict]:
    """Fetch the first `n` SKU-110K test samples with parsed ground-truth boxes.

    Only downloads the `n` image files referenced (plus the streamed prefix of
    samples.json) — never the full dataset.
    """
    samples = _stream_first_n_samples(n)
    subset = []
    for sample in samples:
        image_path = hf_hub_download(
            repo_id=DATASET_ID, repo_type="dataset", filename=sample["filepath"]
        )
        image = Image.open(image_path)
        raw_detections = sample[DETECTIONS_FIELD]["detections"]
        gt_boxes = parse_fiftyone_detections(raw_detections, image.width, image.height)
        subset.append({"image": image, "gt_boxes": gt_boxes})
    return subset
