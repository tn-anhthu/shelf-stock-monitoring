import { useState } from 'react';
import { computeTotalValue, isDuplicateSku } from './quantities.js';

const currency = (n) => n.toLocaleString('vi-VN') + ' đ';

const FLAG_STYLES = {
  ok: 'text-emerald-700',
  low: 'text-amber-700 font-semibold',
  out: 'text-red-700 font-semibold',
};

function isValidQuantity(value) {
  return Number.isInteger(value) && value >= 0;
}

export default function EditStep({ quantities, setQuantities, catalog, boxes, onNext }) {
  const [newSkuId, setNewSkuId] = useState('');

  const totalValue = computeTotalValue(quantities);
  const availableToAdd = catalog.filter((item) => !isDuplicateSku(quantities, item.sku_id));

  function updateRow(index, patch) {
    setQuantities((prev) => prev.map((q, i) => (i === index ? { ...q, ...patch } : q)));
  }

  function handleQuantityChange(index, rawValue) {
    const value = Number(rawValue);
    if (!isValidQuantity(value)) return;
    updateRow(index, {
      facing_count: value,
      total_quantity: value * (quantities[index].depth ?? 1),
    });
  }

  function handleSkuChange(index, skuId) {
    const catalogEntry = catalog.find((item) => item.sku_id === skuId);
    if (!catalogEntry) return;
    const otherRows = quantities.filter((_, i) => i !== index);
    if (isDuplicateSku(otherRows, skuId)) return;
    updateRow(index, {
      sku_id: catalogEntry.sku_id,
      sku_name: catalogEntry.name,
      unit_price: catalogEntry.price,
      shelf_full_qty: catalogEntry.shelf_full_qty,
      flag_status: null,
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
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">3. Kiểm tra & sửa số lượng</h2>

      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b text-left">
            <th className="py-2">Sản phẩm</th>
            <th>SKU</th>
            <th>Số lượng</th>
            <th>Đơn giá</th>
            <th>Thành tiền</th>
            <th>Trạng thái</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {quantities.map((q, index) => {
            const otherRows = quantities.filter((_, i) => i !== index);
            const skuOptions = catalog.filter(
              (item) => item.sku_id === q.sku_id || !isDuplicateSku(otherRows, item.sku_id),
            );
            return (
              <tr key={`${q.sku_id}-${index}`} className="border-b">
                <td className="py-2">{q.sku_name}</td>
                <td>
                  <select
                    value={q.sku_id}
                    onChange={(e) => handleSkuChange(index, e.target.value)}
                    className="rounded border px-2 py-1"
                  >
                    {skuOptions.map((item) => (
                      <option key={item.sku_id} value={item.sku_id}>
                        {item.sku_id}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={q.facing_count}
                    onChange={(e) => handleQuantityChange(index, e.target.value)}
                    className="w-20 rounded border px-2 py-1"
                  />
                </td>
                <td>{currency(q.unit_price)}</td>
                <td>{currency(q.facing_count * (q.depth ?? 1) * q.unit_price)}</td>
                <td>
                  {q.flag_status ? (
                    <span className={FLAG_STYLES[q.flag_status]}>{q.flag_status}</span>
                  ) : (
                    '—'
                  )}
                </td>
                <td>
                  <button type="button" onClick={() => handleRemoveRow(index)} className="text-red-600">
                    Xóa
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="flex items-center gap-2">
        <select
          value={newSkuId}
          onChange={(e) => setNewSkuId(e.target.value)}
          className="rounded border px-2 py-1"
        >
          <option value="">-- chọn SKU để thêm --</option>
          {availableToAdd.map((item) => (
            <option key={item.sku_id} value={item.sku_id}>
              {item.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={handleAddRow}
          disabled={!newSkuId}
          className="rounded border px-3 py-1 disabled:opacity-50"
        >
          Thêm dòng
        </button>
      </div>

      <p className="text-lg font-semibold">Tổng giá trị: {currency(totalValue)}</p>

      <details className="rounded border p-3">
        <summary className="cursor-pointer font-medium">Xem chi tiết kỹ thuật</summary>
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

      <button type="button" onClick={onNext} className="rounded bg-slate-900 px-4 py-2 text-white">
        Tiếp tục
      </button>
    </div>
  );
}
