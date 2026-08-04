import { isDuplicateSku } from './quantities.js';
import StatusChip from '../../shared/ui/StatusChip.jsx';

const currency = (n) => n.toLocaleString('vi-VN') + ' đ';

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
      <table className="w-full min-w-[760px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-card-border text-left text-text-muted">
            <th className="whitespace-nowrap py-2 pr-4 font-medium">Sản phẩm</th>
            <th className="whitespace-nowrap pr-4 font-medium">SKU</th>
            <th className="whitespace-nowrap pr-4 font-medium">Số lượng</th>
            <th className="whitespace-nowrap pr-4 font-medium">Đơn giá</th>
            <th className="whitespace-nowrap pr-4 font-medium">Thành tiền</th>
            <th className="whitespace-nowrap pr-4 font-medium">Trạng thái</th>
            <th className="pr-2" />
          </tr>
        </thead>
        <tbody>
          {quantities.map((q, index) => {
            const otherRows = quantities.filter((_, i) => i !== index);
            const skuOptions = catalog.filter(
              (item) => item.sku_id === q.sku_id || !isDuplicateSku(otherRows, item.sku_id),
            );
            const depth = q.depth ?? 1;
            return (
              <tr
                key={`${q.sku_id}-${index}`}
                onMouseEnter={() => onRowHover(q.sku_id)}
                onMouseLeave={() => onRowHover(null)}
                className={`border-b border-card-border ${hoveredSkuId === q.sku_id ? 'bg-page' : ''}`}
              >
                <td className="py-2 pr-4">
                  <select
                    value={q.sku_id}
                    onChange={(e) => onSkuChange(index, e.target.value)}
                    className="rounded-lg border border-card-border px-2 py-1 font-heading font-medium text-ink"
                  >
                    {skuOptions.map((item) => (
                      <option key={item.sku_id} value={item.sku_id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="whitespace-nowrap pr-4 text-text-secondary">{q.sku_id}</td>
                <td className="pr-4">
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => onQuantityChange(index, String(Math.max(0, q.facing_count - 1)))}
                      className="h-6 w-6 rounded-md border border-card-border bg-white"
                    >
                      −
                    </button>
                    <input
                      type="number"
                      min="0"
                      step="1"
                      value={q.facing_count}
                      onChange={(e) => onQuantityChange(index, e.target.value)}
                      className="w-14 rounded-lg border border-card-border px-2 py-1 text-center"
                    />
                    <button
                      type="button"
                      onClick={() => onQuantityChange(index, String(q.facing_count + 1))}
                      className="h-6 w-6 rounded-md border border-card-border bg-white"
                    >
                      +
                    </button>
                  </div>
                </td>
                <td className="whitespace-nowrap pr-4 text-text-secondary">{currency(q.unit_price)}</td>
                <td className="whitespace-nowrap pr-4 font-heading font-medium text-ink">
                  {currency(q.facing_count * depth * q.unit_price)}
                </td>
                <td className="whitespace-nowrap pr-4">
                  <StatusChip status={q.flag_status} />
                </td>
                <td className="pr-2">
                  <button type="button" onClick={() => onRemoveRow(index)} className="text-status-out-text">
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
