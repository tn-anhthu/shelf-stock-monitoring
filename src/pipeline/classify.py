"""Match a shelf crop's embedding against the catalog's stored embeddings,
reusing the existing cosine-similarity retrieval logic from
src/classification/benchmark/retrieve.py (category_id there is a plain
dict key — using sku_id strings instead of the original int category ids
works identically at runtime).
"""
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.classification.benchmark.retrieve import cosine_similarity


def load_catalog_embeddings(catalog_items: List[Dict]) -> List[Tuple[str, np.ndarray]]:
    return [(item["sku_id"], np.load(item["embedding_path"])) for item in catalog_items]


def classify_crop(
    crop_embedding: Optional[np.ndarray],
    catalog_embeddings: List[Tuple[str, np.ndarray]],
    unknown_threshold: float = 0.5,
) -> Tuple[Optional[str], float]:
    if crop_embedding is None:
        return None, 0.0
    if not catalog_embeddings:
        return None, 0.0

    best_sku_id = None
    best_score = -1.0
    for sku_id, embedding in catalog_embeddings:
        score = cosine_similarity(crop_embedding, embedding)
        if score > best_score:
            best_score = score
            best_sku_id = sku_id

    if best_score < unknown_threshold:
        return None, best_score
    return best_sku_id, best_score
