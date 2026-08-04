"""Calibrate ROW_CLUSTER_TOLERANCE_RATIO / Y_GAP_TOLERANCE_RATIO for
src/pipeline/scan.py::adaptive_tolerances() — see
docs/superpowers/specs/2026-08-04-adaptive-box-tolerance-design.md.

The pipeline's row-clustering (src/pipeline/gap_detection.py,
src/pipeline/box_filter.py) and fragment-merge (src/pipeline/box_merge.py)
logic used hardcoded absolute-pixel tolerances (row_cluster_tolerance=20.0,
y_gap_tolerance=5.0) tuned against the 5 raw (uncropped) test images. Once the
UI's manual crop step (web/src/features/scan-wizard/CropStep.jsx) changes the
absolute resolution of the image sent to /predict, those absolute-pixel
values stop meaning the same thing. This script measures the real median
detected-box height on the 5 raw calibration images and derives a ratio so
the tolerance scales with however "zoomed in" any given photo is:

    row_cluster_tolerance = ROW_CLUSTER_TOLERANCE_RATIO * median_box_height
    y_gap_tolerance = Y_GAP_TOLERANCE_RATIO * median_box_height

Usage:
    python3 scripts/calibrate_adaptive_tolerances.py \
        --weights runs/detect/runs/train_1a/full/weights/best.pt
"""
import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
import pillow_heif
pillow_heif.register_heif_opener()

from src.detection.train.run_trained_1a import detect_1a, load_model_1a

RAW_CALIBRATION_IMAGES = [
    "data/scan_viz/input/test1.HEIC",
    "data/scan_viz/input/test2.HEIC",
    "data/scan_viz/input/test3.HEIC",
    "data/scan_viz/input/test4.HEIC",
    "data/scan_viz/input/test5.HEIC",
]

# Historical hardcoded absolute-pixel values being replaced (see defaults in
# src/pipeline/gap_detection.py, src/pipeline/box_filter.py, src/pipeline/box_merge.py).
OLD_ROW_CLUSTER_TOLERANCE_PX = 20.0
OLD_Y_GAP_TOLERANCE_PX = 5.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=str, required=True)
    args = parser.parse_args()

    model = load_model_1a(Path(args.weights))

    all_heights = []
    for image_path in RAW_CALIBRATION_IMAGES:
        image = Image.open(image_path)
        boxes = detect_1a(model, image)
        heights = [y2 - y1 for (_x1, y1, _x2, y2) in boxes]
        all_heights.extend(heights)
        print(f"{image_path}: {len(boxes)} boxes, median height {statistics.median(heights):.1f}px")

    pooled_median = statistics.median(all_heights)
    row_cluster_ratio = OLD_ROW_CLUSTER_TOLERANCE_PX / pooled_median
    y_gap_ratio = OLD_Y_GAP_TOLERANCE_PX / pooled_median

    print()
    print(f"Pooled median box height across {len(RAW_CALIBRATION_IMAGES)} raw images "
          f"({len(all_heights)} boxes total): {pooled_median:.1f}px")
    print(f"ROW_CLUSTER_TOLERANCE_RATIO = {OLD_ROW_CLUSTER_TOLERANCE_PX} / {pooled_median:.1f} = {row_cluster_ratio:.6f}")
    print(f"Y_GAP_TOLERANCE_RATIO = {OLD_Y_GAP_TOLERANCE_PX} / {pooled_median:.1f} = {y_gap_ratio:.6f}")


if __name__ == "__main__":
    main()
