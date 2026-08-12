"""Manual review tool for gap_verify() (src/pipeline/gap_verify.py) -- runs
the real geometry pipeline (detect -> merge_adjacent_fragments ->
filter_anomalous_boxes -> filter_contained_boxes -> detect_gaps, same stages
and order as src/pipeline/scan.py::run_scan(), matching
scripts/verify_cluster_rows_fix.py) on real shelf photos, then calls
verify_gap() on EVERY candidate detect_gaps() reports -- not the filtering
verify_gaps() wrapper, since this script needs a verdict for every candidate
including the ones that would get filtered out, so a human can confirm the
filter removes the right ones (see docs/superpowers/specs/
2026-08-12-gap-detection-vlm-verify-design.md S9 for the review method and
S5 for why crops here are freshly cut from detect_gaps()'s real bboxes, never
from data/scan_viz/gap_crops/).

Costs real (mostly free-tier) OpenRouter API calls -- see the spec's S10 for
measured token/cost per call and the Gemma free-tier daily rate limit (50
req/day under $10 account credit).

Usage:
    python3 scripts/review_gap_verify.py \
        --weights sku110k_yolo26n_results/weights/best.pt \
        --out data/scan_viz/gap_verify_review

    # Single image (e.g. a cheap smoke check before running all of test1-19):
    python3 scripts/review_gap_verify.py \
        --weights sku110k_yolo26n_results/weights/best.pt \
        --image data/scan_viz/input/test13.HEIC \
        --out data/scan_viz/gap_verify_review
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pillow_heif
pillow_heif.register_heif_opener()
from PIL import Image, ImageDraw

from src.detection.train.run_trained_1a import detect_1a, load_model_1a
from src.pipeline.box_filter import filter_anomalous_boxes, filter_contained_boxes
from src.pipeline.box_merge import merge_adjacent_fragments
from src.pipeline.crop import crop_box
from src.pipeline.gap_detection import detect_gaps
from src.pipeline.gap_verify import CONTEXT_PADDING_RATIO, build_client, verify_gap
from src.pipeline.scan import adaptive_tolerances

TEST_IMAGES = [f"data/scan_viz/input/test{i}.HEIC" for i in range(1, 20)]

VERDICT_COLOR = {
    "gap": (0, 200, 0),
    "uncertain": (255, 230, 0),
    "not_gap": (220, 30, 30),
}


def annotate(image, results, out_path):
    canvas = image.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas)
    for r in results:
        x1, y1, x2, y2 = r["box"]
        color = VERDICT_COLOR[r["verdict"]]
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        label = r["verdict"].upper()
        text_y = max(0, y1 - 14)
        draw.rectangle([x1, text_y, x1 + 7 * len(label), text_y + 13], fill=color)
        draw.text((x1 + 2, text_y), label, fill=(0, 0, 0))
    canvas.save(out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=str, required=True)
    parser.add_argument("--out", type=str, default="data/scan_viz/gap_verify_review")
    parser.add_argument("--image", type=str, default=None, help="Single image; omit to run all of test1-19.")
    args = parser.parse_args()

    client = build_client()
    if client is None:
        raise SystemExit("OPENROUTER_API_KEY not set - export it or add it to .env before running this script.")

    model = load_model_1a(Path(args.weights))
    images = [args.image] if args.image else TEST_IMAGES

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    for image_path in images:
        if not Path(image_path).exists():
            print(f"skip {image_path}: not found")
            continue

        image = Image.open(image_path)
        boxes_raw = detect_1a(model, image)
        row_cluster_tolerance, y_gap_tolerance = adaptive_tolerances(boxes_raw)
        boxes_merged = merge_adjacent_fragments(boxes_raw, y_gap_tolerance=y_gap_tolerance)
        boxes_anom = filter_anomalous_boxes(boxes_merged, row_cluster_tolerance=row_cluster_tolerance)
        boxes_final, _flagged_regions, _flagged_pairs = filter_contained_boxes(boxes_anom)
        gaps = detect_gaps(boxes_final, row_cluster_tolerance=row_cluster_tolerance)

        print(f"\n=== {image_path} ===  {len(gaps)} candidate(s)")
        if not gaps:
            continue

        stem = Path(image_path).stem
        image_out_dir = out_root / stem
        image_out_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for i, box in enumerate(gaps):
            result = verify_gap(client, image, box)
            results.append(result)
            print(
                f"  candidate {i}: box={tuple(round(v) for v in box)} "
                f"verdict={result['verdict']} reason={result['reason']!r}"
            )

            crop = crop_box(image, box, padding_ratio=CONTEXT_PADDING_RATIO)
            if crop is not None:
                crop.convert("RGB").save(image_out_dir / f"candidate_{i:02d}_{result['verdict']}.jpg")

        annotate(image, results, image_out_dir / "annotated.jpg")

    print(f"\nSaved crops + annotated overlays under {out_root}/<image>/ - review by eye.")


if __name__ == "__main__":
    main()
