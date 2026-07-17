import pytest

from src.detection.benchmark.data import parse_fiftyone_detections


def test_parse_fiftyone_detections_converts_relative_to_absolute_boxes():
    detections = [
        {"bounding_box": [0.1, 0.2, 0.3, 0.4]},  # x, y, w, h relative
    ]
    boxes = parse_fiftyone_detections(detections, image_width=100, image_height=200)
    # x1 = 0.1*100=10, y1=0.2*200=40, x2=(0.1+0.3)*100=40, y2=(0.2+0.4)*200=120
    # Compared with pytest.approx: floating-point multiplication of 0.1/0.2/0.3/0.4
    # does not land on exact decimal values (e.g. (0.2+0.4)*200 == 120.00000000000001).
    assert boxes[0] == pytest.approx((10.0, 40.0, 40.0, 120.0))


def test_parse_fiftyone_detections_handles_multiple_boxes():
    detections = [
        {"bounding_box": [0.0, 0.0, 0.5, 0.5]},
        {"bounding_box": [0.5, 0.5, 0.5, 0.5]},
    ]
    boxes = parse_fiftyone_detections(detections, image_width=10, image_height=10)
    assert boxes == [(0.0, 0.0, 5.0, 5.0), (5.0, 5.0, 10.0, 10.0)]


def test_parse_fiftyone_detections_empty_list_returns_empty():
    assert parse_fiftyone_detections([], image_width=100, image_height=100) == []
