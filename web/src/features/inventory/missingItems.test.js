import { describe, expect, test } from 'vitest';
import { buildConfirmationRow, isGapResolved } from './missingItems.js';

describe('buildConfirmationRow', () => {
  test('builds a zero-quantity row tagged with source=oos_confirmation and the originating gap', () => {
    const catalogEntry = { sku_id: 'coca_zero_can_320', name: 'Coca-Cola Zero lon 320ml', price: 10000, shelf_full_qty: 20 };
    expect(buildConfirmationRow('g1', 'coca_zero_can_320', catalogEntry)).toEqual({
      sku_id: 'coca_zero_can_320',
      sku_name: 'Coca-Cola Zero lon 320ml',
      facing_count: 0,
      depth: 1,
      total_quantity: 0,
      shelf_full_qty: 20,
      unit_price: 10000,
      subtotal: 0,
      flag_status: 'out',
      source: 'oos_confirmation',
      source_gap_box_id: 'g1',
    });
  });
});

describe('isGapResolved', () => {
  test('true when a quantities row was confirmed for this gap', () => {
    expect(isGapResolved('g1', [{ sku_id: 'a', source_gap_box_id: 'g1' }])).toBe(true);
  });

  test('false when no row references this gap', () => {
    expect(isGapResolved('g1', [{ sku_id: 'a' }])).toBe(false);
  });
});
