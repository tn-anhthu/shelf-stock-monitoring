"""Download catalog reference images (sourced from web product listings, never
self-photographed or AI-generated per spec section 10) into
data/catalog/images/<sku_id>/<n>.jpg.
"""
import time
from pathlib import Path
from typing import Callable, List
from urllib.parse import urlparse

import requests


def default_http_get(url: str, timeout=10, max_retries: int = 2, _get: Callable = requests.get):
    parsed = urlparse(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ShelfStockMonitor/1.0)",
        "Referer": f"{parsed.scheme}://{parsed.netloc}/",
    }

    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return _get(url, headers=headers, timeout=timeout)
        except requests.exceptions.RequestException as exc:
            last_exception = exc
            if attempt < max_retries:
                time.sleep(1)
    assert last_exception is not None
    raise last_exception


def fetch_sku_images(
    sku_id: str,
    image_urls: List[str],
    output_dir: str,
    http_get: Callable = default_http_get,
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
