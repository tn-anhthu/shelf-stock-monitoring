const { productLineKey, clusterRows, findMissingItemSuggestions } = require('../src/services/neighborInference');

describe('productLineKey', () => {
  test('takes the first underscore-delimited token as the line key', () => {
    expect(productLineKey('coca_org_can_320')).toBe('coca');
    expect(productLineKey('coca_zero_can_320')).toBe('coca');
    expect(productLineKey('alpenliebe_2chew')).toBe('alpenliebe');
  });

  test('returns the id unchanged when there is no underscore', () => {
    expect(productLineKey('nosplit')).toBe('nosplit');
  });
});

describe('clusterRows', () => {
  const box = (id, y1, y2) => ({ box_id: id, bbox: [0, y1, 10, y2] });

  test('groups boxes within tolerance into the same row, splits ones farther apart', () => {
    const boxes = [box('a', 0, 10), box('b', 5, 15), box('c', 200, 210)];
    const rows = clusterRows(boxes, 20);
    expect(rows.map((r) => r.map((b) => b.box_id))).toEqual([['a', 'b'], ['c']]);
  });

  test('defaults tolerance to 20px, matching gap_detection.py row_cluster_tolerance', () => {
    const boxes = [box('a', 0, 10), box('b', 24, 34)]; // y-centers 5 and 29, diff 24 > 20
    expect(clusterRows(boxes)).toHaveLength(2);
  });
});

describe('findMissingItemSuggestions', () => {
  const catalog = new Map([
    ['coca_org_can_320', { name: 'Coca-Cola vị nguyên bản lon 320ml', price: 10000, shelfFullQty: 20 }],
    ['coca_zero_can_320', { name: 'Coca-Cola Zero lon 320ml', price: 10000, shelfFullQty: 20 }],
    ['coca_vani_can_320', { name: 'Coca-Cola vị vani lon 320ml', price: 10000, shelfFullQty: 20 }],
    ['coca_light_can_320', { name: 'Coca-Cola Light lon 320ml', price: 10000, shelfFullQty: 20 }],
    ['karo_org', { name: 'Bánh trứng tươi Karo', price: 41000, shelfFullQty: 10 }],
  ]);

  function gapBox(id, y, opts = {}) {
    return { box_id: id, type: 'gap', bbox: [100, y, 200, y + 50], sku_id: null, is_unknown: false, excluded_from_count: false, needs_review: false, ...opts };
  }
  function productBox(id, skuId, y, opts = {}) {
    return { box_id: id, type: 'product', bbox: [0, y, 90, y + 50], sku_id: skuId, is_unknown: false, excluded_from_count: false, needs_review: false, ...opts };
  }

  test('suggests same-row, same-line SKUs not yet detected anywhere in the image', () => {
    const scanRow = { boxes: [productBox('p1', 'coca_org_can_320', 10), gapBox('g1', 12)] };
    const result = findMissingItemSuggestions(scanRow, catalog);
    expect(result).toHaveLength(1);
    expect(result[0].gap_box_id).toBe('g1');
    expect(result[0].nearby_skus).toEqual([{ sku_id: 'coca_org_can_320', sku_name: 'Coca-Cola vị nguyên bản lon 320ml' }]);
    expect(result[0].candidates.map((c) => c.sku_id).sort()).toEqual(['coca_light_can_320', 'coca_vani_can_320', 'coca_zero_can_320']);
  });

  test('excludes a candidate already detected anywhere in the image, even outside the gap row', () => {
    const scanRow = {
      boxes: [productBox('p1', 'coca_org_can_320', 10), gapBox('g1', 12), productBox('p2', 'coca_zero_can_320', 500)],
    };
    const result = findMissingItemSuggestions(scanRow, catalog);
    expect(result[0].candidates.map((c) => c.sku_id)).not.toContain('coca_zero_can_320');
  });

  test('deduplicates nearby_skus when the same SKU has multiple facings in the row', () => {
    const scanRow = {
      boxes: [productBox('p1', 'coca_org_can_320', 10), productBox('p1b', 'coca_org_can_320', 11), gapBox('g1', 12)],
    };
    const result = findMissingItemSuggestions(scanRow, catalog);
    expect(result[0].nearby_skus).toEqual([{ sku_id: 'coca_org_can_320', sku_name: 'Coca-Cola vị nguyên bản lon 320ml' }]);
  });

  test('returns empty candidates when the neighbor SKU has no other line members in the catalog (abstain, do not guess)', () => {
    const scanRow = { boxes: [productBox('p1', 'karo_org', 10), gapBox('g1', 12)] };
    expect(findMissingItemSuggestions(scanRow, catalog)[0].candidates).toEqual([]);
  });

  test('returns empty nearby_skus and candidates for a gap with no product neighbors in its row', () => {
    const scanRow = { boxes: [gapBox('g1', 12), productBox('p1', 'coca_org_can_320', 500)] };
    const result = findMissingItemSuggestions(scanRow, catalog);
    expect(result[0].nearby_skus).toEqual([]);
    expect(result[0].candidates).toEqual([]);
  });

  test('ignores uncertain gaps (needs_review: true) -- not enough signal to also guess a SKU', () => {
    const scanRow = { boxes: [productBox('p1', 'coca_org_can_320', 10), gapBox('g1', 12, { needs_review: true })] };
    expect(findMissingItemSuggestions(scanRow, catalog)).toEqual([]);
  });

  test('caps candidates at 3', () => {
    const bigCatalog = new Map([
      ['x_a', { name: 'A', price: 1, shelfFullQty: 1 }],
      ['x_b', { name: 'B', price: 1, shelfFullQty: 1 }],
      ['x_c', { name: 'C', price: 1, shelfFullQty: 1 }],
      ['x_d', { name: 'D', price: 1, shelfFullQty: 1 }],
      ['x_e', { name: 'E', price: 1, shelfFullQty: 1 }],
    ]);
    const scanRow = { boxes: [productBox('p1', 'x_a', 10), gapBox('g1', 12)] };
    expect(findMissingItemSuggestions(scanRow, bigCatalog)[0].candidates).toHaveLength(3);
  });
});
