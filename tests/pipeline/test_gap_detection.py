from src.pipeline.gap_detection import detect_gaps


def test_detect_gaps_even_spacing_returns_no_gaps():
    # Small, realistic touching-product spacing (well under 0.9x avg width).
    boxes = [(0, 0, 10, 10), (12, 0, 22, 10), (24, 0, 34, 10)]
    assert detect_gaps(boxes) == []


def test_detect_gaps_flags_one_gap_wider_than_multiplier():
    boxes = [(0, 0, 10, 10), (12, 0, 22, 10), (80, 0, 90, 10)]
    assert detect_gaps(boxes) == [(22, 0, 80, 10)]


def test_detect_gaps_does_not_flag_space_before_first_box_in_row():
    # Boxes start far from x=0; that offset must never be reported as a gap.
    boxes = [(500, 0, 510, 10), (512, 0, 522, 10)]
    assert detect_gaps(boxes) == []


def test_detect_gaps_does_not_flag_space_after_last_box_in_row():
    # Nothing exists past the last box, so there is no "space after" to flag either.
    boxes = [(0, 100, 10, 110), (12, 100, 22, 110)]
    assert detect_gaps(boxes) == []


def test_detect_gaps_handles_multiple_rows_independently():
    row1 = [(0, 0, 10, 10), (12, 0, 22, 10), (80, 0, 90, 10)]
    row2 = [(0, 200, 10, 210), (12, 200, 22, 210), (80, 200, 90, 210)]
    boxes = row1 + row2
    assert detect_gaps(boxes) == [(22, 0, 80, 10), (22, 200, 80, 210)]


def test_detect_gaps_singleton_row_uses_global_median_fallback_without_crashing():
    row1 = [(0, 0, 10, 10), (12, 0, 22, 10), (80, 0, 90, 10)]
    singleton_row = [(0, 500, 10, 510)]
    boxes = row1 + singleton_row
    assert detect_gaps(boxes) == [(22, 0, 80, 10)]


def test_detect_gaps_empty_boxes_returns_empty_list():
    assert detect_gaps([]) == []


def test_detect_gaps_single_box_total_returns_empty_list():
    assert detect_gaps([(0, 0, 10, 10)]) == []
