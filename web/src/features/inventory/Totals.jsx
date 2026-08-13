const currency = (n) => Math.round(n).toLocaleString('vi-VN') + 'đ';

export default function Totals({ kpis }) {
  return (
    <div className="mt-6 max-w-md border-t-4 border-double border-border-strong pt-3 sm:ml-auto">
      <div className="flex justify-between border-b border-card-border py-1.5 text-sm">
        <span>Tổng SKU</span>
        <span className="font-semibold text-ink">{kpis.total_sku_count}</span>
      </div>
      <div className="flex justify-between border-b border-card-border py-1.5 text-sm">
        <span>Tồn kho khỏe (stock health)</span>
        <span className="font-semibold text-ink">{kpis.stock_health_pct}%</span>
      </div>
      <div className="flex justify-between border-b border-card-border py-1.5 text-sm">
        <span>Tổng giá trị tồn</span>
        <span className="font-semibold text-ink">{currency(kpis.total_value)}</span>
      </div>
      <div className="flex justify-between pt-2.5 text-lg font-bold text-ink">
        <span>
          Giá trị bỏ lỡ <span className="text-xs font-normal text-text-secondary">(ước tính)</span>
        </span>
        <span>{currency(kpis.missed_opportunity_total)}</span>
      </div>
    </div>
  );
}
