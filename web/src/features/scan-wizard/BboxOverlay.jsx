import { useState } from 'react';
import { bboxToPercent, getBoxStyle, getBoxLabel } from './bboxUtils.js';

const PRODUCT_COLOR = '#3B82F6';

const NEUTRAL_VARIANT_STYLE = {
  gap: { border: '1.5px solid #EF4444', background: 'transparent' },
  needs_review: { border: '1.5px dashed #FACC15', background: 'rgba(250, 204, 21, 0.15)' },
};

const BOX_FILL_OPACITY = 0.15;

export function hexToRgba(hex, alpha) {
  const normalized = hex.replace('#', '');
  const r = parseInt(normalized.slice(0, 2), 16);
  const g = parseInt(normalized.slice(2, 4), 16);
  const b = parseInt(normalized.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export default function BboxOverlay({ imageUrl, imageWidth, imageHeight, boxes, quantities, hoveredSkuId, onHoverSku }) {
  const [selectedBoxId, setSelectedBoxId] = useState(null);

  if (!imageUrl || !imageWidth || !imageHeight) {
    return (
      <div className="flex aspect-video items-center justify-center rounded-xl border border-dashed border-card-border text-sm text-text-muted">
        Chưa có ảnh
      </div>
    );
  }

  return (
    <div>
      <p className="mb-2 text-xs text-text-muted">Ảnh kệ hàng · di chuột vào dòng bảng để xem vị trí</p>
      <div
        className="relative w-full overflow-hidden rounded-xl border border-card-border"
        style={{ aspectRatio: `${imageWidth} / ${imageHeight}` }}
      >
        <img src={imageUrl} alt="Ảnh kệ hàng đã phân tích" className="absolute inset-0 h-full w-full object-cover" />
        {boxes.map((box) => {
          const style = getBoxStyle(box, quantities);
          if (style.variant === 'hidden') {
            return null;
          }
          const pos = bboxToPercent(box.bbox, imageWidth, imageHeight);
          const isHovered = style.variant === 'product' && !!hoveredSkuId && box.sku_id === hoveredSkuId;

          let border;
          let background;
          if (style.variant === 'product') {
            border = `${isHovered ? 2.5 : 1.5}px solid ${PRODUCT_COLOR}`;
            background = hexToRgba(PRODUCT_COLOR, BOX_FILL_OPACITY);
          } else {
            border = NEUTRAL_VARIANT_STYLE[style.variant].border;
            background = NEUTRAL_VARIANT_STYLE[style.variant].background;
          }

          const isSelected = selectedBoxId === box.box_id;
          const label = isSelected ? getBoxLabel(box, quantities) : null;

          return (
            <div key={box.box_id}>
              <div
                onMouseEnter={() => style.variant === 'product' && box.sku_id && onHoverSku(box.sku_id)}
                onMouseLeave={() => onHoverSku(null)}
                onClick={() => setSelectedBoxId(isSelected ? null : box.box_id)}
                className="absolute cursor-pointer rounded"
                style={{
                  left: `${pos.left}%`,
                  top: `${pos.top}%`,
                  width: `${pos.width}%`,
                  height: `${pos.height}%`,
                  border,
                  backgroundColor: background,
                  boxShadow: isHovered ? '0 0 0 2px #fff' : 'none',
                }}
              />
              {label && (
                <div
                  className="absolute z-10 rounded border border-ink bg-page px-2 py-1 text-xs text-ink shadow-md"
                  style={{ left: `${pos.left}%`, top: `calc(${pos.top}% - 1.75rem)` }}
                >
                  {label.stt !== null && <span className="mr-1 font-bold">#{label.stt}</span>}
                  {label.title}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
