"""Compute one representative SigLIP2 embedding per SKU by averaging its 2-3
exemplar image embeddings, and persist it as a .npy file under
data/catalog/embeddings/<sku_id>.npy.

Uses dependency injection for embed_fn (same pattern as
src/classification/benchmark/catalog.py::build_catalog) so tests never load the
real SigLIP2 model.
"""
from pathlib import Path
from typing import Callable, List

import numpy as np
from PIL import Image


def build_sku_embedding(image_paths: List[str], embed_fn: Callable[[Image.Image], np.ndarray]) -> np.ndarray:
    embeddings = [embed_fn(Image.open(p)) for p in image_paths]
    return np.mean(embeddings, axis=0)


def save_embedding(embedding: np.ndarray, sku_id: str, output_dir: str) -> str:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{sku_id}.npy"
    np.save(path, embedding)
    return str(path)
