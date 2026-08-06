"""Real-image regression tests for cluster_rows.

These replace the previous version of this file, which tested the NEW
(row-mean + span-cap) algorithm introduced in commit 4a9ffed. That commit was
reverted on 06/08/2026 after exhaustive re-investigation found no real case
where the OLD (single-linkage, "compare to last box") algorithm actually
bridges 2 distinct real physical shelf rows, and found the NEW algorithm
actively over-fragmenting at least 3 confirmed genuine single real shelf rows.
See docs/detection-notes/detection-log.md's 06/08/2026 correction entry and
the 2 full investigation reports it cites
(docs/detection-notes/2026-08-06-cluster-rows-diagnostic-report.md,
docs/detection-notes/2026-08-06-cluster-rows-old-algorithm-reverification.md).

Every box tuple below is a real detection from the n_2000 checkpoint
(runs/detect/runs/train_1a/n_2000/weights/best.pt) on test1.HEIC/test3.HEIC,
copied verbatim from those 2 reports -- not synthetic. Tolerances are the
real adaptive_tolerances() output for the corresponding image. The point of
this file is to pin down the OLD (now-reverted, current) algorithm's
confirmed-correct behavior on real data, so an accidental future
reintroduction of the "chaining fix" -- or any other regression -- gets
caught immediately.
"""
from src.pipeline.row_clustering import cluster_rows

# Real adaptive_tolerances() row_cluster_tolerance for test3.HEIC (n_2000
# checkpoint, current recalibrated ROW_CLUSTER_TOLERANCE_RATIO).
TEST3_TOLERANCE = 23.4291

# Real adaptive_tolerances() row_cluster_tolerance for test1.HEIC.
TEST1_TOLERANCE = 18.9501


def test_row4_four_side_by_side_bottles_cluster_into_one_row():
    # test3.HEIC "row 4": 4 real, distinct, side-by-side fermented-milk
    # bottles -- one genuine physical shelf row, visually confirmed. Both the
    # OLD and NEW algorithm agree on this case (identical membership) -- kept
    # here as a baseline regression guard, not a case the revert changes.
    boxes = [
        (2032.8, 1008.9, 2285.4, 1787.2),
        (1753.6, 1011.9, 2018.5, 1804.8),
        (1482.3, 1028.4, 1742.9, 1810.1),
        (2302.6, 1081.2, 2563.4, 1768.0),
    ]
    rows = cluster_rows(boxes, tolerance=TEST3_TOLERANCE)
    assert len(rows) == 1
    assert set(rows[0]) == set(boxes)


def test_row5_five_side_by_side_bottles_cluster_into_one_row():
    # test3.HEIC "row 5": 5 real, distinct, side-by-side bottles -- one
    # genuine physical shelf row (visually confirmed in the diagnostic
    # report). This is the case where the NOW-REVERTED new (row-mean +
    # span-cap) algorithm incorrectly split it into 2 groups (3+2) because
    # its 43.9px span exceeds the span cap. This test protects against that
    # regression specifically.
    boxes = [
        (185.9, 1123.0, 443.0, 1877.7),
        (457.8, 1119.3, 704.8, 1870.2),
        (722.5, 1113.8, 961.2, 1848.9),
        (971.9, 1104.1, 1214.6, 1831.2),
        (1234.4, 1093.7, 1472.4, 1819.3),
    ]
    rows = cluster_rows(boxes, tolerance=TEST3_TOLERANCE)
    assert len(rows) == 1
    assert set(rows[0]) == set(boxes)


def test_row9_yakult_multipacks_plus_stray_fragment_cluster_into_one_row():
    # test3.HEIC "row 9" (Yakult shelf): 2 real multi-packs plus 1 stray
    # duplicate-detection fragment of an item in the row below, which
    # legitimately rides along in the same cluster_rows group under the real
    # system (this is a merge_adjacent_fragments/dedup issue, not a
    # cluster_rows bug -- see the reverification report's Investigation 1).
    # Both OLD and NEW agree on this grouping -- kept as a baseline guard.
    boxes = [
        (0.0, 2200.4, 116.7, 2428.3),
        (127.4, 2039.4, 984.8, 2614.6),
        (1036.5, 2005.7, 1882.1, 2680.6),
    ]
    rows = cluster_rows(boxes, tolerance=TEST3_TOLERANCE)
    assert len(rows) == 1
    assert set(rows[0]) == set(boxes)


