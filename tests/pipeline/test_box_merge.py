from src.pipeline.box_merge import merge_adjacent_fragments


def test_merge_adjacent_fragments_merges_real_measured_split_case():
    # Real pair measured on the milk-shelf photo (scripts/archive/debug_box_fragments.py):
    # IoU=0.025, x_overlap_ratio=1.00, y_gap=-1.7, bottom fragment aspect_ratio=0.33
    # vs top fragment's 1.12 -> should merge into one box.
    boxes = [(184.0, 286.2, 231.3, 339.2), (183.9, 337.5, 232.0, 353.3)]
    assert merge_adjacent_fragments(boxes) == [(183.9, 286.2, 232.0, 353.3)]


def test_merge_adjacent_fragments_does_not_merge_side_by_side_products():
    # Two distinct products next to each other horizontally: x_overlap is ~0,
    # so this must never merge regardless of aspect ratio.
    boxes = [(0, 0, 50, 100), (60, 0, 110, 100)]
    assert merge_adjacent_fragments(boxes) == boxes


def test_merge_adjacent_fragments_merges_chain_of_three_into_one():
    # A tall product sliced into 3 short fragments, stacked and touching, among
    # several normal-shaped products (needed so the "normal" aspect ratio median
    # reflects real products, not the fragments themselves).
    normal_boxes = [
        (300, 0, 350, 150),
        (400, 0, 450, 150),
        (500, 0, 550, 150),
        (600, 0, 650, 150),
    ]
    fragments = [
        (0, 0, 50, 20),
        (0, 20, 50, 40),
        (0, 40, 50, 60),
    ]
    result = merge_adjacent_fragments(normal_boxes + fragments)
    assert set(result) == {(0, 0, 50, 60), *normal_boxes}


def test_merge_adjacent_fragments_single_box_returns_unchanged():
    boxes = [(0, 0, 50, 100)]
    assert merge_adjacent_fragments(boxes) == boxes


def test_merge_adjacent_fragments_empty_returns_empty_list():
    assert merge_adjacent_fragments([]) == []
