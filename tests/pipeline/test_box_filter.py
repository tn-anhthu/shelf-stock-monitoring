from src.pipeline.box_filter import filter_anomalous_boxes, filter_contained_boxes


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


def test_filter_contained_boxes_deletes_redundant_box_haohao_crop45():
    # Real coords from data/scan_viz/test1 (re-run of detect_1a + merge_adjacent_
    # fragments + filter_anomalous_boxes on test1.HEIC, cross-checked against
    # crop_41/45/48_ok.jpg): box41 and box48 are each a tightly-fit, correct
    # detection of one Hao Hao cup; box45 is an oversized box that swallows
    # box41 entirely and also dips into box48's region (containment ~0.6) -
    # both regions box45 covers already have their own independent box, so
    # box45 is genuinely redundant.
    box41_top_cup = (1109.0, 2840.4, 1326.8, 3116.4)
    box45_both_cups = (1116.5, 2843.7, 1326.5, 3254.9)
    box48_bottom_cup = (1125.5, 3098.8, 1318.6, 3359.2)

    kept, flagged, pairs = filter_contained_boxes([box41_top_cup, box45_both_cups, box48_bottom_cup])

    assert set(kept) == {box41_top_cup, box48_bottom_cup}
    assert flagged == []
    assert pairs == []


def test_filter_contained_boxes_flags_instead_of_deleting_binggrae_crop38():
    # Real coords from data/scan_viz/test1 (cross-checked against crop_37/38_
    # ok.jpg): box37 is a correct, tightly-fit detection of the Melon carton;
    # box38 is an oversized box covering both Melon and Strawberry cartons.
    # Unlike the Haohao case, nothing else in the real 60-box detection list
    # overlaps box38's Strawberry-side leftover region at all - there's no
    # independent box to fall back on, so deleting box38 would silently lose
    # the Strawberry carton entirely.
    box37_melon_only = (702.7, 2476.3, 819.0, 2772.5)
    box38_melon_and_strawberry = (610.1, 2478.3, 820.7, 2808.7)

    kept, flagged, pairs = filter_contained_boxes([box37_melon_only, box38_melon_and_strawberry])

    assert set(kept) == {box37_melon_only, box38_melon_and_strawberry}
    assert flagged == [box38_melon_and_strawberry]
    assert pairs == [(box38_melon_and_strawberry, box37_melon_only)]


def test_filter_contained_boxes_no_containment_relationship_keeps_all_unflagged():
    boxes = [(0, 0, 50, 50), (60, 0, 110, 50)]
    kept, flagged, pairs = filter_contained_boxes(boxes)
    assert kept == boxes
    assert flagged == []
    assert pairs == []


def test_filter_contained_boxes_empty_returns_empty_lists():
    assert filter_contained_boxes([]) == ([], [], [])


def test_filter_contained_boxes_reports_a_pair_per_child_when_parent_has_multiple_children():
    # Mirrors the Koreno Premium Kimchi case from docs/superpowers/specs/
    # 2026-08-05-same-item-dedup-design.md: 1 parent box swallowing 3 separate
    # child boxes (not just 1) -> flagged_pairs must contain one tuple per
    # child, all sharing the same parent, so scan.py can compare confidence
    # for each pair independently.
    child_a = (10.0, 10.0, 40.0, 40.0)
    child_b = (10.0, 60.0, 40.0, 90.0)
    parent = (0.0, 0.0, 50.0, 100.0)

    kept, flagged, pairs = filter_contained_boxes([child_a, child_b, parent])

    assert flagged == [parent]
    assert len(pairs) == 2
    assert all(pair[0] == parent for pair in pairs)
    assert {pair[1] for pair in pairs} == {child_a, child_b}


def test_filter_contained_boxes_excludes_pairs_whose_child_was_independently_dropped():
    # Reproduces a real crash found running run_scan() on
    # data/scan_viz/input/test6.jpg: a 3-level nesting chain
    # (grandparent contains middle contains small). `middle`'s own leftover
    # (beyond `small`) is trivially covered by `grandparent` itself -
    # containment_ratio(grandparent, middle) == 1.0 since middle sits fully
    # inside it - so `middle` gets dropped as redundant in its OWN loop
    # iteration, same as the Haohao case above. That decision is independent
    # of `grandparent`'s own iteration, which (computed separately) lists
    # `middle` as one of grandparent's children too, since `middle` also
    # independently satisfies grandparent's containment/IoU thresholds.
    # flagged_pairs must never reference a box that didn't survive into
    # `kept` - scan.py's box_position lookup (keyed off the final kept boxes)
    # would KeyError on a pair naming a box that no longer exists.
    grandparent = (0.0, 0.0, 100.0, 100.0)
    middle = (10.0, 10.0, 90.0, 90.0)
    small = (20.0, 20.0, 50.0, 50.0)

    kept, flagged, pairs = filter_contained_boxes([grandparent, middle, small])

    assert middle not in kept  # existing behavior: redundant, covered by grandparent
    assert set(kept) == {grandparent, small}
    assert pairs == [(grandparent, small)]
