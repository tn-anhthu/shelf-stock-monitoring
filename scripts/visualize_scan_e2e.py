"""Visualize each stage of the real end-to-end scan pipeline (detect -> crop ->
classify) for slides/demo. Unlike scripts/run_scan_e2e.py (which only prints the
final JSON via run_scan), this script runs the same real models but keeps every
intermediate artifact so each pipeline stage is inspectable:

  <out>/0_original.jpg        - the input shelf photo, untouched
  <out>/1_annotated.jpg       - original + YOLO boxes, color-coded green/red by
                                match status (labeled sku_id + confidence), plus
                                orange boxes for detect_gaps() suspected empty gaps
                                and yellow "NEEDS REVIEW" boxes for
                                filter_contained_boxes() regions kept but flagged
                                (ambiguous containment, not a plain unknown match)
  <out>/2_crops_grid.jpg      - contact sheet of every crop_box() output in one image
  <out>/crop_XX_<status>.jpg  - each individual crop as its own file
  stdout                      - per-box detect/crop/classify trace + region-level
                                low_confidence flag (same call as scan.py uses)

Usage:
    python3 scripts/visualize_scan_e2e.py --image path/to/shelf.jpg \
        --weights runs/detect/runs/train_1a/n_2000/weights/best.pt \
        --out data/scan_viz/run1

Must run on the M4 MacBook Pro (needs mps + network access for the SigLIP2
download) — the checkpoint path above matches what's actually on disk today
(nested runs/detect/runs/train_1a/..., not runs/train_1a/... as written in some
earlier notes; run `find runs -iname best.pt` to confirm before running).

Provider is picked by the LLM_PROVIDER env var (anthropic | gemini, default
anthropic -- same switch as src/pipeline/classify.py's _escalate). The
matching API key (ANTHROPIC_API_KEY or GEMINI_API_KEY) is read from the
environment -- either export it yourself before running, or put it in a .env
file (gitignored) and it's auto-loaded via python-dotenv if that package is
installed. Never hardcode the key into this or any other file.
"""
import argparse
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import anthropic
from google import genai
from PIL import Image, ImageDraw
import pillow_heif
pillow_heif.register_heif_opener()

from src.catalog.db import get_connection, list_catalog
from src.classification.benchmark.embed_siglip2 import embed_image_siglip2, load_model_siglip2
from src.detection.train.run_trained_1a import detect_1a, load_model_1a
from src.pipeline.box_filter import filter_anomalous_boxes, filter_contained_boxes
from src.pipeline.box_merge import merge_adjacent_fragments
from src.pipeline.classify import classify_crops_parallel, load_catalog_embeddings, rank_candidates
from src.pipeline.confidence import is_low_confidence
from src.pipeline.crop import crop_box
from src.pipeline.gap_detection import detect_gaps
from src.pipeline.review_export import append_review_sheet, format_candidates
from src.pipeline.scan import adaptive_tolerances

DEFAULT_DB_PATH = "data/shelfsense.db"
DEFAULT_TOP_K = 5
DEFAULT_MAX_WORKERS = 10
REVIEW_XLSX_PATH = "data/scan_viz/review.xlsx"

# Claude Haiku 4.5 pricing (https://docs.claude.com/en/docs/about-claude/pricing), per
# million tokens — used to turn this run's summed usage into a rough dollar estimate.
HAIKU_INPUT_COST_PER_MTOK = 1.0
HAIKU_OUTPUT_COST_PER_MTOK = 5.0

# gemini-3.1-flash-lite pricing (https://ai.google.dev/gemini-api/docs/pricing,
# checked 2026-07-27), per million tokens -- NOT the same as gemini-3.5-flash-lite
# ($0.30/$2.50, used by scripts/pilot_gemini_vs_claude.py) -- update these if
# GEMINI_ESCALATION_MODEL changes to a different model.
GEMINI_INPUT_COST_PER_MTOK = 0.25
GEMINI_OUTPUT_COST_PER_MTOK = 1.50

MATCHED_COLOR = (0, 200, 0)
UNKNOWN_COLOR = (220, 30, 30)
GAP_COLOR = (255, 140, 0)
FLAGGED_COLOR = (255, 230, 0)


