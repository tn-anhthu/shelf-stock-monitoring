"""Real end-to-end scan: YOLOv8 1a detector + SigLIP2 classifier wired into
src/pipeline/scan.py::run_scan, against the catalog seeded by src/catalog/seed.py.

Usage: python3 scripts/run_scan_e2e.py --image path/to/shelf.jpg --weights runs/train_1a/full/weights/best.pt
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
import pillow_heif
pillow_heif.register_heif_opener()

from src.catalog.db import get_connection, list_catalog
from src.classification.benchmark.embed_siglip2 import embed_image_siglip2, load_model_siglip2
from src.detection.train.run_trained_1a import detect_1a, load_model_1a
from src.pipeline.classify import load_catalog_embeddings
from src.pipeline.crop import crop_box
from src.pipeline.scan import run_scan

DEFAULT_DB_PATH = "data/shelfsense.db"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--weights", type=str, required=True)
    parser.add_argument("--db", type=str, default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    conn = get_connection(args.db)
    catalog_items = list_catalog(conn)
    catalog_embeddings = load_catalog_embeddings(catalog_items)

    yolo_model = load_model_1a(Path(args.weights))
    siglip_model, siglip_processor = load_model_siglip2()

    def real_embed_fn(pair):
        image, box = pair
        cropped = crop_box(image, box)
        if cropped is None:
            return None
        return embed_image_siglip2(siglip_model, siglip_processor, cropped)

    shelf_image = Image.open(args.image)
    result = run_scan(
        image=shelf_image,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=lambda img: detect_1a(yolo_model, img),
        embed_fn=real_embed_fn,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
