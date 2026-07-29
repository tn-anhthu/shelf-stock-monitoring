export function computeTotalValue(quantities) {
  return quantities.reduce((sum, q) => sum + q.facing_count * (q.depth ?? 1) * q.unit_price, 0);
}

export function isDuplicateSku(quantities, skuId) {
  return quantities.some((q) => q.sku_id === skuId);
}