def test_row9_yakult_does_not_merge_with_distinct_lower_row():
    # test3.HEIC: confirms row 9 (Yakult, 3 boxes above) never merges with
    # the distinct, genuinely lower real shelf row directly below it
    # (yc~2453.4-2476.4, n=4). The reverification report established this
    # holds for both algorithms; the 4 lower-row box tuples themselves were
    # fetched fresh for this test by rerunning detect_1a/merge_adjacent_
    # fragments/cluster_rows on test3.HEIC and locating the yc-in-[2453,2477]
    # group of 4 that contains (0.0,2219.2,107.8,2733.7) (the one tuple
    # already on record in the reverification report).
    row9_boxes = [
        (0.0, 2200.4, 116.7, 2428.3),
        (127.4, 2039.4, 984.8, 2614.6),
        (1036.5, 2005.7, 1882.1, 2680.6),
    ]
    lower_row_boxes = [
        (126.6, 2190.8, 1001.3, 2716.1),
        (2343.0, 2313.6, 2760.6, 2614.3),
        (1964.1, 2306.3, 2333.9, 2622.7),
        (0.0, 2219.2, 107.8, 2733.7),
    ]
    rows = cluster_rows(row9_boxes + lower_row_boxes, tolerance=TEST3_TOLERANCE)
    assert len(rows) == 2
    row_sets = [set(r) for r in rows]
    assert set(row9_boxes) in row_sets
    assert set(lower_row_boxes) in row_sets


def test_row18_twelve_cartons_cluster_into_one_row():
    # test3.HEIC "row 18": 12 real, distinct cartons -- one genuine physical
    # shelf row, visually confirmed. This is the OTHER case the now-reverted
    # new algorithm incorrectly split, into 3 groups (5+4+3). Protects
    # against that regression.
    boxes = [
        (0.0, 3035.1, 37.0, 3641.7),
        (41.9, 2933.9, 306.0, 3636.5),
        (330.6, 3050.7, 555.3, 3626.3),
        (569.3, 3045.5, 798.5, 3602.4),
        (818.1, 3027.0, 1053.4, 3587.9),
        (1069.7, 3021.0, 1292.1, 3575.9),
        (1305.3, 3011.3, 1522.5, 3555.5),
        (1540.9, 2999.0, 1767.8, 3538.5),
        (1784.8, 2983.2, 2009.1, 3530.3),
        (2031.2, 2995.7, 2268.0, 3523.0),
        (2293.3, 2953.2, 2514.4, 3531.7),
        (2532.7, 2946.1, 2769.5, 3552.9),
    ]
    rows = cluster_rows(boxes, tolerance=TEST3_TOLERANCE)
    assert len(rows) == 1
    assert set(rows[0]) == set(boxes)


def test_hao_hao_row_plus_isolated_singletons():
    # test1.HEIC: 4 real, distinct, side-by-side Hao Hao instant-noodle boxes
    # (one genuine physical shelf row -- includes "box41" from
    # tests/pipeline/test_box_filter.py) discovered as a byproduct of this
    # investigation as a case the now-reverted new algorithm incorrectly
    # split (Investigation 2 in the reverification report), plus 2 more real
    # boxes from the same image -- box45_both_cups and box48_bottom_cup, also
    # from tests/pipeline/test_box_filter.py -- that must each remain their
    # own isolated singleton row under BOTH algorithms: the real y-center
    # gaps around them (38.4px and 179.7px respectively) exceed 2x tolerance
    # with no intermediate boxes to chain through.
    row_boxes = [
        (1109.0, 2840.4, 1326.8, 3116.4),
        (1996.9, 2883.3, 2313.3, 3107.9),
        (1657.7, 2901.9, 1980.0, 3114.8),
        (1347.8, 2864.2, 1636.3, 3157.7),
    ]
    box45_both_cups = (1116.5, 2843.7, 1326.5, 3254.9)
    box48_bottom_cup = (1125.5, 3098.8, 1318.6, 3359.2)

    boxes = row_boxes + [box45_both_cups, box48_bottom_cup]
    rows = cluster_rows(boxes, tolerance=TEST1_TOLERANCE)

    assert len(rows) == 3
    row_sets = [set(r) for r in rows]
    assert set(row_boxes) in row_sets
    assert {box45_both_cups} in row_sets
    assert {box48_bottom_cup} in row_sets


def test_cluster_rows_empty_list_returns_empty_list():
    assert cluster_rows([], tolerance=20.0) == []


def test_cluster_rows_single_box_returns_one_row():
    box = (0.0, -5.0, 10.0, 5.0)
    assert cluster_rows([box], tolerance=20.0) == [[box]]
