import { computeTotalValue } from './quantities.js';
import Button from '../../shared/ui/Button.jsx';

const currency = (n) => n.toLocaleString('vi-VN') + ' đ';

export default function ConfirmStep({
  storeId,
  shelfId,
  quantities,
  confirming,
  confirmError,
  confirmed,
  onConfirm,
  onReset,
}) {
  const totalValue = computeTotalValue(quantities);

  if (confirmed) {
    return (
      <div className="space-y-4">
        <p className="rounded-lg bg-status-ok-bg px-4 py-3 text-status-ok-text">
          Đã lưu kết quả quét kệ {shelfId} tại {storeId}.
        </p>
        <Button type="button" variant="outline" onClick={onReset}>
          Quét kệ khác
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="font-heading text-lg font-semibold text-ink">4. Xác nhận</h2>
      <p className="text-text-secondary">
        Store: {storeId} — Shelf: {shelfId}
      </p>

      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-card-border text-left text-text-muted">
            <th className="py-2 font-medium">Sản phẩm</th>
            <th className="font-medium">Số lượng</th>
            <th className="font-medium">Thành tiền</th>
          </tr>
        </thead>
        <tbody>
          {quantities.map((q, index) => (
            <tr key={`${q.sku_id}-${index}`} className="border-b border-card-border">
              <td className="py-2 text-ink">{q.sku_name}</td>
              <td className="text-ink">{q.facing_count}</td>
              <td className="text-ink">{currency(q.facing_count * (q.depth ?? 1) * q.unit_price)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="font-heading text-lg font-semibold text-ink">Tổng giá trị: {currency(totalValue)}</p>

      {confirmError && (
        <p className="rounded-lg bg-status-out-bg px-3 py-2 text-status-out-text">
          Lưu thất bại: {confirmError} — dữ liệu đã sửa vẫn được giữ nguyên, có thể thử lại.
        </p>
      )}

      <Button type="button" onClick={onConfirm} disabled={confirming} className="w-full md:w-auto">
        {confirming ? 'Đang lưu…' : confirmError ? 'Thử lại' : 'Xác nhận'}
      </Button>
    </div>
  );
}
