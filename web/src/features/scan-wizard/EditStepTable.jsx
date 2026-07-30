import { isDuplicateSku } from './quantities.js';
import StatusChip from '../../shared/ui/StatusChip.jsx';

const currency = (n) => n.toLocaleString('vi-VN') + ' đ';

export default function EditStepTable({ quantities, catalog, onQuantityChange, onSkuChange, onRemoveRow }) {
  return (
    <table className="hidden w-full border-collapse text-sm md:table">
      <thead>
        <tr className="border-b border-card-border text-left text-text-muted">
          <th className="py-2 font-medium">Sản phẩm</th>
          <th className="font-medium">SKU</th>
          <th className="font-medium">Số lượng</th>
          <th className="font-medium">Đơn giá</th>
          <th className="font-medium">Thành tiền</th>
          <th className="font-medium">Trạng thái</th>
          <th />
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
            <tr key={`${q.sku_id}-${index}`} className="border-b border-card-border">
              <td className="py-2 font-heading font-medium text-ink">{q.sku_name}</td>
              <td>
                <select
                  value={q.sku_id}
                  onChange={(e) => onSkuChange(index, e.target.value)}
                  className="rounded-lg border border-card-border px-2 py-1"
                >
                  {skuOptions.map((item) => (
                    <option key={item.sku_id} value={item.sku_id}>
                      {item.sku_id}
                    </option>
                  ))}
                </select>
              </td>
              <td>
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
              <td className="text-text-secondary">{currency(q.unit_price)}</td>
              <td className="font-heading font-medium text-ink">{currency(q.facing_count * depth * q.unit_price)}</td>
              <td>
                <StatusChip status={q.flag_status} />
              </td>
              <td>
                <button type="button" onClick={() => onRemoveRow(index)} className="text-status-out-text">
                  Xóa
                </button>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
