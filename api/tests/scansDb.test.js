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
    expect(columns).toEqual(['scan_id', 'category', 'container', 'quantities', 'total_value', 'confirmed_at', 'boxes', 'last_updated_at']);
    db.close();
  });
});

describe('scansDb boxes + confirmed_at/last_updated_at', () => {
  let dbPath;

  beforeEach(() => {
    dbPath = path.join(os.tmpdir(), `scans-boxes-test-${crypto.randomUUID()}.db`);
  });

  afterEach(() => {
    fs.rmSync(dbPath, { force: true });
  });

  test('stores boxes as JSON and returns them parsed', () => {
    const { insertScan, getScanById, db } = createScansDb(dbPath);
    const boxes = [{ box_id: 'b1', type: 'gap', bbox: [1, 2, 3, 4], sku_id: null, needs_review: false }];
    insertScan({ scanId: 's1', category: 'mi-goi', container: 'ke-a', quantities: [], totalValue: 0, boxes });
    expect(getScanById('s1').boxes).toEqual(boxes);
    db.close();
  });

  test('defaults boxes to [] when omitted on a brand-new scan_id', () => {
    const { insertScan, getScanById, db } = createScansDb(dbPath);
    insertScan({ scanId: 's2', category: 'mi-goi', container: 'ke-a', quantities: [], totalValue: 0 });
    expect(getScanById('s2').boxes).toEqual([]);
    db.close();
  });

  test('preserves existing boxes when insertScan is called again without a boxes argument', () => {
    const { insertScan, getScanById, db } = createScansDb(dbPath);
    const boxes = [{ box_id: 'b1', type: 'gap', bbox: [1, 2, 3, 4], sku_id: null, needs_review: false }];
    insertScan({ scanId: 's3', category: 'mi-goi', container: 'ke-a', quantities: [{ sku_id: 'a' }], totalValue: 0, boxes });
    insertScan({ scanId: 's3', category: 'mi-goi', container: 'ke-a', quantities: [{ sku_id: 'a' }, { sku_id: 'b' }], totalValue: 100 });
    expect(getScanById('s3').boxes).toEqual(boxes);
    db.close();
  });

  test('keeps the original confirmed_at across repeat inserts, but bumps last_updated_at', () => {
    const { insertScan, getScanById, db } = createScansDb(dbPath);
    insertScan({ scanId: 's4', category: 'mi-goi', container: 'ke-a', quantities: [], totalValue: 0 });
    const first = getScanById('s4');

    insertScan({ scanId: 's4', category: 'mi-goi', container: 'ke-a', quantities: [{ sku_id: 'x' }], totalValue: 10 });
    const second = getScanById('s4');

    expect(second.confirmed_at).toBe(first.confirmed_at);
    expect(second.last_updated_at >= first.last_updated_at).toBe(true);
    db.close();
  });

  test('adds boxes and last_updated_at columns to a pre-existing DB missing them, backfilling last_updated_at from confirmed_at', () => {
    const legacyDb = new Database(dbPath);
    legacyDb.exec(`
      CREATE TABLE scans (
        scan_id TEXT PRIMARY KEY,
        category TEXT NOT NULL,
        container TEXT NOT NULL,
        quantities TEXT NOT NULL,
        total_value REAL NOT NULL,
        confirmed_at TEXT NOT NULL
      )
    `);
    legacyDb
      .prepare(
        `INSERT INTO scans (scan_id, category, container, quantities, total_value, confirmed_at)
         VALUES (@scanId, @category, @container, @quantities, @totalValue, @confirmedAt)`,
      )
      .run({ scanId: 'old-1', category: 'mi-goi', container: 'ke-a', quantities: '[]', totalValue: 0, confirmedAt: '2026-08-01T00:00:00.000Z' });
    legacyDb.close();

    const { getScanById, db } = createScansDb(dbPath);
    const migrated = getScanById('old-1');
    expect(migrated.boxes).toEqual([]);
    expect(migrated.last_updated_at).toBe('2026-08-01T00:00:00.000Z');
    db.close();
  });
});
