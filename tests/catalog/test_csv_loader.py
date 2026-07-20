import csv

from src.catalog.csv_loader import load_catalog_rows


def _write_csv(path, rows):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["sku_id", "name", "price", "shelf_full_qty", "image_url_1", "image_url_2", "image_url_3"],
        )
        writer.writeheader()
        writer.writerows(rows)


def test_load_catalog_rows_parses_types(tmp_path):
    csv_path = tmp_path / "catalog.csv"
    _write_csv(
        csv_path,
        [
            {
                "sku_id": "choco_pie_orion",
                "name": "Chocopie Orion hop 12 cai",
                "price": "45000",
                "shelf_full_qty": "10",
                "image_url_1": "https://example.com/1.jpg",
                "image_url_2": "https://example.com/2.jpg",
                "image_url_3": "",
            }
        ],
    )
    rows = load_catalog_rows(str(csv_path))
    assert rows == [
        {
            "sku_id": "choco_pie_orion",
            "name": "Chocopie Orion hop 12 cai",
            "price": 45000,
            "shelf_full_qty": 10,
            "image_urls": ["https://example.com/1.jpg", "https://example.com/2.jpg"],
        }
    ]


def test_load_catalog_rows_multiple_rows(tmp_path):
    csv_path = tmp_path / "catalog.csv"
    _write_csv(
        csv_path,
        [
            {"sku_id": "a", "name": "A", "price": "1000", "shelf_full_qty": "5", "image_url_1": "u1", "image_url_2": "", "image_url_3": ""},
            {"sku_id": "b", "name": "B", "price": "2000", "shelf_full_qty": "8", "image_url_1": "u2", "image_url_2": "u3", "image_url_3": "u4"},
        ],
    )
    rows = load_catalog_rows(str(csv_path))
    assert len(rows) == 2
    assert rows[1]["image_urls"] == ["u2", "u3", "u4"]


def test_load_catalog_rows_empty_file_returns_empty_list(tmp_path):
    csv_path = tmp_path / "catalog.csv"
    _write_csv(csv_path, [])
    assert load_catalog_rows(str(csv_path)) == []
