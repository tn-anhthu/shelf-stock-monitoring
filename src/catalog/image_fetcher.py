"""Download catalog reference images (sourced from web product listings, never
self-photographed or AI-generated per spec section 10) into
data/catalog/images/<sku_id>/<n>.jpg.
"""
from pathlib import Path
from typing import Callable, List

import requests


def fetch_sku_images(
    sku_id: str,
    image_urls: List[str],
    output_dir: str,
    http_get: Callable = requests.get,
) -> List[str]:
    if not image_urls:
        return []

    sku_dir = Path(output_dir) / sku_id
    sku_dir.mkdir(parents=True, exist_ok=True)

    written_paths = []
    for i, url in enumerate(image_urls, start=1):
        response = http_get(url, timeout=10)
        response.raise_for_status()
        dest = sku_dir / f"{i}.jpg"
        dest.write_bytes(response.content)
        written_paths.append(str(dest))
    return written_paths
