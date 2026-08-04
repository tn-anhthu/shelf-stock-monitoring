from mapping import map_scan_result_to_response


CATALOG_ITEMS = [
    {"sku_id": "choco_pie_org", "name": "Bánh chocopie Orion hộp 217.8g (6 cái)"},
    {"sku_id": "karo_org", "name": "Bánh trứng tươi chà bông Karo Richy túi 156g"},
]


def test_maps_known_product_box():
    scan_result = {
        "boxes": [(10, 10, 110, 210)],
        "detections": [{"sku_id": "choco_pie_org", "confidence": 0.94, "depth": 1}],
        "gaps": [],
    }

    result = map_scan_result_to_response(scan_result, CATALOG_ITEMS, image_width=1200, image_height=900)

    assert result["image"] == {"width": 1200, "height": 900}
    assert result["boxes"] == [
        {
            "box_id": "b0",
            "bbox": [10, 10, 110, 210],
            "type": "product",
            "sku_id": "choco_pie_org",
            "sku_name": "Bánh chocopie Orion hộp 217.8g (6 cái)",
            "confidence": 0.94,
            "is_unknown": False,
        }
    ]
    assert result["warnings"] == {"low_confidence_regions": [], "edge_crop_regions": [], "blur_detected": False}


def test_maps_unknown_product_box_into_low_confidence_regions():
    scan_result = {
        "boxes": [(230, 10, 330, 210)],
        "detections": [{"sku_id": None, "confidence": 0.55, "depth": 1}],
        "gaps": [],
    }

    result = map_scan_result_to_response(scan_result, CATALOG_ITEMS, image_width=1200, image_height=900)

    assert result["boxes"] == [
        {
            "box_id": "b0",
            "bbox": [230, 10, 330, 210],
            "type": "product",
            "sku_id": None,
            "sku_name": None,
            "confidence": 0.55,
            "is_unknown": True,
        }
    ]
    assert result["warnings"]["low_confidence_regions"] == ["b0"]


def test_maps_gap_boxes_with_no_sku_and_continues_box_id_sequence():
    scan_result = {
        "boxes": [(10, 10, 110, 210)],
        "detections": [{"sku_id": "choco_pie_org", "confidence": 0.94, "depth": 1}],
        "gaps": [(800, 40, 980, 420)],
    }

    result = map_scan_result_to_response(scan_result, CATALOG_ITEMS, image_width=1200, image_height=900)

    assert result["boxes"][1] == {
        "box_id": "b1",
        "bbox": [800, 40, 980, 420],
        "type": "gap",
        "sku_id": None,
        "sku_name": None,
        "confidence": 0.0,
        "is_unknown": False,
    }
    # gap boxes never count toward low_confidence_regions
    assert result["warnings"]["low_confidence_regions"] == []


def test_multiple_products_get_sequential_box_ids():
    scan_result = {
        "boxes": [(10, 10, 110, 210), (120, 10, 220, 210)],
        "detections": [
            {"sku_id": "choco_pie_org", "confidence": 0.94, "depth": 1},
            {"sku_id": "karo_org", "confidence": 0.89, "depth": 1},
        ],
        "gaps": [],
    }

    result = map_scan_result_to_response(scan_result, CATALOG_ITEMS, image_width=1200, image_height=900)

    assert [b["box_id"] for b in result["boxes"]] == ["b0", "b1"]
    assert [b["sku_id"] for b in result["boxes"]] == ["choco_pie_org", "karo_org"]
