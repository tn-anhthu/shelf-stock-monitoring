from src.pipeline.aggregate import aggregate_quantities, compute_value, flag_status


def test_aggregate_quantities_sums_by_sku():
    detections = [
        {"sku_id": "choco_pie_orion", "depth": 2},
        {"sku_id": "choco_pie_orion", "depth": 3},
        {"sku_id": "coke_330", "depth": 1},
    ]
    assert aggregate_quantities(detections) == {"choco_pie_orion": 5, "coke_330": 1}


def test_aggregate_quantities_empty_returns_empty_dict():
    assert aggregate_quantities([]) == {}


def test_compute_value_multiplies_quantity_by_price():
    quantities = {"choco_pie_orion": 5, "coke_330": 2}
    catalog_items = [
        {"sku_id": "choco_pie_orion", "price": 45000},
        {"sku_id": "coke_330", "price": 10000},
    ]
    assert compute_value(quantities, catalog_items) == 5 * 45000 + 2 * 10000


def test_compute_value_skips_skus_not_in_catalog():
    quantities = {"unknown_sku": 3}
    catalog_items = [{"sku_id": "choco_pie_orion", "price": 45000}]
    assert compute_value(quantities, catalog_items) == 0


def test_flag_status_out_when_zero():
    assert flag_status(0, shelf_full_qty=10) == "out"


def test_flag_status_low_when_below_30_percent():
    assert flag_status(2, shelf_full_qty=10) == "low"


def test_flag_status_ok_when_at_or_above_30_percent():
    assert flag_status(3, shelf_full_qty=10) == "ok"
    assert flag_status(10, shelf_full_qty=10) == "ok"
