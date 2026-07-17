"""Cosine-similarity retrieval: rank catalog categories by similarity to a query embedding.

A catalog entry is (category_id, embedding) — the SAME category can appear multiple times
(once per exemplar image), since a crop matching well against any one exemplar of a
category is what counts, not the average embedding of all its exemplars.
"""
from typing import List, Tuple

import numpy as np

CatalogEntry = Tuple[int, np.ndarray]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def rank_categories(query_embedding: np.ndarray, catalog: List[CatalogEntry]) -> List[int]:
    """Rank distinct categories by their best (max) similarity to the query, descending."""
    best_per_category = {}
    for category_id, embedding in catalog:
        sim = cosine_similarity(query_embedding, embedding)
        if category_id not in best_per_category or sim > best_per_category[category_id]:
            best_per_category[category_id] = sim
    return sorted(best_per_category, key=lambda c: best_per_category[c], reverse=True)
