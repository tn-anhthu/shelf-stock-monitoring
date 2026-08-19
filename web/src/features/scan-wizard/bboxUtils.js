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
