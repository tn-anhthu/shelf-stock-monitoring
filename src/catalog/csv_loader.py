"""Parse the catalog CSV (exported from the Google Sheet used to bulk-seed the
initial ~15-30 SKU catalog, per docs/specs/mvp-design.md
section 10) into plain dicts ready for image fetching and DB insertion.
"""
import csv
from typing import Dict, List


def load_catalog_rows(csv_path: str) -> List[Dict]:
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            image_urls = [
                raw[key].strip()
                for key in ("image_url_1", "image_url_2", "image_url_3")
                if raw.get(key, "").strip()
            ]
            rows.append(
                {
                    "sku_id": raw["sku_id"].strip(),
                    "name": raw["name"].strip(),
                    "price": int(raw["price"]),
                    "shelf_full_qty": int(raw["shelf_full_qty"]),
                    "image_urls": image_urls,
                }
            )
    return rows
