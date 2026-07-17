"""Build a (category_id, embedding) catalog from exemplar images, using any embed_fn
that maps a PIL image to a numpy embedding vector — works for CLIP, SigLIP2, or any
future embedding model without duplicating this loop.
"""
from typing import Callable, Dict, List

import numpy as np
from PIL import Image

from src.classification.benchmark.retrieve import CatalogEntry


def build_catalog(
    catalog_source: List[Dict], embed_fn: Callable[[Image.Image], np.ndarray]
) -> List[CatalogEntry]:
    return [(item["category"], embed_fn(item["image"])) for item in catalog_source]
