import { computeTotalValue } from './quantities.js';

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
        <p className="rounded bg-emerald-50 px-4 py-3 text-emerald-800">
          Đã lưu kết quả quét kệ {shelfId} tại {storeId}.
        </p>
        <button type="button" onClick={onReset} className="rounded border px-4 py-2">
          Quét kệ khác
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">4. Xác nhận</h2>
      <p>
        Store: {storeId} — Shelf: {shelfId}
      </p>

      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b text-left">
            <th className="py-2">Sản phẩm</th>
            <th>Số lượng</th>
            <th>Thành tiền</th>
          </tr>
        </thead>
        <tbody>
          {quantities.map((q, index) => (
            <tr key={`${q.sku_id}-${index}`} className="border-b">
              <td className="py-2">{q.sku_name}</td>
              <td>{q.facing_count}</td>
              <td>{currency(q.facing_count * (q.depth ?? 1) * q.unit_price)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="text-lg font-semibold">Tổng giá trị: {currency(totalValue)}</p>

      {confirmError && (
        <p className="rounded bg-red-50 px-3 py-2 text-red-700">
          Lưu thất bại: {confirmError} — dữ liệu đã sửa vẫn được giữ nguyên, có thể thử lại.
        </p>
      )}

      <button
        type="button"
        onClick={onConfirm}
        disabled={confirming}
        className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
      >
        {confirming ? 'Đang lưu…' : confirmError ? 'Thử lại' : 'Xác nhận'}
      </button>
    </div>
  );
}
