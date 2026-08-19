import { describe, expect, test } from 'vitest';
import { bboxToPercent, getBoxStyle, getBoxLabel, getPopupAnchor } from './bboxUtils.js';

describe('bboxToPercent', () => {
  test('converts a pixel bbox to percentages of the image size', () => {
    expect(bboxToPercent([40, 40, 220, 420], 1000, 500)).toEqual({
      left: 4,
      top: 8,
      width: 18,
      height: 76,
    });
  });

  test('handles a box spanning the full image', () => {
    expect(bboxToPercent([0, 0, 100, 100], 100, 100)).toEqual({
      left: 0,
      top: 0,
      width: 100,
      height: 100,
    });
  });

  test('returns all zeros when imageWidth or imageHeight is falsy', () => {
    expect(bboxToPercent([10, 10, 50, 50], 0, 500)).toEqual({ left: 0, top: 0, width: 0, height: 0 });
    expect(bboxToPercent([10, 10, 50, 50], 500, 0)).toEqual({ left: 0, top: 0, width: 0, height: 0 });
  });
});

describe('getBoxStyle', () => {
  const quantities = [
    { sku_id: 'choco_pie_org', flag_status: 'low' },
    { sku_id: 'karo_org', flag_status: 'ok' },
  ];

  test('maps a product box to its matched quantities row flag_status', () => {
    expect(getBoxStyle({ type: 'product', sku_id: 'choco_pie_org', is_unknown: false }, quantities)).toEqual({
      variant: 'product',
      flagStatus: 'low',
    });
  });

  test('returns flagStatus null when the sku_id has no matching quantities row', () => {
    expect(getBoxStyle({ type: 'product', sku_id: 'missing_sku', is_unknown: false }, quantities)).toEqual({
      variant: 'product',
      flagStatus: null,
    });
  });

  test('marks is_unknown boxes as the needs_review variant regardless of sku_id', () => {
    expect(getBoxStyle({ type: 'product', sku_id: null, is_unknown: true }, quantities)).toEqual({
      variant: 'needs_review',
      reason: 'unknown',
    });
  });

  test('marks type gap boxes without needs_review as the gap variant', () => {
    expect(getBoxStyle({ type: 'gap', sku_id: null, is_unknown: false, needs_review: false }, quantities)).toEqual({
      variant: 'gap',
    });
  });

  test('marks type gap boxes with needs_review as the needs_review variant', () => {
    expect(getBoxStyle({ type: 'gap', sku_id: null, is_unknown: false, needs_review: true }, quantities)).toEqual({
      variant: 'needs_review',
      reason: 'gap_uncertain',
    });
  });

  test('marks excluded_from_count + needs_review boxes as the needs_review variant even when also is_unknown', () => {
    expect(
      getBoxStyle(
        { type: 'product', sku_id: 'choco_pie_org', is_unknown: true, excluded_from_count: true, needs_review: true },
        quantities
      )
    ).toEqual({ variant: 'needs_review', reason: 'duplicate' });
  });

  test('marks excluded_from_count boxes without needs_review as the hidden variant', () => {
    expect(
      getBoxStyle(
        { type: 'product', sku_id: 'choco_pie_org', is_unknown: false, excluded_from_count: true, needs_review: false },
        quantities
      )
    ).toEqual({ variant: 'hidden' });
  });

  test('hidden variant takes priority over is_unknown', () => {
    expect(
      getBoxStyle(
        { type: 'product', sku_id: null, is_unknown: true, excluded_from_count: true, needs_review: false },
        quantities
      )
    ).toEqual({ variant: 'hidden' });
  });
});

describe('getBoxLabel', () => {
  const quantities = [
    { sku_id: 'choco_pie_org', sku_name: 'Bánh chocopie Orion hộp 217.8g (6 cái)', flag_status: 'low' },
    { sku_id: 'karo_org', sku_name: 'Bánh trứng tươi chà bông Karo Richy túi 156g', flag_status: 'ok' },
  ];

  test('resolves a matched product box to its table row name and STT (1-indexed row position)', () => {
    expect(getBoxLabel({ type: 'product', sku_id: 'karo_org', is_unknown: false }, quantities)).toEqual({
      title: 'Bánh trứng tươi chà bông Karo Richy túi 156g',
      sku_id: 'karo_org',
      stt: 2,
    });
  });

  test('a confirmed gap has no STT and a plain label', () => {
    expect(getBoxLabel({ type: 'gap', sku_id: null, needs_review: false }, quantities)).toEqual({
      title: 'Kệ trống (gap)',
      sku_id: null,
      stt: null,
    });
  });

  test('an uncertain gap says so in the label', () => {
    expect(getBoxLabel({ type: 'gap', sku_id: null, needs_review: true }, quantities)).toEqual({
      title: 'Vùng nghi ngờ trống — cần kiểm tra',
      sku_id: null,
      stt: null,
    });
  });

  test('an unknown box has no STT (not in the quantities table)', () => {
    expect(getBoxLabel({ type: 'product', sku_id: null, is_unknown: true }, quantities)).toEqual({
      title: 'Không xác định được sản phẩm',
      sku_id: null,
      stt: null,
    });
  });

  test('an excluded+needs_review (dedup) box says so, keeps its sku_id, has no STT', () => {
    expect(
      getBoxLabel({ type: 'product', sku_id: 'karo_org', is_unknown: false, excluded_from_count: true, needs_review: true }, quantities),
    ).toEqual({ title: 'Nghi trùng với sản phẩm khác — cần kiểm tra', sku_id: 'karo_org', stt: null });
  });
});

describe('getPopupAnchor', () => {
  test('defaults to left/above for a box in the middle of the image', () => {
    expect(getPopupAnchor({ left: 40, top: 40, width: 10, height: 10 })).toEqual({
      horizontal: 'left',
      vertical: 'above',
    });
  });

  test('anchors right when the box is near the right edge (left + width > 70)', () => {
    expect(getPopupAnchor({ left: 65, top: 40, width: 10, height: 10 })).toEqual({
      horizontal: 'right',
      vertical: 'above',
    });
  });

  test('flips below when the box is near the top edge (top < 12)', () => {
    expect(getPopupAnchor({ left: 40, top: 5, width: 10, height: 10 })).toEqual({
      horizontal: 'left',
      vertical: 'below',
    });
  });

  test('anchors right AND flips below when the box is near the top-right corner', () => {
    expect(getPopupAnchor({ left: 65, top: 5, width: 10, height: 10 })).toEqual({
      horizontal: 'right',
      vertical: 'below',
    });
  });

  test('left + width exactly at the 70 threshold stays left (not strictly greater)', () => {
    expect(getPopupAnchor({ left: 60, top: 40, width: 10, height: 10 })).toEqual({
      horizontal: 'left',
      vertical: 'above',
    });
  });

  test('top exactly at the 12 threshold stays above (not strictly less)', () => {
    expect(getPopupAnchor({ left: 40, top: 12, width: 10, height: 10 })).toEqual({
      horizontal: 'left',
      vertical: 'above',
    });
  });
});
