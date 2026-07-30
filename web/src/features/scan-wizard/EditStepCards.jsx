import StatusChip from '../../shared/ui/StatusChip.jsx';
import Card from '../../shared/ui/Card.jsx';

const currency = (n) => n.toLocaleString('vi-VN') + ' đ';

export default function EditStepCards({ quantities, onQuantityChange, onRemoveRow, hoveredSkuId, onRowHover }) {
  return (
    <div className="space-y-3 md:hidden">
      {quantities.map((q, index) => {
        const depth = q.depth ?? 1;
        const isHovered = hoveredSkuId === q.sku_id;
        return (
          <Card
            key={`${q.sku_id}-${index}`}
            onMouseEnter={() => onRowHover(q.sku_id)}
            onMouseLeave={() => onRowHover(null)}
            className={isHovered ? 'border-ink bg-page' : ''}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-heading text-sm font-medium text-ink">{q.sku_name}</p>
                <p className="text-xs text-text-muted">
                  {q.sku_id} · {currency(q.unit_price)}
                </p>
              </div>
              <StatusChip status={q.flag_status} />
            </div>
            <div className="mt-3 flex items-center gap-2">
              <button
                type="button"
                onClick={() => onQuantityChange(index, String(Math.max(0, q.facing_count - 1)))}
                className="h-7 w-7 rounded-md border border-card-border bg-white"
              >
                −
              </button>
              <span className="min-w-[1.5rem] text-center font-heading text-sm font-medium text-ink">
                {q.facing_count}
              </span>
              <button
                type="button"
                onClick={() => onQuantityChange(index, String(q.facing_count + 1))}
                className="h-7 w-7 rounded-md border border-card-border bg-white"
              >
                +
              </button>
              <span className="ml-auto text-sm text-text-secondary">
                {currency(q.facing_count * depth * q.unit_price)}
              </span>
              <button type="button" onClick={() => onRemoveRow(index)} className="text-status-out-text" aria-label="Xóa dòng">
                ✕
              </button>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
