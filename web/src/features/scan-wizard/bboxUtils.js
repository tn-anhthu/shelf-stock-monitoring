export function bboxToPercent(bbox, imageWidth, imageHeight) {
  if (!imageWidth || !imageHeight) {
    return { left: 0, top: 0, width: 0, height: 0 };
  }
  const [x1, y1, x2, y2] = bbox;
  return {
    left: (x1 / imageWidth) * 100,
    top: (y1 / imageHeight) * 100,
    width: ((x2 - x1) / imageWidth) * 100,
    height: ((y2 - y1) / imageHeight) * 100,
  };
}

export function getBoxStyle(box, quantities) {
  if (box.type === 'gap') {
    if (box.needs_review) {
      return { variant: 'needs_review', reason: 'gap_uncertain' };
    }
    return { variant: 'gap' };
  }
  if (box.excluded_from_count && box.needs_review) {
    return { variant: 'needs_review', reason: 'duplicate' };
  }
  if (box.excluded_from_count) {
    return { variant: 'hidden' };
  }
  if (box.is_unknown) {
    return { variant: 'needs_review', reason: 'unknown' };
  }
  const match = quantities.find((q) => q.sku_id === box.sku_id);
  return { variant: 'product', flagStatus: match?.flag_status ?? null };
}

export function getPopupAnchor(pos) {
  return {
    horizontal: pos.left + pos.width > 70 ? 'right' : 'left',
    vertical: pos.top < 12 ? 'below' : 'above',
  };
}

export function getBoxLabel(box, quantities) {
  if (box.type === 'product' && box.sku_id && !box.is_unknown) {
    if (box.excluded_from_count && box.needs_review) {
      return { title: 'Nghi trùng với sản phẩm khác — cần kiểm tra', sku_id: box.sku_id, stt: null };
    }
    const rowIndex = quantities.findIndex((q) => q.sku_id === box.sku_id);
    return {
      title: rowIndex === -1 ? box.sku_id : quantities[rowIndex].sku_name,
      sku_id: box.sku_id,
      stt: rowIndex === -1 ? null : rowIndex + 1,
    };
  }
  if (box.type === 'gap') {
    return { title: box.needs_review ? 'Vùng nghi ngờ trống — cần kiểm tra' : 'Kệ trống (gap)', sku_id: null, stt: null };
  }
  return { title: 'Không xác định được sản phẩm', sku_id: null, stt: null };
}
