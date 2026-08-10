import { useEffect, useRef, useState } from 'react';
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
  const [hoveredSkuId, setHoveredSkuId] = useState(null);
  const [leftWidth, setLeftWidth] = useState(50);
  const containerRef = useRef(null);
  const draggingRef = useRef(false);

  useEffect(() => {
    function handleMouseMove(e) {
      if (!draggingRef.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const percent = ((e.clientX - rect.left) / rect.width) * 100;
      setLeftWidth(Math.min(70, Math.max(25, percent)));
    }
    function handleMouseUp() {
      draggingRef.current = false;
    }
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  const totalValue = computeTotalValue(quantities);
  const availableToAdd = catalog.filter((item) => !isDuplicateSku(quantities, item.sku_id));
  const excludedCount = boxes.filter((box) => box.excluded_from_count).length;

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
    const catalogEntry = availableToAdd[0];
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
  }

  return (
    <div className="space-y-4 pb-32 md:pb-4">
      <h2 className="font-heading text-lg font-semibold text-ink">3. Kiểm tra & sửa số lượng</h2>

      {excludedCount > 0 && (
        <p className="rounded-lg bg-status-out-bg px-3 py-2 text-sm text-status-out-text">
          ⚠️ {excludedCount} vùng cần kiểm tra kỹ (có thể trùng sản phẩm) — xem viền tím trên ảnh bên trái.
        </p>
      )}

      <div ref={containerRef} className="hidden md:flex">
        <div style={{ width: `${leftWidth}%` }} className="pr-3">
          <BboxOverlay
            imageUrl={imageUrl}
            imageWidth={imageWidth}
            imageHeight={imageHeight}
            boxes={boxes}
            quantities={quantities}
            hoveredSkuId={hoveredSkuId}
            onHoverSku={setHoveredSkuId}
          />
        </div>
        <div
          onMouseDown={() => {
            draggingRef.current = true;
          }}
          className="w-1 shrink-0 cursor-col-resize rounded bg-card-border hover:bg-ink"
        />
        <div style={{ width: `${100 - leftWidth}%` }} className="min-w-0 pl-3">
          <EditStepTable
            quantities={quantities}
            catalog={catalog}
            onQuantityChange={handleQuantityChange}
            onSkuChange={handleSkuChange}
            onRemoveRow={handleRemoveRow}
            hoveredSkuId={hoveredSkuId}
            onRowHover={setHoveredSkuId}
          />
          <Button
            type="button"
            variant="outline"
            onClick={handleAddRow}
            disabled={availableToAdd.length === 0}
            className="mt-3"
          >
            + Thêm dòng
          </Button>
        </div>
      </div>

      <div className="space-y-4 md:hidden">
        <BboxOverlay
          imageUrl={imageUrl}
          imageWidth={imageWidth}
          imageHeight={imageHeight}
          boxes={boxes}
          quantities={quantities}
          hoveredSkuId={hoveredSkuId}
          onHoverSku={setHoveredSkuId}
        />
        <EditStepCards
          quantities={quantities}
          onQuantityChange={handleQuantityChange}
          onRemoveRow={handleRemoveRow}
          hoveredSkuId={hoveredSkuId}
          onRowHover={setHoveredSkuId}
        />
        <Button type="button" variant="outline" onClick={handleAddRow} disabled={availableToAdd.length === 0}>
          + Thêm dòng
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
              <th>excluded_from_count</th>
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
                <td>{box.excluded_from_count ? 'có' : ''}</td>
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
