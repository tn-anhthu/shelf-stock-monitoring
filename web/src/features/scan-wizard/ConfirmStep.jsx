import Button from '../../shared/ui/Button.jsx';

export default function ConfirmStep({
  category,
  container,
  quantities,
  confirming,
  confirmError,
  confirmed,
  onConfirm,
  onReset,
}) {
  if (confirmed) {
    return (
      <div className="space-y-4">
        <p className="font-medium text-status-ok">
          Đã lưu kết quả quét container {container} tại category {category}.
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
        Category: {category} — Container: {container}
      </p>

      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-ink text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
            <th className="py-2 font-semibold">Sản phẩm</th>
            <th className="font-semibold">Số lượng</th>
          </tr>
        </thead>
        <tbody>
          {quantities.map((q, index) => (
            <tr key={`${q.sku_id}-${index}`} className="border-b border-card-border">
              <td className="py-2 text-ink">{q.sku_name}</td>
              <td className="text-ink">{q.facing_count}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="space-y-3 border-t border-card-border pt-3">
        {confirmError && (
          <p className="text-status-out">
            Lưu thất bại: {confirmError} — dữ liệu đã sửa vẫn được giữ nguyên, có thể thử lại.
          </p>
        )}

        <button
          type="button"
          onClick={onConfirm}
          disabled={confirming}
          className="flex w-full items-center justify-center border-b-2 border-ink pb-2 text-lg font-heading font-semibold text-ink transition disabled:cursor-not-allowed disabled:opacity-50 md:w-auto md:justify-start"
        >
          {confirming ? 'Đang lưu…' : confirmError ? 'Thử lại' : 'Xác nhận'}
        </button>
      </div>
    </div>
  );
}
