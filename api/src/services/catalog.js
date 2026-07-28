const fs = require('node:fs');
const path = require('node:path');
const { parse } = require('csv-parse/sync');

const CATALOG_PATH =
  process.env.CATALOG_PATH ||
  path.resolve(__dirname, '..', '..', '..', 'data', 'catalog', 'catalog_seed.csv');

function loadCatalog(catalogPath = CATALOG_PATH) {
  const csvText = fs.readFileSync(catalogPath, 'utf8');
  const rows = parse(csvText, { columns: true, skip_empty_lines: true });

  const catalog = new Map();
  for (const row of rows) {
    catalog.set(row.sku_id, {
      name: row.name,
      price: Number(row.price),
      shelfFullQty: Number(row.shelf_full_qty),
    });
  }
  return catalog;
}

// Parsed once at module load and cached for the life of the process.
const catalog = loadCatalog();

module.exports = { catalog, loadCatalog, CATALOG_PATH };
