import json

import numpy as np

from src.catalog.db import create_tables, get_connection
from src.pipeline.box_filter import filter_anomalous_boxes
from src.pipeline.box_merge import merge_adjacent_fragments
from src.pipeline.gap_detection import detect_gaps
from src.pipeline.scan import persist_scan, run_scan


def fake_detect_fn(image):
    # 2 boxes on the "shelf"
    return [(0, 0, 10, 10), (10, 0, 20, 10)]


def fake_detect_fn_with_fragments(image):
    return [
        (0, 0, 10, 10),  # normal box
        (20, 0, 30, 10),  # normal box
        (50, 0, 60, 3),  # split-box fragment (top)
        (50, 3, 60, 6),  # split-box fragment (bottom) -> should merge with the one above
        (100, 0, 100.9, 10),  # anomalously narrow junk box -> should be filtered out
    ]


def fake_embed_fn(crop_image):
    # crop_image is unused by the fake; return a fixed vector so classify_crop
    # always matches "choco_pie_orion" (see catalog_embeddings below)
    return np.array([1.0, 0.0])


def test_run_scan_produces_quantities_value_and_flags():
    catalog_items = [
        {"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10},
    ]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=None,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=fake_detect_fn,
        embed_fn=fake_embed_fn,
    )

    assert result["quantities"] == {"choco_pie_orion": 2}
    assert result["value"] == 2 * 45000
    assert result["flags"] == {"choco_pie_orion": "low"}
    assert result["low_confidence"] is False
    assert len(result["detections"]) == 2


def test_run_scan_applies_depth_multiplier_by_box_index():
    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10}]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=None,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=fake_detect_fn,
        embed_fn=fake_embed_fn,
        depth_by_index={0: 3, 1: 1},
    )

    assert result["quantities"] == {"choco_pie_orion": 4}


def test_run_scan_merges_and_filters_boxes_before_classify_and_gaps():
    catalog_items = [
        {"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10},
    ]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=None,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=fake_detect_fn_with_fragments,
        embed_fn=fake_embed_fn,
    )

    cleaned_boxes = filter_anomalous_boxes(merge_adjacent_fragments(fake_detect_fn_with_fragments(None)))
    assert len(cleaned_boxes) == 3
    assert len(result["detections"]) == 3
    assert result["gaps"] == detect_gaps(cleaned_boxes)


def test_run_scan_includes_gaps_from_detected_boxes():
    catalog_items = [
        {"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10},
    ]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=None,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=fake_detect_fn,
        embed_fn=fake_embed_fn,
    )

    assert result["gaps"] == detect_gaps(fake_detect_fn(None))


def test_run_scan_flags_undetected_catalog_sku_as_out():
    catalog_items = [
        {"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10},
        {"sku_id": "coke_330", "name": "Coke", "price": 12000, "shelf_full_qty": 20},
    ]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=None,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=fake_detect_fn,
        embed_fn=fake_embed_fn,
    )

    assert result["flags"]["coke_330"] == "out"


def test_run_scan_flags_low_confidence_when_no_catalog_match():
    result = run_scan(
        image=None,
        catalog_items=[],
        catalog_embeddings=[],
        detect_fn=fake_detect_fn,
        embed_fn=fake_embed_fn,
    )
    assert result["low_confidence"] is True
    assert result["quantities"] == {}


def test_persist_scan_writes_scan_history_and_inventory_rows(tmp_path):
    db_path = tmp_path / "shelfsense.db"
    conn = get_connection(str(db_path))
    create_tables(conn)

    scan_result = {
        "detections": [{"sku_id": "choco_pie_orion", "confidence": 1.0}],
        "low_confidence": False,
        "quantities": {"choco_pie_orion": 2},
        "value": 90000,
        "flags": {"choco_pie_orion": "low"},
    }

    persist_scan(
        conn,
        image_path="data/scans/1.jpg",
        scan_result=scan_result,
        catalog_items=[{"sku_id": "choco_pie_orion", "price": 45000}],
    )

    scan_rows = conn.execute("SELECT image_path, raw_result FROM scan_history").fetchall()
    assert len(scan_rows) == 1
    assert scan_rows[0][0] == "data/scans/1.jpg"
    assert json.loads(scan_rows[0][1])["quantities"] == {"choco_pie_orion": 2}

    inventory_rows = conn.execute("SELECT sku_id, quantity, value, status FROM inventory").fetchall()
    assert inventory_rows == [("choco_pie_orion", 2, 90000, "low")]
