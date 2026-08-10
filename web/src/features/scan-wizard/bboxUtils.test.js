import { describe, expect, test } from 'vitest';
import { bboxToPercent, getBoxStyle } from './bboxUtils.js';

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

  test('marks is_unknown boxes as the unknown variant regardless of sku_id', () => {
    expect(getBoxStyle({ type: 'product', sku_id: null, is_unknown: true }, quantities)).toEqual({
      variant: 'unknown',
    });
  });

  test('marks type gap boxes as the gap variant', () => {
    expect(getBoxStyle({ type: 'gap', sku_id: null, is_unknown: false }, quantities)).toEqual({
      variant: 'gap',
    });
  });

  test('marks excluded_from_count boxes as the excluded variant even when also is_unknown', () => {
    expect(
      getBoxStyle(
        { type: 'product', sku_id: 'choco_pie_org', is_unknown: true, excluded_from_count: true },
        quantities
      )
    ).toEqual({ variant: 'excluded' });
  });
});
