"""Real end-to-end scan: YOLOv8 1a detector + SigLIP2 classifier + Claude Haiku
verification wired into src/pipeline/scan.py::run_scan, against the catalog
seeded by src/catalog/seed.py.

API key is read from the ANTHROPIC_API_KEY environment variable — either
export it yourself before running, or put it in a .env file (ANTHROPIC_API_KEY=...,
gitignored) and it's auto-loaded via python-dotenv if that package is
installed. Never hardcode the key into this or any other file.

Usage: python3 scripts/run_scan_e2e.py --image path/to/shelf.jpg --weights runs/train_1a/full/weights/best.pt
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import anthropic
from PIL import Image
import pillow_heif
pillow_heif.register_heif_opener()

from src.catalog.db import get_connection, list_catalog
from src.classification.benchmark.embed_siglip2 import embed_image_siglip2, load_model_siglip2
from src.detection.train.run_trained_1a import detect_1a, load_model_1a
from src.pipeline.classify import load_catalog_embeddings
from src.pipeline.scan import run_scan

DEFAULT_DB_PATH = "data/shelfsense.db"
DEFAULT_MAX_WORKERS = 10


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--weights", type=str, required=True)
    parser.add_argument("--db", type=str, default=DEFAULT_DB_PATH)
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set — export it before running this script.")
    llm_client = anthropic.Anthropic()

    conn = get_connection(args.db)
    catalog_items = list_catalog(conn)
    catalog_embeddings = load_catalog_embeddings(catalog_items)

    yolo_model = load_model_1a(Path(args.weights))
    siglip_model, siglip_processor = load_model_siglip2()

    def real_embed_fn(cropped_image):
        return embed_image_siglip2(siglip_model, siglip_processor, cropped_image)

    shelf_image = Image.open(args.image)
    result = run_scan(
        image=shelf_image,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=lambda img: detect_1a(yolo_model, img),
        embed_fn=real_embed_fn,
        llm_client=llm_client,
        max_workers=args.max_workers,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
