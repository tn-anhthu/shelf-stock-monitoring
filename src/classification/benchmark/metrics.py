"""Top-k retrieval accuracy for comparing predicted category rankings against
ground-truth categories.

A "ranking" is a list of category ids ordered by descending similarity to a query
(the most likely category first). Unlike Phase 1's detection metrics (which compute
precision/recall via IoU-based box matching), this is a pure classification metric:
each test crop has exactly one true category, and we check whether it appears within
the top k of the predicted ranking.
"""
from typing import List


def is_correct_at_k(ranked_categories: List[int], true_category: int, k: int) -> bool:
    return true_category in ranked_categories[:k]


def compute_topk_accuracy(
    per_item_rankings: List[List[int]], true_categories: List[int], k: int
) -> float:
    if not per_item_rankings:
        return 0.0
    correct = sum(
        is_correct_at_k(ranking, true_cat, k)
        for ranking, true_cat in zip(per_item_rankings, true_categories)
    )
    return correct / len(per_item_rankings)
