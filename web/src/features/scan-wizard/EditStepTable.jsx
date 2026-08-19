import { isDuplicateSku } from './quantities.js';

function StatusText({ status }) {
  if (status === 'ok') return <span className="font-bold text-status-ok">Đủ</span>;
  if (status === 'low') return <span className="font-bold text-status-low">Sắp hết</span>;
  if (status === 'out') {
    return (
      <span className="inline-block rounded-sm border border-status-out px-1.5 py-0.5 text-xs font-black uppercase tracking-wide text-status-out">
        Hết hàng
      </span>
    );
  }
  return <span className="text-text-muted">—</span>;
}

export default function EditStepTable({
  quantities,
  catalog,
  onQuantityChange,
  onSkuChange,
  onRemoveRow,
  hoveredSkuId,
  onRowHover,
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[600px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-ink text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
            <th className="whitespace-nowrap py-2 pr-2 font-semibold">#</th>
            <th className="whitespace-nowrap py-2 pr-2 font-semibold">Sản phẩm</th>
            <th className="whitespace-nowrap pr-2 font-semibold">SKU</th>
            <th className="whitespace-nowrap pr-2 font-semibold">Số lượng</th>
            <th className="whitespace-nowrap pr-2 font-semibold">Trạng thái</th>
            <th className="pr-2" />
          </tr>
        </thead>
        <tbody>
          {quantities.map((q, index) => {
            const otherRows = quantities.filter((_, i) => i !== index);
            const skuOptions = catalog.filter(
              (item) => item.sku_id === q.sku_id || !isDuplicateSku(otherRows, item.sku_id),
            );
            return (
              <tr
                key={`${q.sku_id}-${index}`}
                onMouseEnter={() => onRowHover(q.sku_id)}
                onMouseLeave={() => onRowHover(null)}
                className={`border-b border-card-border ${hoveredSkuId === q.sku_id ? 'bg-page' : ''}`}
              >
                <td className="py-2.5 pr-2 text-text-secondary">{index + 1}</td>
                <td className="py-2.5 pr-2">
                  <select
                    value={q.sku_id}
                    onChange={(e) => onSkuChange(index, e.target.value)}
                    className="border-0 border-b border-ink bg-transparent px-0 py-1 font-heading font-medium text-ink focus:outline-none"
                  >
                    {skuOptions.map((item) => (
                      <option key={item.sku_id} value={item.sku_id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="whitespace-nowrap pr-2 text-text-secondary">{q.sku_id}</td>
                <td className="pr-2">
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => onQuantityChange(index, String(Math.max(0, q.facing_count - 1)))}
                      className="h-6 w-6 border border-card-border text-ink"
                    >
                      −
                    </button>
                    <input
                      type="number"
                      min="0"
                      step="1"
                      value={q.facing_count}
                      onChange={(e) => onQuantityChange(index, e.target.value)}
                      className="w-14 border-0 border-b border-ink bg-transparent px-0 py-1 text-center focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => onQuantityChange(index, String(q.facing_count + 1))}
                      className="h-6 w-6 border border-card-border text-ink"
                    >
                      +
                    </button>
                  </div>
                </td>
                <td className="whitespace-nowrap pr-2">
                  <StatusText status={q.flag_status} />
                </td>
                <td className="pr-2">
                  <button type="button" onClick={() => onRemoveRow(index)} className="text-status-out">
                    Xóa
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
