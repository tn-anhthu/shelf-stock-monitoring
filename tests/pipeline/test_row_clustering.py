from src.pipeline.row_clustering import cluster_rows


def _box(y_center: float) -> tuple:
    """Build a 10px-tall box centered at the given y-coordinate. x-range and
    exact height don't matter for cluster_rows -- only box_y_center((y1+y2)/2)
    does -- so every test box uses the same fixed x-range/height for clarity.
    """
    return (0.0, y_center - 5.0, 10.0, y_center + 5.0)


def test_cluster_rows_compares_to_row_mean_not_last_box():
    # Reproduces the exact chaining example from docs/superpowers/specs/
    # 2026-08-06-cluster-rows-chaining-fix-design.md section 1: 5 boxes with
    # y-centers 15px apart, tolerance=20. The OLD "compare to last box only"
    # algorithm joins all 5 into one row (each consecutive step is 15<=20).
    # Comparing to the row's running mean instead splits it into 3 rows,
    # because by the 3rd box the row's mean (7.5) is already far enough from
    # the incoming box (30) to exceed tolerance (22.5 > 20).
    boxes = [_box(0), _box(15), _box(30), _box(45), _box(60)]
    rows = cluster_rows(boxes, tolerance=20.0)
    assert rows == [
        [_box(0), _box(15)],
        [_box(30), _box(45)],
        [_box(60)],
    ]


def test_cluster_rows_span_cap_catches_drift_mean_check_alone_would_miss():
    # Adversarial construction: each new box's y-center is chosen as the
    # LARGEST value that still satisfies the row-mean check alone (diff to
    # running mean <= tolerance=20), which lets the row's total span creep
    # past 2x tolerance (40) via slow drift. Box at y-center=41 satisfies
    # the mean check (mean of [0,20,30,36]=21.5, diff=19.5<=20) but would
    # stretch the row's span to 41, past the 40px cap
    # (tolerance * max_span_multiplier, default multiplier=2.0) -- the span
    # cap must reject it even though the mean check alone would accept it.
    boxes = [_box(0), _box(20), _box(30), _box(36), _box(41)]
    rows = cluster_rows(boxes, tolerance=20.0)
    assert rows == [
        [_box(0), _box(20), _box(30), _box(36)],
        [_box(41)],
    ]


def test_cluster_rows_well_separated_rows_unchanged():
    # Sanity check: ordinary, non-adversarial input (rows far apart relative
    # to tolerance) must behave identically to the old algorithm.
    boxes = [_box(0), _box(100), _box(200)]
    rows = cluster_rows(boxes, tolerance=20.0)
    assert rows == [[_box(0)], [_box(100)], [_box(200)]]


def test_cluster_rows_empty_list_returns_empty_list():
    assert cluster_rows([], tolerance=20.0) == []


def test_cluster_rows_single_box_returns_one_row():
    boxes = [_box(0)]
    assert cluster_rows(boxes, tolerance=20.0) == [[_box(0)]]


def test_cluster_rows_max_span_multiplier_is_overridable():
    # Same adversarial boxes as the span-cap test above, but with a looser
    # multiplier (3.0 -> cap=60) -- box at y-center=41 (span=41) must now be
    # allowed to join, proving the parameter actually takes effect.
    boxes = [_box(0), _box(20), _box(30), _box(36), _box(41)]
    rows = cluster_rows(boxes, tolerance=20.0, max_span_multiplier=3.0)
    assert rows == [[_box(0), _box(20), _box(30), _box(36), _box(41)]]
