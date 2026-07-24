"""Orchestrate catalog seeding: CSV row -> fetch images -> build embedding -> upsert
into SQLite. This is the script Thư runs after editing the Google Sheet CSV, per
docs/specs/mvp-design.md section 10/Week 1.

Usage: python3 -m src.catalog.seed --csv path/to/catalog.csv
"""
import argparse
from typing import Callable

from src.catalog.build_embeddings import build_sku_embedding, save_embedding
from src.catalog.csv_loader import load_catalog_rows
from src.catalog.db import create_tables, get_connection, upsert_catalog_item
from src.catalog.image_fetcher import default_http_get, fetch_sku_images
from src.classification.benchmark.embed_siglip2 import embed_image_siglip2, load_model_siglip2

DEFAULT_IMAGES_DIR = "data/catalog/images"
DEFAULT_EMBEDDINGS_DIR = "data/catalog/embeddings"
DEFAULT_DB_PATH = "data/shelfsense.db"


def seed_catalog(
    csv_path: str,
    images_dir: str,
    embeddings_dir: str,
    db_path: str,
    embed_fn: Callable,
    http_get: Callable = default_http_get,
) -> int:
    rows = load_catalog_rows(csv_path)

    conn = get_connection(db_path)
    create_tables(conn)

    for row in rows:
        image_paths = fetch_sku_images(row["sku_id"], row["image_urls"], images_dir, http_get=http_get)
        embedding = build_sku_embedding(image_paths, embed_fn=embed_fn)
        embedding_path = save_embedding(embedding, row["sku_id"], embeddings_dir)
        upsert_catalog_item(
            conn,
            sku_id=row["sku_id"],
            name=row["name"],
            price=row["price"],
            shelf_full_qty=row["shelf_full_qty"],
            embedding_path=embedding_path,
        )

    return len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=str, required=True)
    parser.add_argument("--images-dir", type=str, default=DEFAULT_IMAGES_DIR)
    parser.add_argument("--embeddings-dir", type=str, default=DEFAULT_EMBEDDINGS_DIR)
    parser.add_argument("--db", type=str, default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    model, processor = load_model_siglip2()
    embed_fn = lambda image: embed_image_siglip2(model, processor, image)

    count = seed_catalog(args.csv, args.images_dir, args.embeddings_dir, args.db, embed_fn=embed_fn)
    print(f"Seeded {count} SKUs into {args.db}")


if __name__ == "__main__":
    main()