def annotate_and_save(
    image: Image.Image, per_box_results: list, gaps: list, flagged_regions: list, out_path: Path
) -> None:
    flagged_set = {tuple(box) for box in flagged_regions}
    canvas = image.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas)
    for r in per_box_results:
        x1, y1, x2, y2 = r["box"]
        is_flagged = tuple(r["box"]) in flagged_set
        color = FLAGGED_COLOR if is_flagged else (MATCHED_COLOR if r["sku_id"] else UNKNOWN_COLOR)
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        label = f'{r["sku_id"] or "unknown"} ({r["score"]:.2f})'
        if is_flagged:
            # Distinct from a plain "unknown" match: this box was kept but
            # flagged by filter_contained_boxes because it's an oversized box
            # whose leftover region (beyond what another box already covers)
            # has no independent detection to fall back on - ambiguous
            # containment, not a classification failure.
            label += " NEEDS REVIEW"
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


def build_crops_grid(crops: list, labels: list, out_path: Path, thumb_size: int = 150) -> None:
    if not crops:
        return
    cols = min(6, len(crops))
    rows = math.ceil(len(crops) / cols)
    label_h = 18
    grid = Image.new("RGB", (cols * thumb_size, rows * (thumb_size + label_h)), (30, 30, 30))
    draw = ImageDraw.Draw(grid)
    for i, (crop, label) in enumerate(zip(crops, labels)):
        thumb = crop.copy()
        thumb.thumbnail((thumb_size, thumb_size))
        col, row = i % cols, i // cols
        x = col * thumb_size + (thumb_size - thumb.width) // 2
        y = row * (thumb_size + label_h)
        grid.paste(thumb, (x, y))
        draw.text((col * thumb_size + 4, y + thumb_size + 2), label, fill=(255, 255, 255))
    grid.save(out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--weights", type=str, required=True)
    parser.add_argument("--db", type=str, default=DEFAULT_DB_PATH)
    parser.add_argument("--out", type=str, default="data/scan_viz/run1")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    args = parser.parse_args()

    provider = os.environ.get("LLM_PROVIDER", "anthropic")
    if provider == "gemini":
        if not os.environ.get("GEMINI_API_KEY"):
            raise SystemExit("GEMINI_API_KEY not set — export it before running this script.")
        llm_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("ANTHROPIC_API_KEY not set — export it before running this script.")
        llm_client = anthropic.Anthropic()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = get_connection(args.db)
    catalog_items = list_catalog(conn)
    catalog_embeddings = load_catalog_embeddings(catalog_items)
    print(f"Loaded {len(catalog_items)} catalog SKUs, {len(catalog_embeddings)} embeddings")

    yolo_model = load_model_1a(Path(args.weights))
    siglip_model, siglip_processor = load_model_siglip2()

    shelf_image = Image.open(args.image)
    shelf_image.convert("RGB").save(out_dir / "0_original.jpg")

    boxes = detect_1a(yolo_model, shelf_image)
    print(f"YOLO detected {len(boxes)} boxes")

    row_cluster_tolerance, y_gap_tolerance = adaptive_tolerances(boxes)
    print(f"adaptive_tolerances: row_cluster={row_cluster_tolerance:.2f}px, y_gap={y_gap_tolerance:.2f}px")

    boxes_merged = merge_adjacent_fragments(boxes, y_gap_tolerance=y_gap_tolerance)
    print(f"After merge_adjacent_fragments: {len(boxes)} -> {len(boxes_merged)} boxes")

    boxes = filter_anomalous_boxes(boxes_merged, row_cluster_tolerance=row_cluster_tolerance)
    print(f"After filter_anomalous_boxes: {len(boxes_merged)} -> {len(boxes)} boxes")

    boxes_before_containment = len(boxes)
    boxes, flagged_regions = filter_contained_boxes(boxes)
    print(
        f"After filter_contained_boxes: {boxes_before_containment} -> {len(boxes)} boxes "
        f"({len(flagged_regions)} flagged for review)"
    )

    gaps = detect_gaps(boxes, row_cluster_tolerance=row_cluster_tolerance)
    print(f"Gap detection flagged {len(gaps)} suspicious gap(s)")
    for gx1, gy1, gx2, gy2 in gaps:
        print(f"  gap: box_coords={tuple(round(v) for v in (gx1, gy1, gx2, gy2))}")

    # Phase 1 (sequential): crop + save + embed + cosine-rank candidates per
    # box. Stays sequential since embed_image_siglip2 shares one SigLIP2
    # model/GPU across boxes.
    pending = []  # (i, box, cropped, crop_status, ranked)
    for i, box in enumerate(boxes):
        cropped = crop_box(shelf_image, box)
        crop_status = "degenerate" if cropped is None else "ok"

        ranked = []
        if cropped is not None:
            crop_path = out_dir / f"crop_{i:02d}_{crop_status}.jpg"
            cropped.convert("RGB").save(crop_path)
            embedding = embed_image_siglip2(siglip_model, siglip_processor, cropped)
            ranked = rank_candidates(embedding, catalog_embeddings, top_k=args.top_k)

        pending.append((i, box, cropped, crop_status, ranked))

    # Phase 2 (parallel): verify every box's candidate shortlist with the LLM
    # concurrently — network I/O, not GPU/CPU-bound, so a thread pool is
    # enough. classify_crops_parallel preserves the input order above
    # regardless of which thread finishes first.
    llm_results = classify_crops_parallel(
        [(cropped, ranked) for _, _, cropped, _, ranked in pending],
        catalog_items,
        llm_client,
        max_workers=args.max_workers,
    )

    per_box_results = []
    crop_thumbs, crop_labels = [], []
    total_input_tokens, total_output_tokens = 0, 0
    for (i, box, cropped, crop_status, _ranked), (sku_id, score, reasoning, usage, candidates) in zip(pending, llm_results):
        per_box_results.append({
            "box": box, "sku_id": sku_id, "score": score, "crop_status": crop_status, "reasoning": reasoning,
            "candidates": candidates,
        })
        total_input_tokens += usage["input_tokens"]
        total_output_tokens += usage["output_tokens"]

        tag = sku_id or "UNKNOWN"
        print(f"  box {i:02d}: {tag:<25s} score={score:.3f}  crop={crop_status}  box_coords={tuple(round(v) for v in box)}")

        if cropped is not None:
            crop_thumbs.append(cropped)
            crop_labels.append(f"{tag} {score:.2f}")

    annotate_and_save(shelf_image, per_box_results, gaps, flagged_regions, out_dir / "1_annotated.jpg")
    build_crops_grid(crop_thumbs, crop_labels, out_dir / "2_crops_grid.jpg")

    scores = [r["score"] for r in per_box_results]
    if scores:
        region_low_conf = is_low_confidence(per_box_results)
        avg = sum(scores) / len(scores)
        unknown_count = sum(1 for r in per_box_results if r["sku_id"] is None)
        print(f"\nAvg confidence: {avg:.3f}  |  region-level low_confidence flag: {region_low_conf}")
        print(f"Per-detection unknown: {unknown_count}/{len(per_box_results)}")
    else:
        print("\nNo detections — nothing to score.")

    input_cost_per_mtok, output_cost_per_mtok = (
        (GEMINI_INPUT_COST_PER_MTOK, GEMINI_OUTPUT_COST_PER_MTOK) if provider == "gemini"
        else (HAIKU_INPUT_COST_PER_MTOK, HAIKU_OUTPUT_COST_PER_MTOK)
    )
    estimated_cost = (
        total_input_tokens / 1_000_000 * input_cost_per_mtok
        + total_output_tokens / 1_000_000 * output_cost_per_mtok
    )
    print(
        f"LLM token usage: {total_input_tokens} input, {total_output_tokens} output "
        f"-> estimated cost ${estimated_cost:.4f}"
    )

    print(f"\nSaved to {out_dir}/: 0_original.jpg, 1_annotated.jpg, 2_crops_grid.jpg, "
          f"{sum(1 for r in per_box_results if r['crop_status'] == 'ok')} individual crop files")

    review_rows = [
        {
            "index": i,
            "crop_file": f"crop_{i:02d}_ok.jpg" if r["crop_status"] == "ok" else "",
            "predicted_sku_id": r["sku_id"],
            "score": r["score"],
            "top5_candidates": format_candidates(r["candidates"]),
            "llm_reasoning": r["reasoning"],
            "correct": "",
            "true_sku_id": "",
            "depth": 1,
        }
        for i, r in enumerate(per_box_results)
    ]
    try:
        Path(REVIEW_XLSX_PATH).parent.mkdir(parents=True, exist_ok=True)
        used_sheet_name = append_review_sheet(REVIEW_XLSX_PATH, out_dir.name, review_rows)
    except RuntimeError as e:
        raise SystemExit(str(e))
    print(f"Review sheet '{used_sheet_name}' appended to {REVIEW_XLSX_PATH}")


if __name__ == "__main__":
    main()
