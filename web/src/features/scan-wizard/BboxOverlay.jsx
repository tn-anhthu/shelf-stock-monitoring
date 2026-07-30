import { bboxToPercent, getBoxStyle } from './bboxUtils.js';
import { getStatusStyle } from '../../shared/ui/statusStyles.js';

const NEUTRAL_VARIANT_STYLE = {
  unknown: { border: '2px dashed #94A3B8', background: 'rgba(148, 163, 184, 0.15)' },
  gap: { border: '2px dashed #E2E8F0', background: 'transparent' },
};

export default function BboxOverlay({ imageUrl, imageWidth, imageHeight, boxes, quantities, hoveredSkuId, onHoverSku }) {
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
          const pos = bboxToPercent(box.bbox, imageWidth, imageHeight);
          const style = getBoxStyle(box, quantities);
          const isHovered = style.variant === 'product' && !!hoveredSkuId && box.sku_id === hoveredSkuId;

          let border;
          let background;
          if (style.variant === 'product') {
            const statusStyle = getStatusStyle(style.flagStatus) ?? { bg: 'transparent', text: '#94A3B8' };
            border = `${isHovered ? 3 : 2}px solid ${statusStyle.text}`;
            background = statusStyle.bg;
          } else {
            border = NEUTRAL_VARIANT_STYLE[style.variant].border;
            background = NEUTRAL_VARIANT_STYLE[style.variant].background;
          }

          return (
            <div
              key={box.box_id}
              onMouseEnter={() => style.variant === 'product' && box.sku_id && onHoverSku(box.sku_id)}
              onMouseLeave={() => onHoverSku(null)}
              className="absolute rounded"
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
          );
        })}
      </div>
    </div>
  );
}
