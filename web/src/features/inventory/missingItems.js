export function buildConfirmationRow(gapBoxId, skuId, catalogEntry) {
  return {
    sku_id: skuId,
    sku_name: catalogEntry.name,
    facing_count: 0,
    depth: 1,
    total_quantity: 0,
    shelf_full_qty: catalogEntry.shelf_full_qty,
    unit_price: catalogEntry.price,
    subtotal: 0,
    flag_status: 'out',
    source: 'oos_confirmation',
    source_gap_box_id: gapBoxId,
  };
}

export function isGapResolved(gapBoxId, quantities) {
  return quantities.some((q) => q.source_gap_box_id === gapBoxId);
}
