jest.mock('../src/services/mlService');

const request = require('supertest');
const mlService = require('../src/services/mlService');
const app = require('../src/app');

// Content doesn't matter -- mlService.predict is mocked, nothing reads these bytes.
const FAKE_IMAGE = Buffer.from([0x89, 0x50, 0x4e, 0x47]);

function postAnalyze(fields = {}) {
  const req = request(app).post('/analyze');
  if (fields.category !== undefined) req.field('category', fields.category);
  if (fields.container !== undefined) req.field('container', fields.container);
  if (fields.attachImage !== false) req.attach('image', FAKE_IMAGE, 'shelf.jpg');
  return req;
}

const WARNINGS = { low_confidence_regions: [], edge_crop_regions: [], blur_detected: false };

beforeEach(() => {
  mlService.predict.mockReset();
});

describe('POST /analyze', () => {
  test('status: ok -- all boxes recognized, no is_unknown', async () => {
    mlService.predict.mockResolvedValue({
      image: { width: 1200, height: 900 },
      boxes: [
        { box_id: 'b1', bbox: [0, 0, 10, 10], type: 'product', sku_id: 'choco_pie_org', sku_name: 'Bánh chocopie Orion hộp 217.8g (6 cái)', confidence: 0.94, is_unknown: false },
        { box_id: 'b2', bbox: [20, 0, 30, 10], type: 'product', sku_id: 'choco_pie_org', sku_name: 'Bánh chocopie Orion hộp 217.8g (6 cái)', confidence: 0.91, is_unknown: false },
      ],
      warnings: WARNINGS,
    });

    const res = await postAnalyze({ category: 'mi-goi', container: 'ke-a' });

    expect(res.status).toBe(200);
    expect(res.body.status).toBe('ok');
    expect(res.body.error_message).toBeNull();
    expect(res.body.category).toBe('mi-goi');
    expect(res.body.container).toBe('ke-a');
    expect(res.body.boxes).toHaveLength(2);
    expect(res.body.quantities).toHaveLength(1);
    expect(res.body.quantities[0].facing_count).toBe(2);
  });

  test('status: failed -- ml-service call throws', async () => {
    mlService.predict.mockRejectedValue(new Error('ml-service responded 500'));

    const res = await postAnalyze({ category: 'mi-goi', container: 'ke-a' });

    expect(res.status).toBe(200);
    expect(res.body.status).toBe('failed');
    expect(res.body.error_message).toMatch(/ml-service responded 500/);
    expect(res.body.boxes).toEqual([]);
    expect(res.body.quantities).toEqual([]);
    expect(res.body.image).toEqual({ width: 0, height: 0 });
    expect(res.body.total_value).toBe(0);
  });

  test('status: partial -- an is_unknown box does not hide the rest of the data', async () => {
    mlService.predict.mockResolvedValue({
      image: { width: 1200, height: 900 },
      boxes: [
        { box_id: 'b1', bbox: [0, 0, 10, 10], type: 'product', sku_id: 'choco_pie_org', sku_name: 'Bánh chocopie Orion hộp 217.8g (6 cái)', confidence: 0.94, is_unknown: false },
        { box_id: 'b2', bbox: [20, 0, 30, 10], type: 'product', sku_id: null, sku_name: null, confidence: 0.52, is_unknown: true },
      ],
      warnings: WARNINGS,
    });

    const res = await postAnalyze({ category: 'mi-goi', container: 'ke-a' });

    expect(res.status).toBe(200);
    expect(res.body.status).toBe('partial');
    expect(res.body.error_message).toBeNull();
    // partial must NOT behave like failed: boxes/quantities stay populated.
    expect(res.body.boxes).toHaveLength(2);
    expect(res.body.quantities).toHaveLength(1);
    expect(res.body.quantities[0].sku_id).toBe('choco_pie_org');
  });

  test('joins catalog for unit_price, shelf_full_qty, and subtotal', async () => {
    mlService.predict.mockResolvedValue({
      image: { width: 1200, height: 900 },
      boxes: [
        { box_id: 'b1', bbox: [0, 0, 10, 10], type: 'product', sku_id: 'choco_pie_org', sku_name: 'Bánh chocopie Orion hộp 217.8g (6 cái)', confidence: 0.94, is_unknown: false },
        { box_id: 'b2', bbox: [20, 0, 30, 10], type: 'product', sku_id: 'choco_pie_org', sku_name: 'Bánh chocopie Orion hộp 217.8g (6 cái)', confidence: 0.9, is_unknown: false },
        { box_id: 'b3', bbox: [40, 0, 50, 10], type: 'product', sku_id: 'karo_org', sku_name: 'Bánh trứng tươi chà bông Karo Richy túi 156g', confidence: 0.89, is_unknown: false },
      ],
      warnings: WARNINGS,
    });

    const res = await postAnalyze({ category: 'mi-goi', container: 'ke-a' });

    const choco = res.body.quantities.find((q) => q.sku_id === 'choco_pie_org');
    expect(choco).toMatchObject({
      facing_count: 2,
      depth: 1,
      total_quantity: 2,
      shelf_full_qty: 10,
      unit_price: 30000,
      subtotal: 60000,
      flag_status: 'low', // 2 < 0.3 * 10
    });

    const karo = res.body.quantities.find((q) => q.sku_id === 'karo_org');
    expect(karo).toMatchObject({
      facing_count: 1,
      unit_price: 41000,
      shelf_full_qty: 10,
      subtotal: 41000,
      flag_status: 'low',
    });

    expect(res.body.total_value).toBe(60000 + 41000);
  });

  test('excludes boxes flagged excluded_from_count from facing_count', async () => {
    mlService.predict.mockResolvedValue({
      image: { width: 1200, height: 900 },
      boxes: [
        { box_id: 'b1', bbox: [0, 0, 10, 10], type: 'product', sku_id: 'choco_pie_org', sku_name: 'Bánh chocopie Orion hộp 217.8g (6 cái)', confidence: 0.94, is_unknown: false, excluded_from_count: false },
        { box_id: 'b2', bbox: [20, 0, 30, 10], type: 'product', sku_id: 'choco_pie_org', sku_name: 'Bánh chocopie Orion hộp 217.8g (6 cái)', confidence: 0.91, is_unknown: false, excluded_from_count: true },
      ],
      warnings: WARNINGS,
    });

    const res = await postAnalyze({ category: 'mi-goi', container: 'ke-a' });

    expect(res.status).toBe(200);
    expect(res.body.quantities).toHaveLength(1);
    expect(res.body.quantities[0].facing_count).toBe(1);
    // excluded box still comes back in boxes so the FE can draw the purple flag overlay.
    expect(res.body.boxes).toHaveLength(2);
  });

  test('rejects a request missing category/container/image with 400', async () => {
    const res = await postAnalyze({ container: 'ke-a' });
    expect(res.status).toBe(400);
    expect(mlService.predict).not.toHaveBeenCalled();
  });

  test('rejects a category/container that does not exist or is not active with 400', async () => {
    const res1 = await postAnalyze({ category: 'mi-goi', container: 'ke-b' }); // exists but not active
    expect(res1.status).toBe(400);
    expect(mlService.predict).not.toHaveBeenCalled();

    const res2 = await postAnalyze({ category: 'banh-keo', container: 'ke-a' }); // category exists but not active
    expect(res2.status).toBe(400);

    const res3 = await postAnalyze({ category: 'khong-ton-tai', container: 'ke-a' }); // category doesn't exist
    expect(res3.status).toBe(400);
  });
});
