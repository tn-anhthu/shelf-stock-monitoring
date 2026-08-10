"""End-to-end scan orchestrator: detect boxes -> classify each box against the
catalog -> flag low-confidence -> aggregate quantities/value/stock flags ->
persist the confirmed result. This is the module the Streamlit/Gradio UI (a
later, separate plan for Week 3-4) calls directly for Path 1/Path 2 of
docs/superpowers/specs/2026-07-20-shelfsense-mvp-design.md section 7.

Per that spec's General A/C: results from run_scan() are a DRAFT. Only
persist_scan() (called after the employee confirms in the UI) writes to
inventory — run_scan() itself never writes to the database.
"""
import json
import statistics
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

from src.catalog.db import insert_inventory_records, insert_scan_history
from src.detection.benchmark.metrics import Box
from src.pipeline.aggregate import aggregate_quantities, compute_value, flag_status
from src.pipeline.box_filter import filter_anomalous_boxes, filter_contained_boxes
from src.pipeline.box_merge import merge_adjacent_fragments
from src.pipeline.classify import classify_crops_parallel, rank_candidates
from src.pipeline.confidence import is_low_confidence
from src.pipeline.crop import crop_box
from src.pipeline.gap_detection import detect_gaps

CONFIDENCE_THRESHOLD = 0.5

