"""Pure functions mapping src/pipeline/scan.py::run_scan()'s internal result
shape into the ml-service POST /predict response shape frozen by
docs/adr/0002-analyze-endpoint-schema.md. Deliberately has no dependency on
FastAPI, torch, or any model — keeps this the one part of ml-service that's
unit-testable without loading real models (see app.py for the wiring that
does need real models).
"""
from typing import Dict, List


def map_scan_result_to_response(
    scan_result: Dict,
    catalog_items: List[Dict],
    image_width: int,
    image_height: int,
) -> Dict:
    catalog_by_id = {item["sku_id"]: item for item in catalog_items}

    boxes_out = []
    low_confidence_regions = []
    box_index = 0

    for bbox, detection in zip(scan_result["boxes"], scan_result["detections"]):
        box_id = f"b{box_index}"
        box_index += 1
        sku_id = detection["sku_id"]
        is_unknown = sku_id is None
        catalog_entry = catalog_by_id.get(sku_id)

        boxes_out.append(
            {
                "box_id": box_id,
                "bbox": list(bbox),
                "type": "product",
                "sku_id": sku_id,
                "sku_name": catalog_entry["name"] if catalog_entry else None,
                "confidence": detection["confidence"],
                "is_unknown": is_unknown,
                "excluded_from_count": detection.get("excluded_from_count", False),
            }
        )
        if is_unknown:
            low_confidence_regions.append(box_id)

    for gap_bbox in scan_result["gaps"]:
        box_id = f"b{box_index}"
        box_index += 1
        boxes_out.append(
            {
                "box_id": box_id,
                "bbox": list(gap_bbox),
                "type": "gap",
                "sku_id": None,
                "sku_name": None,
                "confidence": 0.0,
                "is_unknown": False,
            }
        )

    return {
        "image": {"width": image_width, "height": image_height},
        "boxes": boxes_out,
        "warnings": {
            "low_confidence_regions": low_confidence_regions,
            "edge_crop_regions": [],
            "blur_detected": False,
        },
    }
