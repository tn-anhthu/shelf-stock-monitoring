"""Aggregate per-box detections into per-SKU quantities, compute inventory value,
and flag low-stock/out-of-stock SKUs — spec section 6 (Feature Spec: Depth input,
Aggregate & Price, Low-stock flag).
"""
from typing import Dict, List

LOW_STOCK_RATIO = 0.3


def aggregate_quantities(detections: List[Dict]) -> Dict[str, int]:
    quantities: Dict[str, int] = {}
    for detection in detections:
        sku_id = detection["sku_id"]
        quantities[sku_id] = quantities.get(sku_id, 0) + detection["depth"]
    return quantities


def compute_value(quantities: Dict[str, int], catalog_items: List[Dict]) -> int:
    prices = {item["sku_id"]: item["price"] for item in catalog_items}
    return sum(
        quantity * prices[sku_id]
        for sku_id, quantity in quantities.items()
        if sku_id in prices
    )


def flag_status(quantity: int, shelf_full_qty: int) -> str:
    if quantity == 0:
        return "out"
    if quantity < shelf_full_qty * LOW_STOCK_RATIO:
        return "low"
    return "ok"
