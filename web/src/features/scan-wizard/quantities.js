export function buildEmptyRow() {
  return {
    sku_id: null,
    sku_name: null,
    facing_count: 0,
    depth: 1,
    total_quantity: 0,
    shelf_full_qty: null,
    unit_price: null,
    subtotal: 0,
    flag_status: null,
  };
}

export function computeTotalValue(quantities) {
  return quantities.reduce((sum, q) => sum + q.facing_count * (q.depth ?? 1) * q.unit_price, 0);
}

export function isDuplicateSku(quantities, skuId) {
  return quantities.some((q) => q.sku_id === skuId);
}
