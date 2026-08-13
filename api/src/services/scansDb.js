const path = require('node:path');
const Database = require('better-sqlite3');

function defaultDbPath() {
  if (process.env.SCANS_DB_PATH) return process.env.SCANS_DB_PATH;
  if (process.env.NODE_ENV === 'test') return ':memory:';
  return path.resolve(__dirname, '..', '..', 'scans.db');
}

function createScansDb(dbPath = defaultDbPath()) {
  const db = new Database(dbPath);

  // Migrate a pre-rename DB in place (see
  // docs/superpowers/specs/2026-08-13-category-container-naming-design.md §3)
  // -- idempotent: only runs when the old column still exists, so re-running
  // this against an already-migrated or brand-new DB is a no-op.
  const existingColumns = db.prepare('PRAGMA table_info(scans)').all();
  const hasOldColumn = existingColumns.some((col) => col.name === 'store_id');
  if (hasOldColumn) {
    db.exec(`
      BEGIN;
      ALTER TABLE scans RENAME COLUMN store_id TO category;
      ALTER TABLE scans RENAME COLUMN shelf_id TO container;
      COMMIT;
    `);
  }

  db.exec(`
    CREATE TABLE IF NOT EXISTS scans (
      scan_id TEXT PRIMARY KEY,
      category TEXT NOT NULL,
      container TEXT NOT NULL,
      quantities TEXT NOT NULL,
      total_value REAL NOT NULL,
      confirmed_at TEXT NOT NULL
    )
  `);

  function insertScan({ scanId, category, container, quantities, totalValue }) {
    db.prepare(
      `INSERT OR REPLACE INTO scans (scan_id, category, container, quantities, total_value, confirmed_at)
       VALUES (@scanId, @category, @container, @quantities, @totalValue, @confirmedAt)`,
    ).run({
      scanId,
      category,
      container,
      quantities: JSON.stringify(quantities),
      totalValue,
      confirmedAt: new Date().toISOString(),
    });
  }

  function getScanById(scanId) {
    const row = db.prepare('SELECT * FROM scans WHERE scan_id = ?').get(scanId);
    if (!row) return null;
    return { ...row, quantities: JSON.parse(row.quantities) };
  }

  function getLatestScan(category, container) {
    const row = db
      .prepare(
        'SELECT * FROM scans WHERE category = ? AND container = ? ORDER BY confirmed_at DESC LIMIT 1',
      )
      .get(category, container);
    if (!row) return null;
    return { ...row, quantities: JSON.parse(row.quantities) };
  }

  return { db, insertScan, getScanById, getLatestScan };
}

const scansDb = createScansDb();

module.exports = { createScansDb, scansDb };
