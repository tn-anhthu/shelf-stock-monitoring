from src.detection.benchmark.metrics import (
    compute_iou,
    match_boxes,
    compute_precision_recall,
    aggregate_precision_recall,
)


def test_compute_iou_identical_boxes_returns_one():
    box = (0.0, 0.0, 10.0, 10.0)
    assert compute_iou(box, box) == 1.0


def test_compute_iou_no_overlap_returns_zero():
    box_a = (0.0, 0.0, 10.0, 10.0)
    box_b = (20.0, 20.0, 30.0, 30.0)
    assert compute_iou(box_a, box_b) == 0.0


def test_compute_iou_partial_overlap():
    box_a = (0.0, 0.0, 10.0, 10.0)
    box_b = (5.0, 0.0, 15.0, 10.0)
    # intersection = 5 x 10 = 50, union = 100 + 100 - 50 = 150
    assert compute_iou(box_a, box_b) == 50.0 / 150.0


def test_match_boxes_all_predictions_match_ground_truth():
    gt = [(0.0, 0.0, 10.0, 10.0), (20.0, 20.0, 30.0, 30.0)]
    pred = [(0.0, 0.0, 10.0, 10.0), (20.0, 20.0, 30.0, 30.0)]
    assert match_boxes(pred, gt, iou_threshold=0.5) == (2, 0, 0)


def test_match_boxes_extra_prediction_counts_as_false_positive():
    gt = [(0.0, 0.0, 10.0, 10.0)]
    pred = [(0.0, 0.0, 10.0, 10.0), (50.0, 50.0, 60.0, 60.0)]
    assert match_boxes(pred, gt, iou_threshold=0.5) == (1, 1, 0)


def test_match_boxes_missed_ground_truth_counts_as_false_negative():
    gt = [(0.0, 0.0, 10.0, 10.0), (20.0, 20.0, 30.0, 30.0)]
    pred = [(0.0, 0.0, 10.0, 10.0)]
    assert match_boxes(pred, gt, iou_threshold=0.5) == (1, 0, 1)


def test_compute_precision_recall_returns_expected_values():
    gt = [(0.0, 0.0, 10.0, 10.0), (20.0, 20.0, 30.0, 30.0)]
    pred = [(0.0, 0.0, 10.0, 10.0), (50.0, 50.0, 60.0, 60.0)]
    result = compute_precision_recall(pred, gt, iou_threshold=0.5)
    assert result["tp"] == 1
    assert result["fp"] == 1
    assert result["fn"] == 1
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5


def test_aggregate_precision_recall_micro_averages_across_images():
    per_image = [
        {"tp": 2, "fp": 1, "fn": 0},
        {"tp": 1, "fp": 0, "fn": 1},
    ]
    result = aggregate_precision_recall(per_image)
    assert result["tp"] == 3
    assert result["fp"] == 1
    assert result["fn"] == 1
    assert result["precision"] == 3 / 4
    assert result["recall"] == 3 / 4
