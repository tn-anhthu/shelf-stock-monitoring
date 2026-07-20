import csv

import numpy as np

from src.catalog.db import get_connection, list_catalog
from src.catalog.seed import seed_catalog


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


def _write_csv(path):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["sku_id", "name", "price", "shelf_full_qty", "image_url_1", "image_url_2", "image_url_3"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "sku_id": "choco_pie_orion",
                "name": "Chocopie Orion hop 12 cai",
                "price": "45000",
                "shelf_full_qty": "10",
                "image_url_1": "https://example.com/1.jpg",
                "image_url_2": "https://example.com/2.jpg",
                "image_url_3": "",
            }
        )


def test_seed_catalog_writes_images_embedding_and_db_row(tmp_path):
    csv_path = tmp_path / "catalog.csv"
    _write_csv(csv_path)
    images_dir = tmp_path / "images"
    embeddings_dir = tmp_path / "embeddings"
    db_path = tmp_path / "shelfsense.db"

    from PIL import Image
    import io

    def fake_get(url, timeout=10):
        buf = io.BytesIO()
        Image.new("RGB", (4, 4)).save(buf, format="JPEG")
        return FakeResponse(buf.getvalue())

    count = seed_catalog(
        csv_path=str(csv_path),
        images_dir=str(images_dir),
        embeddings_dir=str(embeddings_dir),
        db_path=str(db_path),
        embed_fn=lambda image: np.array([1.0, 0.0]),
        http_get=fake_get,
    )

    assert count == 1
    assert (images_dir / "choco_pie_orion" / "1.jpg").exists()
    assert (images_dir / "choco_pie_orion" / "2.jpg").exists()
    assert (embeddings_dir / "choco_pie_orion.npy").exists()

    conn = get_connection(str(db_path))
    catalog = list_catalog(conn)
    assert len(catalog) == 1
    assert catalog[0]["sku_id"] == "choco_pie_orion"
    assert catalog[0]["price"] == 45000
    assert catalog[0]["embedding_path"] == str(embeddings_dir / "choco_pie_orion.npy")
