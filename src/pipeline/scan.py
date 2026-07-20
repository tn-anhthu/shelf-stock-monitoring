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
from typing import Callable, Dict, List, Optional

from src.catalog.db import insert_inventory_records, insert_scan_history
from src.pipeline.aggregate import aggregate_quantities, compute_value, flag_status
from src.pipeline.classify import classify_crop
from src.pipeline.confidence import is_low_confidence

CONFIDENCE_THRESHOLD = 0.5


def run_scan(
    image,
    catalog_items: List[Dict],
    catalog_embeddings,
    detect_fn: Callable,
    embed_fn: Callable,
    depth_by_index: Optional[Dict[int, int]] = None,
) -> Dict:
    depth_by_index = depth_by_index or {}
    boxes = detect_fn(image)

    detections = []
    scores = []
    for i, box in enumerate(boxes):
        # Week 3-4 UI crops the real image region for `box`; this pipeline module
        # only needs whatever embed_fn returns for that region, so it accepts the
        # box/image pair opaquely rather than performing the crop itself.
        crop_embedding = embed_fn((image, box))
        sku_id, score = classify_crop(crop_embedding, catalog_embeddings)
        scores.append(score)
        depth = depth_by_index.get(i, 1)
        detections.append({"sku_id": sku_id, "confidence": score, "depth": depth})

    low_confidence = is_low_confidence(scores, threshold=CONFIDENCE_THRESHOLD)

    matched_detections = [d for d in detections if d["sku_id"] is not None]
    quantities = aggregate_quantities(matched_detections)
    value = compute_value(quantities, catalog_items)

    shelf_full_qty_by_sku = {item["sku_id"]: item["shelf_full_qty"] for item in catalog_items}
    flags = {
        sku_id: flag_status(quantity, shelf_full_qty_by_sku[sku_id])
        for sku_id, quantity in quantities.items()
        if sku_id in shelf_full_qty_by_sku
    }

    return {
        "detections": detections,
        "low_confidence": low_confidence,
        "quantities": quantities,
        "value": value,
        "flags": flags,
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
