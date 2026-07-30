import { useState } from 'react';
import { computeTotalValue, isDuplicateSku } from './quantities.js';
import EditStepTable from './EditStepTable.jsx';
import EditStepCards from './EditStepCards.jsx';
import BboxOverlay from './BboxOverlay.jsx';
import Button from '../../shared/ui/Button.jsx';

function isValidQuantity(value) {
  return Number.isInteger(value) && value >= 0;
}

export default function EditStep({
  quantities,
  setQuantities,
  catalog,
  boxes,
  imageUrl,
  imageWidth,
  imageHeight,
  onNext,
}) {
  const [newSkuId, setNewSkuId] = useState('');
  const [hoveredSkuId, setHoveredSkuId] = useState(null);

  const totalValue = computeTotalValue(quantities);
  const availableToAdd = catalog.filter((item) => !isDuplicateSku(quantities, item.sku_id));

  function updateRow(index, patch) {
    setQuantities((prev) => prev.map((q, i) => (i === index ? { ...q, ...patch } : q)));
  }

  function handleQuantityChange(index, rawValue) {
    const value = Number(rawValue);
    if (!isValidQuantity(value)) return;
    const depth = quantities[index].depth ?? 1;
    updateRow(index, {
      facing_count: value,
      total_quantity: value * depth,
      subtotal: value * depth * quantities[index].unit_price,
    });
  }

  function handleSkuChange(index, skuId) {
    const catalogEntry = catalog.find((item) => item.sku_id === skuId);
    if (!catalogEntry) return;
    const otherRows = quantities.filter((_, i) => i !== index);
    if (isDuplicateSku(otherRows, skuId)) return;
    const { facing_count } = quantities[index];
    const depth = quantities[index].depth ?? 1;
    updateRow(index, {
      sku_id: catalogEntry.sku_id,
      sku_name: catalogEntry.name,
      unit_price: catalogEntry.price,
      shelf_full_qty: catalogEntry.shelf_full_qty,
      flag_status: null,
      total_quantity: facing_count * depth,
      subtotal: facing_count * depth * catalogEntry.price,
    });
  }

  function handleRemoveRow(index) {
    setQuantities((prev) => prev.filter((_, i) => i !== index));
  }

  function handleAddRow() {
    if (!newSkuId || isDuplicateSku(quantities, newSkuId)) return;
    const catalogEntry = catalog.find((item) => item.sku_id === newSkuId);
    if (!catalogEntry) return;
    setQuantities((prev) => [
      ...prev,
      {
        sku_id: catalogEntry.sku_id,
        sku_name: catalogEntry.name,
        facing_count: 0,
        depth: 1,
        total_quantity: 0,
        shelf_full_qty: catalogEntry.shelf_full_qty,
        unit_price: catalogEntry.price,
        subtotal: 0,
        flag_status: null,
      },
    ]);
    setNewSkuId('');
  }

  return (
    <div className="space-y-4 pb-32 md:pb-4">
      <h2 className="font-heading text-lg font-semibold text-ink">3. Kiểm tra & sửa số lượng</h2>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <BboxOverlay
          imageUrl={imageUrl}
          imageWidth={imageWidth}
          imageHeight={imageHeight}
          boxes={boxes}
          quantities={quantities}
          hoveredSkuId={hoveredSkuId}
          onHoverSku={setHoveredSkuId}
        />
        <div>
          <EditStepTable
            quantities={quantities}
            catalog={catalog}
            onQuantityChange={handleQuantityChange}
            onSkuChange={handleSkuChange}
            onRemoveRow={handleRemoveRow}
            hoveredSkuId={hoveredSkuId}
            onRowHover={setHoveredSkuId}
          />
          <EditStepCards
            quantities={quantities}
            onQuantityChange={handleQuantityChange}
            onRemoveRow={handleRemoveRow}
            hoveredSkuId={hoveredSkuId}
            onRowHover={setHoveredSkuId}
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <select
          value={newSkuId}
          onChange={(e) => setNewSkuId(e.target.value)}
          className="rounded-lg border border-card-border px-2 py-1"
        >
          <option value="">-- chọn SKU để thêm --</option>
          {availableToAdd.map((item) => (
            <option key={item.sku_id} value={item.sku_id}>
              {item.name}
            </option>
          ))}
        </select>
        <Button type="button" variant="outline" onClick={handleAddRow} disabled={!newSkuId}>
          Thêm dòng
        </Button>
      </div>

      <div className="fixed inset-x-0 bottom-16 border-t border-card-border bg-white p-3 md:static md:border-0 md:bg-transparent md:p-0">
        <p className="font-heading text-lg font-semibold text-ink">Tổng giá trị: {totalValue.toLocaleString('vi-VN')} đ</p>
      </div>

      <details className="rounded-lg border border-card-border p-3">
        <summary className="cursor-pointer font-medium text-ink">Xem chi tiết kỹ thuật</summary>
        <table className="mt-2 w-full text-xs">
          <thead>
            <tr className="text-left">
              <th>box_id</th>
              <th>type</th>
              <th>sku_id</th>
              <th>confidence</th>
              <th>is_unknown</th>
            </tr>
          </thead>
          <tbody>
            {boxes.map((box) => (
              <tr key={box.box_id}>
                <td>{box.box_id}</td>
                <td>{box.type}</td>
                <td>{box.sku_id ?? '—'}</td>
                <td>{box.confidence.toFixed(2)}</td>
                <td>{box.is_unknown ? 'có' : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      <Button type="button" onClick={onNext} className="w-full md:w-auto">
        Tiếp tục
      </Button>
    </div>
  );
}
