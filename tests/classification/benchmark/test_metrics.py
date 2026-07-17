from src.classification.benchmark.metrics import is_correct_at_k, compute_topk_accuracy


def test_is_correct_at_k_true_category_in_top_k():
    assert is_correct_at_k([5, 2, 9], true_category=2, k=3) is True


def test_is_correct_at_k_true_category_outside_top_k():
    assert is_correct_at_k([5, 2, 9, 1], true_category=1, k=2) is False


def test_is_correct_at_k_empty_ranking_returns_false():
    assert is_correct_at_k([], true_category=1, k=5) is False


def test_compute_topk_accuracy_all_correct_at_k1():
    rankings = [[3, 1, 2], [7, 8, 9]]
    true_categories = [3, 7]
    assert compute_topk_accuracy(rankings, true_categories, k=1) == 1.0


def test_compute_topk_accuracy_half_correct_at_k1():
    rankings = [[3, 1, 2], [7, 8, 9]]
    true_categories = [3, 9]  # second one is at rank 3, not rank 1
    assert compute_topk_accuracy(rankings, true_categories, k=1) == 0.5


def test_compute_topk_accuracy_correct_when_k5_covers_it():
    rankings = [[1, 2, 3, 4, 9]]
    true_categories = [9]
    assert compute_topk_accuracy(rankings, true_categories, k=5) == 1.0


def test_compute_topk_accuracy_empty_returns_zero():
    assert compute_topk_accuracy([], [], k=1) == 0.0
