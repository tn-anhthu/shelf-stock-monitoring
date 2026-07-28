const crypto = require('node:crypto');
const { computeFlagStatus } = require('../config/flagStatus');

const DEPTH = 1; // pipeline doesn't estimate depth yet -- docs/adr/0002

// Groups product boxes by sku_id and joins price/shelf_full_qty from the
// catalog. Boxes with no sku_id (gap, unknown) or a sku_id missing from the
// catalog are left out -- there's no price to attach to them.
function aggregateQuantities(boxes, catalog) {
  const bySku = new Map();

  for (const box of boxes) {
    if (box.type !== 'product' || !box.sku_id) continue;
    const catalogEntry = catalog.get(box.sku_id);
    if (!catalogEntry) continue;

    const existing = bySku.get(box.sku_id);
    if (existing) {
      existing.facing_count += 1;
    } else {
      bySku.set(box.sku_id, {
        sku_id: box.sku_id,
        sku_name: box.sku_name || catalogEntry.name,
        facing_count: 1,
        unit_price: catalogEntry.price,
        shelf_full_qty: catalogEntry.shelfFullQty,
      });
    }
  }

  return Array.from(bySku.values()).map((entry) => {
    const totalQuantity = entry.facing_count * DEPTH;
    const subtotal = totalQuantity * entry.unit_price;
    return {
      sku_id: entry.sku_id,
      sku_name: entry.sku_name,
      facing_count: entry.facing_count,
      depth: DEPTH,
      total_quantity: totalQuantity,
      shelf_full_qty: entry.shelf_full_qty,
      unit_price: entry.unit_price,
      subtotal,
      flag_status: computeFlagStatus(totalQuantity, entry.shelf_full_qty),
    };
  });
}

function buildSuccessResult({ storeId, shelfId, mlResult, catalog }) {
  const quantities = aggregateQuantities(mlResult.boxes, catalog);
  const totalValue = quantities.reduce((sum, q) => sum + q.subtotal, 0);
  const status = mlResult.boxes.some((box) => box.is_unknown) ? 'partial' : 'ok';

  return {
    scan_id: crypto.randomUUID(),
    store_id: storeId,
    shelf_id: shelfId,
    timestamp: new Date().toISOString(),
    status,
    error_message: null,
    image: mlResult.image,
    boxes: mlResult.boxes,
    quantities,
    warnings: mlResult.warnings,
    total_value: totalValue,
  };
}

function buildFailedResult({ storeId, shelfId, errorMessage }) {
  return {
    scan_id: crypto.randomUUID(),
    store_id: storeId,
    shelf_id: shelfId,
    timestamp: new Date().toISOString(),
    status: 'failed',
    error_message: errorMessage,
    image: { width: 0, height: 0 },
    boxes: [],
    quantities: [],
    warnings: { low_confidence_regions: [], edge_crop_regions: [], blur_detected: false },
    total_value: 0,
  };
}

module.exports = { aggregateQuantities, buildSuccessResult, buildFailedResult };
