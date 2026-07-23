import sqlite3

from src.catalog.db import (
    create_tables,
    get_catalog_item,
    get_connection,
    list_catalog,
    upsert_catalog_item,
)
from src.catalog.db import insert_inventory_records, insert_scan_history


def test_create_tables_creates_catalog_inventory_scan_history():
    conn = get_connection(":memory:")
    create_tables(conn)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"catalog", "inventory", "scan_history"} <= tables


def test_upsert_catalog_item_then_get_returns_it():
    conn = get_connection(":memory:")
    create_tables(conn)
    upsert_catalog_item(conn, "choco_pie_orion", "Chocopie Orion hop 12 cai", 45000, 10, "data/catalog/embeddings/choco_pie_orion.npy")
    item = get_catalog_item(conn, "choco_pie_orion")
    assert item == {
        "sku_id": "choco_pie_orion",
        "name": "Chocopie Orion hop 12 cai",
        "price": 45000,
        "shelf_full_qty": 10,
        "embedding_path": "data/catalog/embeddings/choco_pie_orion.npy",
    }


def test_upsert_catalog_item_twice_replaces_not_duplicates():
    conn = get_connection(":memory:")
    create_tables(conn)
    upsert_catalog_item(conn, "coke_330", "Coca-Cola lon 330ml", 10000, 12, "e/coke_330.npy")
    upsert_catalog_item(conn, "coke_330", "Coca-Cola lon 330ml", 11000, 12, "e/coke_330.npy")
    assert len(list_catalog(conn)) == 1
    assert get_catalog_item(conn, "coke_330")["price"] == 11000


def test_get_catalog_item_missing_sku_returns_none():
    conn = get_connection(":memory:")
    create_tables(conn)
    assert get_catalog_item(conn, "does_not_exist") is None


def test_list_catalog_empty_returns_empty_list():
    conn = get_connection(":memory:")
    create_tables(conn)
    assert list_catalog(conn) == []


def test_insert_scan_history_then_query():
    conn = get_connection(":memory:")
    create_tables(conn)
    insert_scan_history(conn, image_path="data/scans/1.jpg", raw_result="{}", confirmed_result=None, created_at="2026-07-27T10:00:00")
    rows = conn.execute("SELECT image_path, raw_result, confirmed_result FROM scan_history").fetchall()
    assert rows == [("data/scans/1.jpg", "{}", None)]


def test_insert_inventory_records_writes_one_row_per_sku():
    conn = get_connection(":memory:")
    create_tables(conn)
    insert_inventory_records(
        conn,
        records=[
            {"sku_id": "choco_pie_orion", "quantity": 5, "value": 225000, "status": "ok"},
            {"sku_id": "coke_330", "quantity": 1, "value": 10000, "status": "low"},
        ],
        scanned_at="2026-07-27T10:00:00",
    )
    rows = conn.execute("SELECT sku_id, quantity, value, status FROM inventory").fetchall()
    assert set(rows) == {
        ("choco_pie_orion", 5, 225000, "ok"),
        ("coke_330", 1, 10000, "low"),
    }
