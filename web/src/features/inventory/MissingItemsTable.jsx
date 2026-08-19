import { useState } from 'react';
import Button from '../../shared/ui/Button.jsx';
import { confirmScan } from '../scan-wizard/api.js';
import { computeTotalValue, isDuplicateSku } from '../scan-wizard/quantities.js';
import { buildConfirmationRow, isGapResolved } from './missingItems.js';

const UNRESOLVED_VALUE = '__unresolved__';

export default function MissingItemsTable({ missingItems, quantities, catalog, scanId, category, container, confirmedAt, onConfirmed }) {
  const [selections, setSelections] = useState({});
  const [dismissed, setDismissed] = useState(() => new Set());
  const [savingId, setSavingId] = useState(null);
  const [saveError, setSaveError] = useState(null);

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
        Sản phẩm nghi thiếu (gap chưa xác định SKU)
      </h2>
      {confirmedAt && (
        <p className="mt-1 text-xs text-text-secondary">
          Dựa trên lần quét gần nhất — {new Date(confirmedAt).toLocaleString('vi-VN')}
        </p>
      )}
      <table className="mt-3 w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-ink text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
            <th className="py-2 pr-2">Sản phẩm lân cận</th>
            <th className="pr-2">Gợi ý SKU</th>
            <th className="pr-2">Chọn xác nhận</th>
            <th className="pr-2">Trạng thái</th>
          </tr>
        </thead>
        <tbody>
          {missingItems.map((item) => {
            const resolved = isGapResolved(item.gap_box_id, quantities);
            const status = resolved ? 'confirmed' : dismissed.has(item.gap_box_id) ? 'unresolved' : 'needs_review';
            return (
              <tr key={item.gap_box_id} className="border-b border-card-border align-top">
                <td className="py-2.5 pr-2 text-text-secondary">
                  {item.nearby_skus.length > 0 ? item.nearby_skus.map((s) => s.sku_name).join(', ') : '—'}
                </td>
                <td className="pr-2 text-text-secondary">
                  {item.candidates.length > 0
                    ? item.candidates.map((c) => c.sku_name).join(', ')
                    : 'Không xác định được gợi ý — cần kiểm tra thủ công'}
                </td>
                <td className="pr-2">
                  {status === 'needs_review' ? (
                    <div className="flex items-center gap-2">
                      <select
                        value={selections[item.gap_box_id] ?? ''}
                        onChange={(e) => setSelections((prev) => ({ ...prev, [item.gap_box_id]: e.target.value }))}
                        className="border-0 border-b border-ink bg-transparent px-0 py-1 focus:outline-none"
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
                        onClick={() => handleConfirm(item)}
                        disabled={!selections[item.gap_box_id] || savingId === item.gap_box_id}
                      >
                        {savingId === item.gap_box_id ? 'Đang lưu…' : 'Xác nhận'}
                      </Button>
                    </div>
                  ) : (
                    <span className="text-text-muted">—</span>
                  )}
                </td>
                <td className="pr-2">
                  {status === 'confirmed' && <span className="font-bold text-status-ok">Đã xác nhận</span>}
                  {status === 'unresolved' && <span className="text-text-muted">Không xác định</span>}
                  {status === 'needs_review' && <span className="font-medium text-status-out">Cần kiểm tra</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {saveError && <p className="mt-2 text-status-out">Lưu thất bại: {saveError}</p>}
    </div>
  );
}
