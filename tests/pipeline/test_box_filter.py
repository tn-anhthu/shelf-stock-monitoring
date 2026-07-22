from src.pipeline.box_filter import filter_anomalous_boxes


def test_filter_anomalous_boxes_removes_clear_outlier_in_row():
    boxes = [(0, 0, 50, 10), (60, 0, 110, 10), (120, 0, 130, 10), (140, 0, 190, 10)]
    # widths: 50, 50, 10, 50 -> avg=40, threshold=0.6*40=24 -> the width=10 box is dropped
    assert filter_anomalous_boxes(boxes) == [(0, 0, 50, 10), (60, 0, 110, 10), (140, 0, 190, 10)]


def test_filter_anomalous_boxes_keeps_all_when_row_is_even():
    boxes = [(0, 0, 50, 10), (60, 0, 110, 10), (120, 0, 170, 10)]
    assert filter_anomalous_boxes(boxes) == boxes


def test_filter_anomalous_boxes_row_with_fewer_than_two_boxes_keeps_all():
    # Two separate singleton rows (y-centers far apart) -> neither has a peer to
    # compare width against, so both are kept even though their widths differ a lot.
    boxes = [(0, 0, 10, 10), (0, 500, 50, 600)]
    assert filter_anomalous_boxes(boxes) == boxes


def test_filter_anomalous_boxes_empty_returns_empty_list():
    assert filter_anomalous_boxes([]) == []
