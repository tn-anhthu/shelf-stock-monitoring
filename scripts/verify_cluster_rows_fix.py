"""General-purpose, geometry-only pipeline verification/visualization tool for
cluster_rows (src/pipeline/row_clustering.py) and the row-grouping/gap-detection
stages that depend on it, run against real detected boxes on the 5 raw
calibration images (originally written per docs/superpowers/specs/
2026-08-06-cluster-rows-chaining-fix-design.md, kept as a durable tool since --
see docs/detection-notes/detection-log.md's 06/08/2026 entry).

Unlike scripts/debug_stage_trace.py (which stops at filter_contained_boxes
and never calls detect_gaps) and scripts/visualize_scan_e2e.py (which draws
an annotated image but only after running crop -> SigLIP2 embed -> LLM
classify on every box, i.e. it costs real tokens/API calls per run), this
script runs the exact same geometry stages src/pipeline/scan.py::run_scan()
runs (detect -> merge_adjacent_fragments -> filter_anomalous_boxes ->
filter_contained_boxes -> detect_gaps, same order, same adaptive_tolerances())
and STOPS there -- no crop_box, no SigLIP2, no LLM call, ever. That makes it
the right tool for inspecting what the geometry stages currently produce
without paying for classification you haven't touched yet.

It prints, per image:
  - box count at each stage (dedup regression check)
  - every gap detect_gaps() reports
  - for each --check-region given (single-image mode only), whether any
    reported gap overlaps it
  - (optional, with --out) saves an annotated image: detected boxes in blue,
    filter_contained_boxes NEEDS REVIEW boxes in yellow, gaps in orange --
    same color convention as scripts/visualize_scan_e2e.py's GAP_COLOR/
    FLAGGED_COLOR, minus the green/red matched/unknown colors (which require
    classification results this script never computes)

Usage:
    # Full run across all 5 raw calibration images, no region check, no image output:
    python3 scripts/verify_cluster_rows_fix.py \\
        --weights runs/detect/runs/train_1a/n_2000/weights/best.pt

    # Single image + save an annotated image to eyeball boxes/gaps directly:
    python3 scripts/verify_cluster_rows_fix.py \\
        --weights runs/detect/runs/train_1a/n_2000/weights/best.pt \\
        --image data/scan_viz/input/test3.HEIC \\
        --out data/scan_viz/test3_geometry_only

    # Single image + check whether a specific known-bad region still gets a
    # phantom gap (repeat --check-region for more than one; x1,y1,x2,y2 in
    # that image's raw pixel coordinates):
    python3 scripts/verify_cluster_rows_fix.py \\
        --weights runs/detect/runs/train_1a/n_2000/weights/best.pt \\
        --image data/scan_viz/input/test3.HEIC \\
        --check-region 600,2400,1150,2850

"""
import argparse
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pillow_heif
pillow_heif.register_heif_opener()
from PIL import Image, ImageDraw

from src.detection.benchmark.metrics import Box
from src.detection.train.run_trained_1a import detect_1a, load_model_1a
from src.pipeline.box_filter import filter_anomalous_boxes, filter_contained_boxes
from src.pipeline.box_merge import merge_adjacent_fragments
from src.pipeline.gap_detection import detect_gaps
from src.pipeline.row_clustering import cluster_rows
from src.pipeline.scan import adaptive_tolerances

DEFAULT_IMAGES = [
    "data/scan_viz/input/test1.HEIC",
    "data/scan_viz/input/test2.HEIC",
    "data/scan_viz/input/test3.HEIC",
    "data/scan_viz/input/test4.HEIC",
    "data/scan_viz/input/test5.HEIC",
]

# Same GAP_COLOR/FLAGGED_COLOR values as scripts/visualize_scan_e2e.py, for
# visual consistency between the two tools. No MATCHED_COLOR/UNKNOWN_COLOR
# here -- this script never runs classification, so there's no sku match
# status to color by. Every plain detected box uses BOX_COLOR instead.
BOX_COLOR = (60, 120, 255)
GAP_COLOR = (255, 140, 0)
FLAGGED_COLOR = (255, 230, 0)


def box_overlaps_region(box: Box, region: Box) -> bool:
    x1, y1, x2, y2 = box
    rx1, ry1, rx2, ry2 = region
    return not (x2 <= rx1 or x1 >= rx2 or y2 <= ry1 or y1 >= ry2)


