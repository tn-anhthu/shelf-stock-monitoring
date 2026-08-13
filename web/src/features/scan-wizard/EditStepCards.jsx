import { IconClose } from '../../shared/ui/icons.jsx';

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

export default function EditStepCards({ quantities, onQuantityChange, onRemoveRow, hoveredSkuId, onRowHover }) {
  return (
    <div className="border-t border-ink">
      {quantities.map((q, index) => {
        const isHovered = hoveredSkuId === q.sku_id;
        return (
          <div
            key={`${q.sku_id}-${index}`}
            onMouseEnter={() => onRowHover(q.sku_id)}
            onMouseLeave={() => onRowHover(null)}
            className={`border-b border-card-border py-3 ${isHovered ? 'bg-page' : ''}`}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-heading text-sm font-medium text-ink">{q.sku_name}</p>
                <p className="text-xs text-text-secondary">{q.sku_id}</p>
              </div>
              <StatusText status={q.flag_status} />
            </div>
            <div className="mt-3 flex items-center gap-2">
              <button
                type="button"
                onClick={() => onQuantityChange(index, String(Math.max(0, q.facing_count - 1)))}
                className="h-7 w-7 border border-card-border text-ink"
              >
                −
              </button>
              <span className="min-w-[1.5rem] text-center font-heading text-sm font-medium text-ink">
                {q.facing_count}
              </span>
              <button
                type="button"
                onClick={() => onQuantityChange(index, String(q.facing_count + 1))}
                className="h-7 w-7 border border-card-border text-ink"
              >
                +
              </button>
              <button
                type="button"
                onClick={() => onRemoveRow(index)}
                className="ml-auto text-status-out"
                aria-label="Xóa dòng"
              >
                <IconClose />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
