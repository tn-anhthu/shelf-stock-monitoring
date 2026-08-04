// flag_status thresholds -- docs/adr/0002-analyze-endpoint-schema.md

const LOW_STOCK_RATIO = 0.3;

function computeFlagStatus(totalQuantity, shelfFullQty) {
  if (totalQuantity === 0) return 'out';
  if (totalQuantity < LOW_STOCK_RATIO * shelfFullQty) return 'low';
  return 'ok';
}

module.exports = { LOW_STOCK_RATIO, computeFlagStatus };
