import { useState } from 'react';
import Button from '../../shared/ui/Button.jsx';
import { confirmScan } from '../scan-wizard/api.js';
import { computeTotalValue, isDuplicateSku } from '../scan-wizard/quantities.js';
import { buildConfirmationRow, isGapResolved } from './missingItems.js';
import GapImageModal from './GapImageModal.jsx';

const UNRESOLVED_VALUE = '__unresolved__';

const GRID_COLS = 'grid-cols-[56px_1.4fr_1.4fr_260px_120px]';

export default function MissingItemsTable({
  missingItems,
  quantities,
  catalog,
  scanId,
  category,
  container,
  confirmedAt,
  imageUrl,
  imageWidth,
  imageHeight,
  onConfirmed,
}) {
  const [selections, setSelections] = useState({});
  const [dismissed, setDismissed] = useState(() => new Set());
  const [savingId, setSavingId] = useState(null);
  const [saveError, setSaveError] = useState(null);
  const [viewingItem, setViewingItem] = useState(null);

  if (!missingItems || missingItems.length === 0) return null;

  async function handleConfirm(item) {
    const choice = selections[item.gap_box_id];
    if (!choice) return;

    if (choice === UNRESOLVED_VALUE) {
      setDismissed((prev) => new Set(prev).add(item.gap_box_id));
      return;
    }

    const catalogEntry = catalog.find((c) => c.sku_id === choice);
    if (!catalogEntry) return;

    if (isDuplicateSku(quantities, choice)) {
      setSaveError('SKU này đã có trong danh sách — vui lòng chọn SKU khác hoặc bỏ qua.');
      return;
    }

    const nextQuantities = [...quantities, buildConfirmationRow(item.gap_box_id, choice, catalogEntry)];
    setSavingId(item.gap_box_id);
    setSaveError(null);
    try {
      await confirmScan({
        scan_id: scanId,
        category,
        container,
        quantities: nextQuantities,
        total_value: computeTotalValue(nextQuantities),
      });
      onConfirmed();
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className="mt-6 border-t border-ink pt-4">
      <h2 className="font-heading text-sm font-bold uppercase tracking-wide text-text-secondary">
        Missing Items
      </h2>
      {confirmedAt && (
        <p className="mt-1 text-xs text-text-secondary">
          Based on latest scan — {new Date(confirmedAt).toLocaleString('vi-VN')}
        </p>
      )}
      <div className="mt-3 border-t border-ink">
        <div
          className={`sticky top-0 z-10 grid ${GRID_COLS} gap-4 border-b border-ink bg-page py-2.5 text-[10px] font-bold uppercase tracking-wide text-text-secondary`}
        >
          <div>Preview</div>
          <div>Neighbor Products</div>
          <div>Suggest</div>
          <div>Select SKU</div>
          <div className="text-right">Status</div>
        </div>

        {missingItems.map((item) => {
          const resolved = isGapResolved(item.gap_box_id, quantities);
          const status = resolved ? 'confirmed' : dismissed.has(item.gap_box_id) ? 'unresolved' : 'needs_review';
          return (
            <div
              key={item.gap_box_id}
              className={`grid ${GRID_COLS} gap-4 items-start border-b border-card-border py-2.5 text-sm`}
            >
              <div>
                {imageUrl ? (
                  <button
                    type="button"
                    onClick={() => setViewingItem(item)}
                    className="text-xs text-text-secondary underline decoration-1 underline-offset-2 hover:text-ink"
                  >
                    Xem
                  </button>
                ) : (
                  <span className="text-text-muted">—</span>
                )}
              </div>
              <div className="text-text-secondary">
                {item.nearby_skus.length > 0 ? (
                  <div className="flex flex-wrap gap-1">
                    {item.nearby_skus.map((s) => (
                      <span
                        key={s.sku_id}
                        className="rounded-sm border border-card-border bg-page px-1.5 py-0.5 text-xs leading-relaxed text-text-secondary"
                      >
                        {s.sku_name}
                      </span>
                    ))}
                  </div>
                ) : (
                  '—'
                )}
              </div>
              <div className="text-text-secondary">
                {item.candidates.length > 0 ? (
                  <div className="flex flex-wrap gap-1">
                    {item.candidates.map((c) => (
                      <span
                        key={c.sku_id}
                        className="rounded-sm border border-card-border bg-page px-1.5 py-0.5 text-xs leading-relaxed text-text-secondary"
                      >
                        {c.sku_name}
                      </span>
                    ))}
                  </div>
                ) : (
                  'Không xác định được gợi ý — cần kiểm tra thủ công'
                )}
              </div>
              <div>
                {status === 'needs_review' ? (
                  <div className="flex items-center gap-2">
                    <select
                      value={selections[item.gap_box_id] ?? ''}
                      onChange={(e) => setSelections((prev) => ({ ...prev, [item.gap_box_id]: e.target.value }))}
                      className="flex-1 min-w-0 truncate border-0 border-b border-ink bg-transparent px-0 py-1 focus:outline-none"
                    >
                      <option value="">— Chọn —</option>
                      {item.candidates.filter((c) => !isDuplicateSku(quantities, c.sku_id)).map((c) => (
                        <option key={c.sku_id} value={c.sku_id}>{c.sku_name}</option>
                      ))}
                      <optgroup label="Khác (toàn bộ danh mục)">
                        {catalog.filter((c) => !isDuplicateSku(quantities, c.sku_id)).map((c) => (
                          <option key={c.sku_id} value={c.sku_id}>{c.name}</option>
                        ))}
                      </optgroup>
                      <option value={UNRESOLVED_VALUE}>Không xác định</option>
                    </select>
                    <Button
                      type="button"
                      variant="outline"
                      className="shrink-0"
                      onClick={() => handleConfirm(item)}
                      disabled={!selections[item.gap_box_id] || savingId === item.gap_box_id}
                    >
                      {savingId === item.gap_box_id ? 'Đang lưu…' : 'Xác nhận'}
                    </Button>
                  </div>
                ) : (
                  <span className="text-text-muted">—</span>
                )}
              </div>
              <div className="text-right">
                {status === 'confirmed' && <span className="font-bold text-status-ok">Đã xác nhận</span>}
                {status === 'unresolved' && <span className="text-text-muted">Không xác định</span>}
                {status === 'needs_review' && <span className="font-medium text-status-out">Cần kiểm tra</span>}
              </div>
            </div>
          );
        })}
      </div>
      {saveError && <p className="mt-2 text-status-out">Lưu thất bại: {saveError}</p>}
      {viewingItem && (
        <GapImageModal
          item={viewingItem}
          imageUrl={imageUrl}
          imageWidth={imageWidth}
          imageHeight={imageHeight}
          onClose={() => setViewingItem(null)}
        />
      )}
    </div>
  );
}
