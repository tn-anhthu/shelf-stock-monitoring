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

# Calibrated 2026-08-04 via scripts/calibrate_adaptive_tolerances.py against
# the 5 raw (uncropped) test images — see
# docs/superpowers/specs/2026-08-04-adaptive-box-tolerance-design.md.
ROW_CLUSTER_TOLERANCE_RATIO = 0.051246
Y_GAP_TOLERANCE_RATIO = 0.012812


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
    roi_crop_fn: Optional[Callable] = None,
    depth_by_index: Optional[Dict[int, int]] = None,
    top_k: int = 5,
    images_dir: str = "data/catalog/images",
    max_workers: int = 10,
) -> Dict:
    depth_by_index = depth_by_index or {}

    # ROI-crop preprocessing (docs/specs/mvp-design.md section 7): strip out
    # neighboring shelves/background that sit entirely inside the frame, before
    # YOLO ever sees the image. Optional and off by default (None) so callers
    # that don't inject it (and every existing test) get the pre-2026-07-28
    # behavior unchanged. roi_crop_fn must never raise — src/pipeline/roi_crop.py's
    # crop_to_roi already catches segmentation failures and returns the original
    # image with a reason instead; this is just the wiring point, not the
    # fallback logic itself.
    roi_crop_applied, roi_crop_reason, roi_crop_bbox = False, "disabled", None
    if roi_crop_fn is not None:
        roi_result = roi_crop_fn(image)
        image = roi_result.image
        roi_crop_applied = roi_result.applied
        roi_crop_reason = roi_result.reason
        roi_crop_bbox = roi_result.bbox

    boxes = detect_fn(image)
    row_cluster_tolerance, y_gap_tolerance = adaptive_tolerances(boxes)
    boxes = merge_adjacent_fragments(boxes, y_gap_tolerance=y_gap_tolerance)
    boxes = filter_anomalous_boxes(boxes, row_cluster_tolerance=row_cluster_tolerance)
    boxes, flagged_regions = filter_contained_boxes(boxes)
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
            detections[i] = {"sku_id": None, "confidence": 0.0, "depth": depth}
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
        detections[i] = {"sku_id": sku_id, "confidence": score, "depth": depth}

    low_confidence = is_low_confidence(detections, threshold=CONFIDENCE_THRESHOLD)

    matched_detections = [d for d in detections if d["sku_id"] is not None]
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
        "roi_crop": {
            "applied": roi_crop_applied,
            "reason": roi_crop_reason,
            "bbox": roi_crop_bbox,
        },
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
