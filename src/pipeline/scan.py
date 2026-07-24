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
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

from src.catalog.db import insert_inventory_records, insert_scan_history
from src.pipeline.aggregate import aggregate_quantities, compute_value, flag_status
from src.pipeline.box_filter import filter_anomalous_boxes, filter_contained_boxes
from src.pipeline.box_merge import merge_adjacent_fragments
from src.pipeline.classify import classify_crops_parallel, rank_candidates
from src.pipeline.confidence import is_low_confidence
from src.pipeline.crop import crop_box
from src.pipeline.gap_detection import detect_gaps

CONFIDENCE_THRESHOLD = 0.5


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
    boxes = merge_adjacent_fragments(boxes)
    boxes = filter_anomalous_boxes(boxes)
    boxes, flagged_regions = filter_contained_boxes(boxes)
    gaps = detect_gaps(boxes)

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
