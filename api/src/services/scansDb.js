const path = require('node:path');
const Database = require('better-sqlite3');

function defaultDbPath() {
  if (process.env.SCANS_DB_PATH) return process.env.SCANS_DB_PATH;
  if (process.env.NODE_ENV === 'test') return ':memory:';
  return path.resolve(__dirname, '..', '..', 'scans.db');
}

function createScansDb(dbPath = defaultDbPath()) {
  const db = new Database(dbPath);
  db.exec(`
    CREATE TABLE IF NOT EXISTS scans (
      scan_id TEXT PRIMARY KEY,
      store_id TEXT NOT NULL,
      shelf_id TEXT NOT NULL,
      quantities TEXT NOT NULL,
      total_value REAL NOT NULL,
      confirmed_at TEXT NOT NULL
    )
  `);

  function insertScan({ scanId, storeId, shelfId, quantities, totalValue }) {
    db.prepare(
      `INSERT OR REPLACE INTO scans (scan_id, store_id, shelf_id, quantities, total_value, confirmed_at)
       VALUES (@scanId, @storeId, @shelfId, @quantities, @totalValue, @confirmedAt)`,
    ).run({
      scanId,
      storeId,
      shelfId,
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

  function getLatestScan(storeId, shelfId) {
    const row = db
      .prepare(
        'SELECT * FROM scans WHERE store_id = ? AND shelf_id = ? ORDER BY confirmed_at DESC LIMIT 1',
      )
      .get(storeId, shelfId);
    if (!row) return null;
    return { ...row, quantities: JSON.parse(row.quantities) };
  }

  return { db, insertScan, getScanById, getLatestScan };
}

const scansDb = createScansDb();

module.exports = { createScansDb, scansDb };
