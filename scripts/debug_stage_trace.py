"""Trace box counts/coordinates through each detect-pipeline stage (raw YOLO ->
merge_adjacent_fragments -> filter_anomalous_boxes -> filter_contained_boxes)
restricted to a region of interest, to find which stage first produced/changed
a suspicious box -- e.g. deciding whether a NEEDS REVIEW oversized box (flagged
by filter_contained_boxes) already existed as a single raw YOLO detection (a
detector limitation) or was created by merge_adjacent_fragments combining two
genuinely separate raw boxes (a merge-logic bug).

Only runs YOLO + the pure-geometry pipeline stages -- no SigLIP2/LLM, so it's
fast and free. filter_contained_boxes's own flagged_boxes return value is the
ground truth for "where is the NEEDS REVIEW box", no guessing/visual-inspection
needed to find it; crops are saved only so a human can eyeball confirm what
product(s) are inside.

Usage:
    # Region-scoped (verbose per-stage box listing + crops), when you already
    # know roughly where the suspicious box is:
    python3 scripts/debug_stage_trace.py --image path/to/shelf.jpg \
        --weights runs/detect/runs/train_1a/n_2000/weights/best.pt \
        --region 600,2400,1150,2850 \
        --out data/scan_viz/test1_stage_trace

    # Whole-image scan (no --region): only stage box counts + every flagged
    # NEEDS REVIEW box's raw-YOLO provenance + a saved crop of each, since you
    # don't know in advance where (or whether) any flagged boxes are:
    python3 scripts/debug_stage_trace.py --image path/to/shelf.jpg \
        --weights runs/detect/runs/train_1a/n_2000/weights/best.pt \
        --out data/scan_viz/test2_stage_trace
"""
import argparse
import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pillow_heif
pillow_heif.register_heif_opener()
from PIL import Image

from src.detection.benchmark.metrics import Box, compute_iou, containment_ratio
from src.detection.train.run_trained_1a import detect_1a, load_model_1a
from src.pipeline.box_filter import filter_anomalous_boxes, filter_contained_boxes
from src.pipeline.box_merge import merge_adjacent_fragments


def box_overlaps_region(box: Box, region: Box) -> bool:
    x1, y1, x2, y2 = box
    rx1, ry1, rx2, ry2 = region
    return not (x2 <= rx1 or x1 >= rx2 or y2 <= ry1 or y1 >= ry2)


def print_stage(name: str, all_boxes: List[Box], region: Box) -> List[Box]:
    in_region = [b for b in all_boxes if box_overlaps_region(b, region)]
    print(f"\n=== {name}: {len(all_boxes)} total box(es), {len(in_region)} overlapping region {region} ===")
    for b in in_region:
        w, h = b[2] - b[0], b[3] - b[1]
        print(f"  {tuple(round(v, 1) for v in b)}  (w={w:.0f}, h={h:.0f})")
    return in_region


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--weights", type=str, required=True)
    parser.add_argument(
        "--region", type=str, default=None,
        help="Optional x1,y1,x2,y2 region of interest to filter per-stage box "
             "listing/crops down to. Omit to scan the whole image instead: stage "
             "listing collapses to counts only, and only flagged NEEDS REVIEW "
             "boxes get detailed provenance + a crop each.",
    )
    parser.add_argument("--out", type=str, default=None, help="If set, saves crops (region boxes per stage, or flagged boxes in whole-image mode)")
    args = parser.parse_args()

    yolo_model = load_model_1a(Path(args.weights))
    shelf_image = Image.open(args.image)

    whole_image_mode = args.region is None
    region: Box = (
        (0.0, 0.0, float(shelf_image.width), float(shelf_image.height))
        if whole_image_mode else tuple(float(v) for v in args.region.split(","))
    )

    boxes_raw = detect_1a(yolo_model, shelf_image)
    boxes_merged = merge_adjacent_fragments(boxes_raw)
    boxes_anom = filter_anomalous_boxes(boxes_merged)
    boxes_final, flagged = filter_contained_boxes(boxes_anom)

    if whole_image_mode:
        print(f"1. raw YOLO (detect_1a): {len(boxes_raw)} box(es)")
        print(f"2. after merge_adjacent_fragments: {len(boxes_merged)} box(es)")
        print(f"3. after filter_anomalous_boxes: {len(boxes_anom)} box(es)")
        print(f"4. after filter_contained_boxes: {len(boxes_final)} kept, {len(flagged)} flagged NEEDS REVIEW")
        raw_in_region = merged_in_region = anom_in_region = final_in_region = []
    else:
        raw_in_region = print_stage("1. raw YOLO (detect_1a)", boxes_raw, region)
        merged_in_region = print_stage("2. after merge_adjacent_fragments", boxes_merged, region)
        anom_in_region = print_stage("3. after filter_anomalous_boxes", boxes_anom, region)
        final_in_region = print_stage("4. after filter_contained_boxes (kept)", boxes_final, region)

    flagged_in_region = flagged if whole_image_mode else [b for b in flagged if box_overlaps_region(b, region)]
    print(f"\n=== flagged (NEEDS REVIEW) box(es): {len(flagged_in_region)} ===")
    for b in flagged_in_region:
        print(f"  {tuple(round(v, 1) for v in b)}")

    # For each flagged box in the region, check whether raw YOLO already had a
    # separate box for the "leftover" area (the part not covered by the
    # flagged box's contained child) -- if yes, root cause is
    # merge_adjacent_fragments merging two real raw boxes; if the flagged box
    # itself already appears (or something within compute_iou~1.0 of it)
    # directly in boxes_raw, root cause is the YOLO detector itself.
    for fb in flagged_in_region:
        print(f"\n--- Provenance check for flagged box {tuple(round(v, 1) for v in fb)} ---")
        best_raw_match = max(boxes_raw, key=lambda rb: compute_iou(rb, fb))
        iou = compute_iou(best_raw_match, fb)
        print(f"  Best-matching raw YOLO box: {tuple(round(v, 1) for v in best_raw_match)} (IoU={iou:.3f})")
        if iou > 0.9:
            print("  -> This box already existed in raw YOLO output nearly unchanged: "
                  "NOT created by merge_adjacent_fragments.")
        else:
            print("  -> No raw YOLO box closely matches this flagged box's full extent: "
                  "likely assembled/altered by merge_adjacent_fragments.")

    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        if whole_image_mode:
            for i, b in enumerate(flagged_in_region):
                x1, y1, x2, y2 = (max(0, v) for v in b)
                crop = shelf_image.convert("RGB").crop((x1, y1, x2, y2))
                crop.save(out_dir / f"flagged_box{i}.jpg")
            print(f"\nSaved {len(flagged_in_region)} flagged-box crop(s) to {out_dir}/")
        else:
            stages = [
                ("1_raw", raw_in_region),
                ("2_merged", merged_in_region),
                ("3_anom", anom_in_region),
                ("4_final", final_in_region),
            ]
            for stage_name, region_boxes in stages:
                for i, b in enumerate(region_boxes):
                    x1, y1, x2, y2 = (max(0, v) for v in b)
                    crop = shelf_image.convert("RGB").crop((x1, y1, x2, y2))
                    crop.save(out_dir / f"{stage_name}_box{i}.jpg")
            print(f"\nSaved per-stage region crops to {out_dir}/")


if __name__ == "__main__":
    main()
