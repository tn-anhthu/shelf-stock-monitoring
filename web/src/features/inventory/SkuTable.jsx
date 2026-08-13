import { useMemo, useState } from 'react';

const GRID_COLS = 'grid-cols-[1fr_64px_128px_104px]';

const formatMissed = (n) => `~${Math.round(n).toLocaleString('vi-VN')}đ`;

function StatusCell({ status }) {
  if (status === 'ok') return <span className="text-right font-bold text-status-ok">Đủ</span>;
  if (status === 'low') return <span className="text-right font-bold text-status-low">Sắp hết</span>;
  if (status === 'out') {
    return (
      <span className="justify-self-end whitespace-nowrap rounded-sm border border-status-out px-1.5 py-0.5 text-xs font-black uppercase tracking-wide text-status-out">
        Hết hàng
      </span>
    );
  }
  return <span className="text-right text-text-muted">—</span>;
}

const STATUS_FILTERS = [
  { value: 'all', label: 'Tất cả trạng thái' },
  { value: 'ok', label: 'Đủ' },
  { value: 'low', label: 'Sắp hết' },
  { value: 'out', label: 'Hết hàng' },
];

export default function SkuTable({ rows }) {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase();
    return rows.filter((q) => {
      if (statusFilter !== 'all' && (q.flag_status ?? 'ok') !== statusFilter) return false;
      if (query && !q.sku_name.toLowerCase().includes(query)) return false;
      return true;
    });
  }, [rows, search, statusFilter]);

  return (
    <div>
      <div className="flex flex-col gap-3 sm:flex-row sm:gap-5">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Tìm theo tên SKU"
          className="flex-1 border-0 border-b border-ink bg-transparent py-1.5 text-sm text-ink placeholder:text-text-muted focus:outline-none sm:max-w-xs"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border-0 border-b border-ink bg-transparent py-1.5 text-sm text-ink focus:outline-none sm:w-40"
        >
          {STATUS_FILTERS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-5 border-t border-ink">
        <div
          className={`sticky top-0 z-10 hidden ${GRID_COLS} gap-3 border-b border-ink bg-page py-2.5 text-[10px] font-bold uppercase tracking-wide text-text-secondary sm:grid`}
        >
          <div>SKU</div>
          <div className="text-right">Tồn</div>
          <div className="text-right">Trạng thái</div>
          <div className="text-right">Bỏ lỡ</div>
        </div>

        {filteredRows.length === 0 ? (
          <p className="py-6 text-center text-sm text-text-muted">Không có SKU nào khớp.</p>
        ) : (
          filteredRows.map((q) => (
            <div key={q.sku_id} className={`${GRID_COLS} gap-1 border-b border-card-border py-2.5 text-sm sm:grid sm:items-center sm:gap-3`}>
              <div className="font-medium text-ink sm:truncate">{q.sku_name}</div>
              <div className="mt-1 flex items-center justify-between text-xs text-text-secondary sm:mt-0 sm:contents">
                <span className="text-ink sm:text-right sm:text-sm">
                  <span className="sm:hidden">Tồn: </span>
                  {q.total_quantity}
                </span>
                <span className="sm:text-right">
                  <StatusCell status={q.flag_status} />
                </span>
                <span
                  className={
                    q.flag_status === 'out'
                      ? 'font-medium text-status-out sm:text-right sm:text-xs'
                      : q.flag_status === 'low'
                        ? 'font-medium text-status-low sm:text-right sm:text-xs'
                        : 'text-text-muted sm:text-right sm:text-xs'
                  }
                >
                  {q.missed_value > 0 ? formatMissed(q.missed_value) : '—'}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