# Re-calibrated 2026-08-10 via scripts/calibrate_adaptive_tolerances.py against
# sku110k_yolo26n_results/weights/best.pt (YOLO26n) — the checkpoint
# ml-service/app.py now serves after the YOLOv8n->YOLO26n migration. The
# YOLO26n chapter is at the bottom of this block; the two paragraphs below are
# the retained history of the `full` -> `n_2000` calibrations, kept because
# they document *why* a margin measured against one checkpoint's box positions
# can't be assumed to transfer to another's.
#
# Calibrated 2026-08-04 via scripts/calibrate_adaptive_tolerances.py against
# runs/detect/runs/train_1a/n_2000/weights/best.pt — the official checkpoint
# per docs/detection-notes/detection-log.md's "Quyết định cuối cùng" — on the
# 5 raw (uncropped) test images. See
# docs/superpowers/specs/2026-08-04-adaptive-box-tolerance-design.md for the
# original design (that doc still shows numbers from the first calibration
# run, see next paragraph — treat this comment as current, that doc as
# historical).
#
# An earlier version of these two constants (0.044584 / 0.008584) was
# calibrated against runs/detect/runs/train_1a/full/weights/best.pt by
# mistake — the same checkpoint mix-up that had ml-service/app.py's
# WEIGHTS_PATH pointing at `full` instead of `n_2000` (both fixed together,
# 2026-08-04). Because these ratios scale with *this checkpoint's* detected
# box heights, a safety margin measured against one checkpoint's box
# positions doesn't transfer to another: n_2000 detects test3's boxes at a
# meaningfully different scale (519.9px median height vs full's ~450.9px),
# so the danger-zone numbers below had to be re-measured from scratch
# against real n_2000 detections, not just re-derived from the old ones.
#
# Includes a 0.87 safety margin below the raw pooled-median ratio (0.051799,
# pooled_median=386.1px across all 5 images). At test3's n_2000 scale
# (519.9px median height) this lands row_cluster_tolerance at ~23.4px.
# Verified directly against real cluster_rows() behavior (not just ratio
# arithmetic) by sweeping tolerance 1px-120px on all 5 calibration images,
# looking for the specific failure this margin exists to prevent: many rows
# collapsing into one dominant row (a jump in max row size of 3+ boxes in a
# single step), which is what produced the phantom-gap-spanning-a-shelf-row
# bug this margin was originally written against (found on test3 with the
# `full` checkpoint, between 21.0px-safe and 21.5px-danger). That specific
# danger zone does not reproduce with n_2000's box positions: test3's real
# jump is now at 74.5px (~51px above the calibrated tolerance), test1's is at
# 24.5px (~5.6px above), and test2/test4/test5 show no such jump anywhere in
# the swept range. (Below that: small single-box reassignments between
# adjacent rows happen every ~0.3-2px more or less regardless of tolerance
# choice — inherent to continuous, closely-spaced box gaps across 40-95
# boxes per image, not a sign of approaching danger. Distance to the
# *nearest* flip of any kind is not a meaningful safety metric here; distance
# to the nearest *severe* one is.)
#
# --- YOLO26n chapter (2026-08-10) ---
# Re-measured from scratch against real YOLO26n detections, same methodology,
# because the migration changed both box scale and box *count*:
#
#     image   n_2000 boxes / median h      YOLO26n boxes / median h
#     test1   60 / 420.5px                 56 / 435.7px
#     test2   95 / 344.8px                 88 / 340.3px
#     test3   54 / 519.9px                 37 / 566.9px   <- -31% boxes, +9.0% scale
#     test4   39 / 711.5px                 39 / 715.7px
#     test5   60 / 293.2px                 51 / 302.9px
#     pooled  308 / 386.1px                271 / 404.2px  <- +4.7% scale
#
# The pooled median moved only +4.7%, which on its own would have justified
# light-touch verification. The full re-sweep was done anyway because test3 —
# the single image both danger zones were originally measured on — lost 31% of
# its boxes. The danger boundary is a function of box *positions*, not of the
# pooled median, so a 4.7% pooled shift is not evidence that the boundary
# stayed put when a third of that image's boxes disappeared.
#
# New raw ratio 20.0 / 404.2 = 0.049482, times the same 0.87 margin = 0.043050.
# Sweeping row_cluster_tolerance 1.0-120.0px in 0.5px steps against real
# cluster_rows() on YOLO26n's post-merge boxes, looking for the same severe
# signature (max row size jumping 3+ boxes in one step): **no severe jump
# occurs above the calibrated tolerance on any of the 5 images, anywhere up to
# 120px.** That is strictly safer than n_2000, whose tightest margin was test1
# at only +5.55px (jump at 24.5px vs 18.95px calibrated). YOLO26n's remaining
# jumps all sit *below* the calibrated tolerance (test1 5.5px and 16.0px,
# test2 9.0px, test3 11.5px, test4 4.0px and 11.5px) — those are already
# passed through in normal operation and are not a boundary being approached.
#
# The sweep harness was validated before being trusted: re-run against n_2000's
# cached detections it reproduces this block's own historical numbers — test3's
# jump at 74.5px (+51.07px above calibrated, matching the "~51px" cited above)
# and test1's at 24.5px (+5.55px, matching "~5.6px above").
ROW_CLUSTER_TOLERANCE_RATIO = 0.043050
# Includes a 0.67 safety margin below the raw pooled-median ratio (0.012950).
# At test3's n_2000 scale this lands y_gap_tolerance at ~4.51px. Re-verified
# the same way as ROW_CLUSTER_TOLERANCE_RATIO above, but against real
# merge_adjacent_fragments() output: swept tolerance 0.5px-150px on all 5
# images looking for the first real fragment-merge event (the failure mode
# this tolerance guards against — see historical note below). With n_2000's
# box positions, test3's first merge is at 38.3px (~33.8px above the
# calibrated tolerance); the tightest across all 5 images is test2 at 6.5px
# (~3.5px above). All comfortably clear.
#
# (Historical note: the original tuning — done against the `full` checkpoint
# — found this same test3 photo had a real ~5.1px gap between two separate,
# correctly-classified stacked Yakult 5-packs, at risk of being wrongly
# merged, and iterated the margin factor specifically to stay clear of that
# value. That measurement was tied to `full`'s box positions and hasn't been
# re-verified against n_2000's; the merge-event sweep above (which found no
# merge until 38.3px) is the up-to-date safety check. The other historical
# floor still holds regardless of checkpoint: the real fragment case in
# tests/pipeline/test_box_merge.py::test_merge_adjacent_fragments_merges_real_measured_split_case
# measured y_gap=-1.7, i.e. the fragments actually overlap in y — so there's
# no meaningful floor pushing this ratio up.)
#
# --- YOLO26n chapter (2026-08-10) ---
# New raw ratio 5.0 / 404.2 = 0.012371, times the same 0.67 margin = 0.008288.
# Re-swept 0.5-150.0px in 0.1px steps against real merge_adjacent_fragments()
# on YOLO26n's detections, looking for the first tolerance at which ANY merge
# fires. Calibrated tolerance vs first merge event, per image:
#
#     test1  3.61px calibrated  ->  first merge 13.0px   (+9.39px)
#     test2  2.82px calibrated  ->  first merge  6.0px   (+3.18px)  <- tightest
#     test3  4.70px calibrated  ->  first merge 26.8px   (+22.10px)
#     test4  5.93px calibrated  ->  no merge anywhere <=150px
#     test5  2.51px calibrated  ->  no merge anywhere <=150px
#
# The tightest margin (test2, +3.18px) is marginally better than n_2000's
# equivalent (+3.41px at 2.99px calibrated vs a 6.4px first merge — same image,
# same binding constraint), so the migration does not tighten this bound.
#
# On the historical Yakult case: the ~5.1px stacked-5-pack gap described above
# does not reproduce under YOLO26n, just as it no longer reproduced under
# n_2000. test3's tightest merge-*eligible* pair (x-overlap >=0.8 AND at least
# one box aspect-anomalous, i.e. all three conditions merge_adjacent_fragments
# actually requires) is 26.75px under YOLO26n and 38.15px under n_2000. In the
# region the old bug was found in (600,2400,1150,2850), n_2000 emitted 5
# heavily mutually-overlapping boxes where YOLO26n emits 1 — consistent with
# the migration's "fewer boxes = fewer duplicates" expectation rather than lost
# detections. test3 does contain a 1.43px-gap pair at the left image edge
# (x≈0-120), but both of its boxes have normal aspect ratio, so the
# aspect-anomaly condition rejects it at every tolerance — it can never merge.
#
# Note on why these constants moved at all: the *previous* values (0.045065 /
# 0.008676) were re-swept against YOLO26n's boxes too and are also safe (no
# severe row jump anywhere; test2 y-gap margin +3.05px). They were updated not
# to fix a live hazard but to keep the constants reproducible from the
# checkpoint actually deployed — leaving ratios derived from one checkpoint's
# pooled median in place while serving another is precisely the `full`-vs-
# `n_2000` mix-up documented at the top of this block.
Y_GAP_TOLERANCE_RATIO = 0.008288


