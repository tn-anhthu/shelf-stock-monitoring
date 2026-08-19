import BboxOverlay from '../scan-wizard/BboxOverlay.jsx';

export default function GapImageModal({ item, imageUrl, imageWidth, imageHeight, onClose }) {
  const gapBox = {
    box_id: item.gap_box_id,
    bbox: item.bbox,
    type: 'gap',
    sku_id: null,
    is_unknown: false,
    excluded_from_count: false,
    needs_review: false,
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4" onClick={onClose}>
      <div className="w-full max-w-2xl border border-card-border bg-page p-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="font-heading text-sm font-bold text-ink">Vị trí trên kệ</h2>
          <button type="button" onClick={onClose} className="text-text-secondary hover:text-ink" aria-label="Đóng">
            ✕
          </button>
        </div>
        <div className="mt-3">
          <BboxOverlay
            imageUrl={imageUrl}
            imageWidth={imageWidth}
            imageHeight={imageHeight}
            boxes={[gapBox]}
            quantities={[]}
            hoveredSkuId={null}
            onHoverSku={() => {}}
            captionOverride="Ảnh kệ hàng · viền đỏ đánh dấu vị trí gap"
          />
        </div>
      </div>
    </div>
  );
}
