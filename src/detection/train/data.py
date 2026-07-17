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
