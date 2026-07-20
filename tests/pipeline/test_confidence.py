from src.pipeline.confidence import is_low_confidence


def test_is_low_confidence_true_when_average_below_threshold():
    assert is_low_confidence([0.3, 0.4, 0.2], threshold=0.5) is True


def test_is_low_confidence_false_when_average_at_or_above_threshold():
    assert is_low_confidence([0.6, 0.7, 0.8], threshold=0.5) is False


def test_is_low_confidence_empty_scores_returns_true():
    # no detections in a region we expected to score -> treat as low-confidence
    assert is_low_confidence([], threshold=0.5) is True


def test_is_low_confidence_uses_default_threshold():
    assert is_low_confidence([0.1, 0.1]) is True