def annotate_and_save(
    image: Image.Image, boxes: List[Box], flagged_regions: List[Box], gaps: List[Box], out_path: Path
) -> None:
    flagged_set = {tuple(b) for b in flagged_regions}
    canvas = image.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas)
    for b in boxes:
        x1, y1, x2, y2 = b
        color = FLAGGED_COLOR if tuple(b) in flagged_set else BOX_COLOR
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        if tuple(b) in flagged_set:
            label = "NEEDS REVIEW"
            text_y = max(0, y1 - 14)
            draw.rectangle([x1, text_y, x1 + 7 * len(label), text_y + 13], fill=color)
            draw.text((x1 + 2, text_y), label, fill=(0, 0, 0))
    for gx1, gy1, gx2, gy2 in gaps:
        draw.rectangle([gx1, gy1, gx2, gy2], outline=GAP_COLOR, width=3)
        label = "GAP?"
        text_y = max(0, gy1 - 14)
        draw.rectangle([gx1, text_y, gx1 + 7 * len(label), text_y + 13], fill=GAP_COLOR)
        draw.text((gx1 + 2, text_y), label, fill=(0, 0, 0))
    canvas.save(out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=str, required=True)
    parser.add_argument(
        "--image", type=str, default=None,
        help="Single image to run (enables --check-region and --out). Omit to run all of DEFAULT_IMAGES instead.",
    )
    parser.add_argument(
        "--check-region", type=str, action="append", default=[],
        help="x1,y1,x2,y2 in the given --image's raw pixel coords. Repeatable. "
             "Reports whether any detected gap overlaps it. Only used with --image.",
    )
    parser.add_argument(
        "--out", type=str, default=None,
        help="If set (requires --image), saves an annotated image (boxes/NEEDS REVIEW/gaps, "
             "no classification) to <out>/annotated.jpg.",
    )
    parser.add_argument(
        "--sweep", type=str, default=None,
        help="Comma-separated max_span_multiplier candidates to test directly against "
             "cluster_rows() on the post-merge boxes of --image (e.g. '1.2,1.5,1.8,2.0,2.5,3.0'). "
             "Requires exactly 2 --check-region values representing 2 known-DISTINCT physical "
             "shelf rows -- reports, per candidate, whether the two regions land in the same "
             "cluster_rows() row (FAIL, still chaining) or different rows (PASS).",
    )
    args = parser.parse_args()

    model = load_model_1a(Path(args.weights))
    images = [args.image] if args.image else DEFAULT_IMAGES
    regions: List[Box] = [tuple(float(v) for v in r.split(",")) for r in args.check_region]

    for image_path in images:
        image = Image.open(image_path)
        boxes_raw = detect_1a(model, image)
        row_cluster_tolerance, y_gap_tolerance = adaptive_tolerances(boxes_raw)
        boxes_merged = merge_adjacent_fragments(boxes_raw, y_gap_tolerance=y_gap_tolerance)

        if args.sweep:
            if len(regions) != 2:
                parser.error("--sweep requires exactly 2 --check-region values (2 known-distinct rows)")
            multipliers = [float(m) for m in args.sweep.split(",")]
            print(f"\n=== sweep on {image_path} (post-merge, {len(boxes_merged)} boxes) ===")
            for m in multipliers:
                swept_rows = cluster_rows(boxes_merged, row_cluster_tolerance, max_span_multiplier=m)
                row_of_region0 = next(
                    (i for i, row in enumerate(swept_rows) if any(box_overlaps_region(b, regions[0]) for b in row)),
                    None,
                )
                row_of_region1 = next(
                    (i for i, row in enumerate(swept_rows) if any(box_overlaps_region(b, regions[1]) for b in row)),
                    None,
                )
                same_row = row_of_region0 is not None and row_of_region0 == row_of_region1
                status = "FAIL (still chained together)" if same_row else "PASS (correctly separated)"
                print(f"  max_span_multiplier={m}: {len(swept_rows)} row(s) total -> {status}")
            continue

        boxes_anom = filter_anomalous_boxes(boxes_merged, row_cluster_tolerance=row_cluster_tolerance)
        boxes_final, flagged_regions = filter_contained_boxes(boxes_anom)
        gaps = detect_gaps(boxes_final, row_cluster_tolerance=row_cluster_tolerance)

        print(f"\n=== {image_path} ===")
        print(f"  raw: {len(boxes_raw)}  merged: {len(boxes_merged)}  "
              f"after filter_anomalous_boxes: {len(boxes_anom)}  "
              f"after filter_contained_boxes: {len(boxes_final)} ({len(flagged_regions)} flagged)  "
              f"gaps: {len(gaps)}")
        for g in gaps:
            print(f"    gap: {tuple(round(v, 1) for v in g)}")

        if args.image:
            for region in regions:
                overlapping = [g for g in gaps if box_overlaps_region(g, region)]
                status = "PHANTOM GAP STILL PRESENT" if overlapping else "clear"
                print(f"  check-region {region}: {status} ({len(overlapping)} overlapping gap(s))")

            if args.out:
                out_dir = Path(args.out)
                out_dir.mkdir(parents=True, exist_ok=True)
                annotate_and_save(image, boxes_final, flagged_regions, gaps, out_dir / "annotated.jpg")
                print(f"  saved annotated image to {out_dir / 'annotated.jpg'}")


if __name__ == "__main__":
    main()
