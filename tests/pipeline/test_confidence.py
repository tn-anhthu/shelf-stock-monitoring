from src.pipeline.confidence import is_low_confidence


def test_is_low_confidence_true_when_most_detections_are_unknown():
    detections = [{"sku_id": None}, {"sku_id": None}, {"sku_id": "choco_pie_orion"}]
    assert is_low_confidence(detections, threshold=0.5) is True


def test_is_low_confidence_false_when_most_detections_matched():
    detections = [{"sku_id": "choco_pie_orion"}, {"sku_id": "coke_330"}, {"sku_id": None}]
    assert is_low_confidence(detections, threshold=0.5) is False


def test_is_low_confidence_empty_detections_returns_true():
    # no detections in a region we expected to score -> treat as low-confidence
    assert is_low_confidence([], threshold=0.5) is True


def test_is_low_confidence_uses_default_threshold():
    detections = [{"sku_id": None}, {"sku_id": None}]
    assert is_low_confidence(detections) is True


def test_is_low_confidence_exactly_at_threshold_is_not_low_confidence():
    # 1/2 unknown == threshold -> not strictly over it, so not flagged
    detections = [{"sku_id": None}, {"sku_id": "choco_pie_orion"}]
    assert is_low_confidence(detections, threshold=0.5) is False
