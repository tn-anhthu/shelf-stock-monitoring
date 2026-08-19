import { describe, expect, test } from 'vitest';
import { buildEmptyRow, computeTotalValue, isDuplicateSku } from './quantities.js';

describe('computeTotalValue', () => {
  test('sums facing_count * depth * unit_price across rows', () => {
    const quantities = [
      { sku_id: 'a', facing_count: 2, depth: 1, unit_price: 30000 },
      { sku_id: 'b', facing_count: 1, depth: 1, unit_price: 41000 },
    ];
    expect(computeTotalValue(quantities)).toBe(60000 + 41000);
  });

  test('defaults depth to 1 when missing', () => {
    const quantities = [{ sku_id: 'a', facing_count: 3, unit_price: 1000 }];
    expect(computeTotalValue(quantities)).toBe(3000);
  });

  test('returns 0 for an empty list', () => {
    expect(computeTotalValue([])).toBe(0);
  });
});

describe('buildEmptyRow', () => {
  test('returns a blank row with no sku_id, not a default catalog pick', () => {
    expect(buildEmptyRow()).toEqual({
      sku_id: null,
      sku_name: null,
      facing_count: 0,
      depth: 1,
      total_quantity: 0,
      shelf_full_qty: null,
      unit_price: null,
      subtotal: 0,
      flag_status: null,
    });
  });
});

describe('isDuplicateSku', () => {
  test('returns true when the sku_id is already present', () => {
    const quantities = [{ sku_id: 'choco_pie_org' }];
    expect(isDuplicateSku(quantities, 'choco_pie_org')).toBe(true);
  });

  test('returns false when the sku_id is not present', () => {
    const quantities = [{ sku_id: 'choco_pie_org' }];
    expect(isDuplicateSku(quantities, 'karo_org')).toBe(false);
  });

  test('returns false for an empty list', () => {
    expect(isDuplicateSku([], 'choco_pie_org')).toBe(false);
  });
});
