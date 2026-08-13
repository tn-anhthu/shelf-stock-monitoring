const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const Database = require('better-sqlite3');
const { createScansDb } = require('../src/services/scansDb');

describe('scansDb migration', () => {
  let dbPath;

  beforeEach(() => {
    dbPath = path.join(os.tmpdir(), `scans-migration-test-${crypto.randomUUID()}.db`);
  });

  afterEach(() => {
    fs.rmSync(dbPath, { force: true });
  });

  test('renames store_id/shelf_id to category/container on an old-schema DB, keeping data intact', () => {
    // Simulate a real scans.db still on the pre-rename schema (see
    // docs/superpowers/specs/2026-08-13-category-container-naming-design.md §3).
    const legacyDb = new Database(dbPath);
    legacyDb.exec(`
      CREATE TABLE scans (
        scan_id TEXT PRIMARY KEY,
        store_id TEXT NOT NULL,
        shelf_id TEXT NOT NULL,
        quantities TEXT NOT NULL,
        total_value REAL NOT NULL,
        confirmed_at TEXT NOT NULL
      )
    `);
    legacyDb
      .prepare(
        `INSERT INTO scans (scan_id, store_id, shelf_id, quantities, total_value, confirmed_at)
         VALUES (@scanId, @storeId, @shelfId, @quantities, @totalValue, @confirmedAt)`,
      )
      .run({
        scanId: 'legacy-scan-1',
        storeId: 'mi-goi',
        shelfId: 'ke-a',
        quantities: JSON.stringify([{ sku_id: 'a' }]),
        totalValue: 100,
        confirmedAt: '2026-08-01T00:00:00.000Z',
      });
    legacyDb.close();

    const { db, getScanById } = createScansDb(dbPath);

    const columns = db.prepare('PRAGMA table_info(scans)').all().map((col) => col.name);
    expect(columns).toContain('category');
    expect(columns).toContain('container');
    expect(columns).not.toContain('store_id');
    expect(columns).not.toContain('shelf_id');

    const migrated = getScanById('legacy-scan-1');
    expect(migrated.category).toBe('mi-goi');
    expect(migrated.container).toBe('ke-a');
    expect(migrated.total_value).toBe(100);
    expect(migrated.quantities).toEqual([{ sku_id: 'a' }]);

    db.close();
  });

  test('creates a fresh DB with category/container columns directly when no file exists yet', () => {
    const { db } = createScansDb(dbPath);
    const columns = db.prepare('PRAGMA table_info(scans)').all().map((col) => col.name);
    expect(columns).toEqual(['scan_id', 'category', 'container', 'quantities', 'total_value', 'confirmed_at']);
    db.close();
  });
});
