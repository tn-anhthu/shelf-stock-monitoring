// KPI / status-breakdown / attention-list computation for the Inventory page.
// docs/superpowers/specs/2026-08-10-dashboard-design.md §4.3-4.4.

const { findMissingItemSuggestions } = require('./neighborInference');

function computeMissedValue(item) {
  if (item.flag_status === 'ok') return 0;
  return Math.max(0, (item.shelf_full_qty - item.total_quantity) * item.unit_price);
}

function computeKpis(quantities) {
  const totalValue = quantities.reduce((sum, q) => sum + (q.subtotal ?? 0), 0);
  const totalSkuCount = quantities.length;
  const okCount = quantities.filter((q) => q.flag_status === 'ok').length;
  const stockHealthPct = totalSkuCount === 0 ? 0 : Math.round((okCount / totalSkuCount) * 100);
  const missedOpportunityTotal = quantities.reduce((sum, q) => sum + computeMissedValue(q), 0);

  return {
    total_value: totalValue,
    total_sku_count: totalSkuCount,
    stock_health_pct: stockHealthPct,
    missed_opportunity_total: missedOpportunityTotal,
  };
}

function computeStatusBreakdown(quantities) {
  return {
    ok: quantities.filter((q) => q.flag_status === 'ok').length,
    low: quantities.filter((q) => q.flag_status === 'low').length,
    out: quantities.filter((q) => q.flag_status === 'out').length,
  };
}

const ATTENTION_ORDER = { out: 0, low: 1 };

function computeAttentionList(quantities) {
  return quantities
    .filter((q) => q.flag_status === 'out' || q.flag_status === 'low')
    .map((q) => ({ ...q, missed_value: computeMissedValue(q) }))
    .sort((a, b) => {
      const orderDiff = ATTENTION_ORDER[a.flag_status] - ATTENTION_ORDER[b.flag_status];
      if (orderDiff !== 0) return orderDiff;
      return b.missed_value - a.missed_value;
    });
}

function buildDashboardPayload(scanRow, catalog) {
  if (!scanRow) {
    return { has_data: false };
  }

  const { quantities } = scanRow;
  return {
    has_data: true,
    scan_id: scanRow.scan_id,
    confirmed_at: scanRow.confirmed_at,
    image_url: scanRow.image_path ? `/uploads/${scanRow.image_path}` : null,
    image_width: scanRow.image_width ?? null,
    image_height: scanRow.image_height ?? null,
    kpis: computeKpis(quantities),
    status_breakdown: computeStatusBreakdown(quantities),
    attention_list: computeAttentionList(quantities),
    full_table: quantities,
    missing_items: findMissingItemSuggestions(scanRow, catalog),
  };
}

module.exports = { computeMissedValue, computeKpis, computeStatusBreakdown, computeAttentionList, buildDashboardPayload };
