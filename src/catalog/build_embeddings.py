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
    """Compute one representative embedding per SKU by averaging its exemplar embeddings.

    Args:
        image_paths: List of paths to exemplar images for this SKU.
        embed_fn: Callable that takes a PIL.Image.Image (full reference image) and returns
            its embedding as an np.ndarray. NOTE: This is a different embed_fn contract
            than src/pipeline/scan.py::run_scan uses — scan.py's embed_fn takes a
            (image, box) tuple for a shelf crop. A future caller wiring the real SigLIP2
            model into both places needs two separate adapter lambdas.

    Returns:
        The mean embedding across all exemplar images.
    """
    embeddings = [embed_fn(Image.open(p)) for p in image_paths]
    return np.mean(embeddings, axis=0)


def save_embedding(embedding: np.ndarray, sku_id: str, output_dir: str) -> str:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{sku_id}.npy"
    np.save(path, embedding)
    return str(path)
