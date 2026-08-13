export default function StatusBar({ ok, low, out }) {
  const total = ok + low + out;

  return (
    <div>
      <div
        className="grid h-2.5 gap-1"
        style={{ gridTemplateColumns: `${ok}fr ${low}fr ${out}fr` }}
      >
        <div className="rounded-sm bg-status-ok-bar" />
        <div className="rounded-sm bg-status-low-bar" />
        <div className="rounded-sm bg-status-out-bar" />
      </div>
      <div className="mt-2.5 flex flex-wrap gap-4 text-xs text-text-secondary">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm bg-status-ok-bar" />
          Đủ: <b className="font-bold text-ink">{ok}</b>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm bg-status-low-bar" />
          Sắp hết: <b className="font-bold text-ink">{low}</b>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm bg-status-out-bar" />
          Hết hàng: <b className="font-bold text-ink">{out}</b>
        </span>
        {total === 0 && <span className="text-text-muted">Chưa có dữ liệu trạng thái.</span>}
      </div>
    </div>
  );
}
