// Attention-first ordering, matching the approved comp: Hết hàng/Sắp hết first (by missed
// value descending, from the server), then Đủ ascending by tồn kho (docs/superpowers/specs
// /2026-08-10-dashboard-design.md §5, .impeccable/mocks/comp-c.json revision "Round 5").
export function buildAttentionFirstRows(dashboard) {
  if (!dashboard?.has_data) return [];
  const attentionIds = new Set(dashboard.attention_list.map((q) => q.sku_id));
  const okRows = dashboard.full_table
    .filter((q) => !attentionIds.has(q.sku_id))
    .slice()
    .sort((a, b) => a.total_quantity - b.total_quantity)
    .map((q) => ({ ...q, missed_value: 0 }));
  return [...dashboard.attention_list, ...okRows];
}
