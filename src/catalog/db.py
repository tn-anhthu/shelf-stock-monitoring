"""SQLite schema and CRUD helpers for the ShelfSense catalog, inventory, and scan
history. Single-file local database per docs/superpowers/specs/2026-07-20-shelfsense-mvp-design.md
section 9 (SQLite, not Supabase/cloud — this app runs local, no multi-user need).
"""
import sqlite3
from typing import Dict, List, Optional

CREATE_CATALOG_TABLE = """
CREATE TABLE IF NOT EXISTS catalog (
    sku_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price INTEGER NOT NULL,
    shelf_full_qty INTEGER NOT NULL,
    embedding_path TEXT NOT NULL
)
"""

CREATE_INVENTORY_TABLE = """
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    value INTEGER NOT NULL,
    status TEXT NOT NULL,
    scanned_at TEXT NOT NULL
)
"""

CREATE_SCAN_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_path TEXT NOT NULL,
    raw_result TEXT NOT NULL,
    confirmed_result TEXT,
    created_at TEXT NOT NULL
)
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute(CREATE_CATALOG_TABLE)
    conn.execute(CREATE_INVENTORY_TABLE)
    conn.execute(CREATE_SCAN_HISTORY_TABLE)
    conn.commit()


def upsert_catalog_item(
    conn: sqlite3.Connection,
    sku_id: str,
    name: str,
    price: int,
    shelf_full_qty: int,
    embedding_path: str,
) -> None:
    conn.execute(
        """
        INSERT INTO catalog (sku_id, name, price, shelf_full_qty, embedding_path)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(sku_id) DO UPDATE SET
            name = excluded.name,
            price = excluded.price,
            shelf_full_qty = excluded.shelf_full_qty,
            embedding_path = excluded.embedding_path
        """,
        (sku_id, name, price, shelf_full_qty, embedding_path),
    )
    conn.commit()


def get_catalog_item(conn: sqlite3.Connection, sku_id: str) -> Optional[Dict]:
    row = conn.execute(
        "SELECT sku_id, name, price, shelf_full_qty, embedding_path FROM catalog WHERE sku_id = ?",
        (sku_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "sku_id": row[0],
        "name": row[1],
        "price": row[2],
        "shelf_full_qty": row[3],
        "embedding_path": row[4],
    }


def list_catalog(conn: sqlite3.Connection) -> List[Dict]:
    rows = conn.execute(
        "SELECT sku_id, name, price, shelf_full_qty, embedding_path FROM catalog"
    ).fetchall()
    return [
        {
            "sku_id": r[0],
            "name": r[1],
            "price": r[2],
            "shelf_full_qty": r[3],
            "embedding_path": r[4],
        }
        for r in rows
    ]


def insert_scan_history(
    conn: sqlite3.Connection,
    image_path: str,
    raw_result: str,
    confirmed_result: Optional[str],
    created_at: str,
) -> None:
    conn.execute(
        "INSERT INTO scan_history (image_path, raw_result, confirmed_result, created_at) VALUES (?, ?, ?, ?)",
        (image_path, raw_result, confirmed_result, created_at),
    )
    conn.commit()


def insert_inventory_records(conn: sqlite3.Connection, records: List[Dict], scanned_at: str) -> None:
    conn.executemany(
        "INSERT INTO inventory (sku_id, quantity, value, status, scanned_at) VALUES (?, ?, ?, ?, ?)",
        [(r["sku_id"], r["quantity"], r["value"], r["status"], scanned_at) for r in records],
    )
    conn.commit()