def adaptive_tolerances(boxes: List[Box]) -> Tuple[float, float]:
    """Return (row_cluster_tolerance, y_gap_tolerance) scaled to the median
    detected-box height in this image, instead of a hardcoded absolute pixel
    value — so results don't degrade when the input image's resolution
    changes (e.g. the UI's manual CropStep). Falls back to the historical
    absolute values (20.0, 5.0) when fewer than 2 boxes are detected: there's
    no meaningful median to compute, and every caller of these tolerances
    already skips the comparison entirely when len(boxes) < 2, so the
    fallback value here is never actually exercised — it only keeps the
    return type consistent.
    """
    if len(boxes) < 2:
        return 20.0, 5.0
    median_height = statistics.median(b[3] - b[1] for b in boxes)
    return (
        ROW_CLUSTER_TOLERANCE_RATIO * median_height,
        Y_GAP_TOLERANCE_RATIO * median_height,
    )


def run_scan(
    image,
    catalog_items: List[Dict],
    catalog_embeddings,
    detect_fn: Callable,
    embed_fn: Callable,
    llm_client,
    depth_by_index: Optional[Dict[int, int]] = None,
    top_k: int = 5,
    images_dir: str = "data/catalog/images",
    max_workers: int = 10,
) -> Dict:
    depth_by_index = depth_by_index or {}

    boxes = detect_fn(image)
    row_cluster_tolerance, y_gap_tolerance = adaptive_tolerances(boxes)
    boxes = merge_adjacent_fragments(boxes, y_gap_tolerance=y_gap_tolerance)
    boxes = filter_anomalous_boxes(boxes, row_cluster_tolerance=row_cluster_tolerance)
    boxes, flagged_regions, flagged_pairs = filter_contained_boxes(boxes)
    gaps = detect_gaps(boxes, row_cluster_tolerance=row_cluster_tolerance)

    # Phase 1 (sequential): crop + embed + cosine-rank candidates per box.
    # Stays sequential because embed_fn shares the SigLIP2 model/GPU across
    # boxes; a degenerate crop (box.crop_box returns None) is resolved here
    # directly without ever touching embed_fn or the LLM.
    detections: List[Optional[Dict]] = [None] * len(boxes)
    pending: List[Tuple[int, int, object, List[Tuple[str, float]]]] = []
    for i, box in enumerate(boxes):
        depth = depth_by_index.get(i, 1)
        cropped = crop_box(image, box)
        if cropped is None:
            detections[i] = {
                "sku_id": None,
                "confidence": 0.0,
                "depth": depth,
                "excluded_from_count": False,
                "needs_review": False,
            }
            continue

        # embed_fn(PIL.Image) -> np.ndarray — same contract as
        # src/catalog/build_embeddings.py::build_sku_embedding uses for catalog
        # reference images, now that run_scan crops the region itself instead
        # of leaving that to embed_fn.
        crop_embedding = embed_fn(cropped)
        ranked = rank_candidates(crop_embedding, catalog_embeddings, top_k=top_k)
        pending.append((i, depth, cropped, ranked))

    # Phase 2 (parallel): verify each pending box's candidates with the LLM —
    # network I/O, not GPU/CPU-bound, so a thread pool is enough. Order is
    # preserved by classify_crops_parallel regardless of thread completion
    # order, which matters here since `i` drives depth_by_index/detections.
    llm_results = classify_crops_parallel(
        [(cropped, ranked) for _, _, cropped, ranked in pending],
        catalog_items,
        llm_client,
        images_dir=images_dir,
        max_workers=max_workers,
    )
    # reasoning/usage are discarded here — reasoning is for human review via
    # scripts/visualize_scan_e2e.py + data/scan_viz/review.xlsx, and usage
    # (token cost tracking) is aggregated there too; neither is persisted to
    # scan_history/inventory.
    for (i, depth, _, _), (sku_id, score, _reasoning, _usage, _ranked) in zip(pending, llm_results):
        detections[i] = {
            "sku_id": sku_id,
            "confidence": score,
            "depth": depth,
            "excluded_from_count": False,
            "needs_review": False,
        }

    # filter_contained_boxes flags NEEDS REVIEW pairs at the geometry level,
    # before classify has run - it can't know which of the two represents the
    # same physical item more reliably. Now that detections carry confidence,
    # resolve each pair here: keep the higher-confidence box in the count,
    # exclude the other. The excluded box is still kept in `detections` (never
    # deleted), but the UI now only draws it (a purple "needs review" border)
    # when needs_review is True; a same-SKU excluded box is hidden from the
    # overlay entirely - see
    # docs/superpowers/specs/2026-08-10-hide-same-sku-purple-box-design.md.
    box_position = {box: i for i, box in enumerate(boxes)}
    for parent, child in flagged_pairs:
        parent_i, child_i = box_position[parent], box_position[child]
        # Tie: default to excluding the child, keeping the parent (a
        # full-package box is usually a more complete representation) - ties
        # are effectively never hit with real (float) confidence scores, so
        # this is just a deterministic tie-break, not a load-bearing assumption.
        if detections[child_i]["confidence"] <= detections[parent_i]["confidence"]:
            loser_i, winner_i = child_i, parent_i
        else:
            loser_i, winner_i = parent_i, child_i
        detections[loser_i]["excluded_from_count"] = True
        # needs_review is only True when the excluded box's SKU actually
        # disagrees with the surviving box's SKU (see
        # docs/superpowers/specs/2026-08-10-hide-same-sku-purple-box-design.md)
        # -- the common case (both boxes agree on the same SKU, e.g. a
        # package photo + its own printed mascot both matching the same
        # product) doesn't need a human to look at it. OR'd (not overwritten)
        # against any prior value: filter_contained_boxes can emit multiple
        # pairs naming the same parent (one per swallowed child), so a box
        # already flagged True by an earlier pair must stay True even if a
        # later pair agrees on SKU - otherwise that later pair would silently
        # erase a real conflict already found.
        detections[loser_i]["needs_review"] = (
            detections[loser_i]["needs_review"]
            or detections[loser_i]["sku_id"] != detections[winner_i]["sku_id"]
        )

    low_confidence = is_low_confidence(detections, threshold=CONFIDENCE_THRESHOLD)

    matched_detections = [
        d for d in detections if d["sku_id"] is not None and not d["excluded_from_count"]
    ]
    quantities = aggregate_quantities(matched_detections)
    value = compute_value(quantities, catalog_items)

    flags = {
        item["sku_id"]: flag_status(quantities.get(item["sku_id"], 0), item["shelf_full_qty"])
        for item in catalog_items
    }

    return {
        "boxes": boxes,
        "detections": detections,
        "low_confidence": low_confidence,
        "quantities": quantities,
        "value": value,
        "flags": flags,
        "gaps": gaps,
        "flagged_regions": flagged_regions,
    }


def persist_scan(conn, image_path: str, scan_result: Dict, catalog_items: List[Dict]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    insert_scan_history(
        conn,
        image_path=image_path,
        raw_result=json.dumps(scan_result),
        confirmed_result=None,
        created_at=now,
    )

    prices = {item["sku_id"]: item["price"] for item in catalog_items}
    records = [
        {
            "sku_id": sku_id,
            "quantity": quantity,
            "value": quantity * prices.get(sku_id, 0),
            "status": scan_result["flags"].get(sku_id, "ok"),
        }
        for sku_id, quantity in scan_result["quantities"].items()
    ]
    insert_inventory_records(conn, records=records, scanned_at=now)
