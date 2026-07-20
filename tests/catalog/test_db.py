import sqlite3

from src.catalog.db import (
    create_tables,
    get_catalog_item,
    get_connection,
    list_catalog,
    upsert_catalog_item,
)


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
