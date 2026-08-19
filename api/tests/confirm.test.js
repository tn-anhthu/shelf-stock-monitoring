const request = require('supertest');
const app = require('../src/app');
const { scansDb } = require('../src/services/scansDb');

const QUANTITIES = [
  {
    sku_id: 'choco_pie_org',
    sku_name: 'Bánh chocopie Orion hộp 217.8g (6 cái)',
    facing_count: 2,
    depth: 1,
    total_quantity: 2,
    shelf_full_qty: 10,
    unit_price: 30000,
    subtotal: 60000,
    flag_status: 'low',
  },
];

describe('POST /confirm', () => {
  test('inserts a scan into SQLite and returns confirmed: true', async () => {
    const payload = {
      scan_id: 'scan-1',
      category: 'mi-goi',
      container: 'ke-a',
      quantities: QUANTITIES,
      total_value: 60000,
    };

    const res = await request(app).post('/confirm').send(payload);

    expect(res.status).toBe(200);
    expect(res.body).toEqual({ confirmed: true, scan_id: 'scan-1' });

    const saved = scansDb.getScanById('scan-1');
    expect(saved).toMatchObject({
      scan_id: 'scan-1',
      category: 'mi-goi',
      container: 'ke-a',
      total_value: 60000,
    });
    expect(saved.quantities).toEqual([{ ...QUANTITIES[0], source: 'scan' }]);
  });

  test('rejects a request with an empty quantities array with 400', async () => {
    const res = await request(app).post('/confirm').send({
      scan_id: 'scan-2',
      category: 'mi-goi',
      container: 'ke-a',
      quantities: [],
      total_value: 0,
    });
    expect(res.status).toBe(400);
    expect(scansDb.getScanById('scan-2')).toBeNull();
  });

  test('rejects a request missing quantities entirely with 400', async () => {
    const res = await request(app).post('/confirm').send({
      scan_id: 'scan-3',
      category: 'mi-goi',
      container: 'ke-a',
      total_value: 0,
    });
    expect(res.status).toBe(400);
  });

  test('rejects a request missing category with 400', async () => {
    const res = await request(app).post('/confirm').send({
      scan_id: 'scan-4',
      container: 'ke-a',
      quantities: QUANTITIES,
      total_value: 60000,
    });
    expect(res.status).toBe(400);
  });

  test('rejects a category/container that does not exist or is not active with 400', async () => {
    const res1 = await request(app).post('/confirm').send({
      scan_id: 'scan-5',
      category: 'mi-goi',
      container: 'ke-b', // exists but not active
      quantities: QUANTITIES,
      total_value: 60000,
    });
    expect(res1.status).toBe(400);
    expect(scansDb.getScanById('scan-5')).toBeNull();

    const res2 = await request(app).post('/confirm').send({
      scan_id: 'scan-6',
      category: 'banh-keo', // category exists but not active
      container: 'ke-a',
      quantities: QUANTITIES,
      total_value: 60000,
    });
    expect(res2.status).toBe(400);

    const res3 = await request(app).post('/confirm').send({
      scan_id: 'scan-7',
      category: 'khong-ton-tai', // category doesn't exist
      container: 'ke-a',
      quantities: QUANTITIES,
      total_value: 60000,
    });
    expect(res3.status).toBe(400);
  });

  test('stores boxes when provided in the payload', async () => {
    const boxes = [{ box_id: 'b1', type: 'gap', bbox: [1, 2, 3, 4], sku_id: null, needs_review: false }];
    const res = await request(app).post('/confirm').send({
      scan_id: 'scan-boxes-1',
      category: 'mi-goi',
      container: 'ke-a',
      quantities: QUANTITIES,
      total_value: 60000,
      boxes,
    });
    expect(res.status).toBe(200);
    expect(scansDb.getScanById('scan-boxes-1').boxes).toEqual(boxes);
  });

  test('defaults source to "scan" on quantities rows that do not already specify it', async () => {
    const res = await request(app).post('/confirm').send({
      scan_id: 'scan-source-1',
      category: 'mi-goi',
      container: 'ke-a',
      quantities: QUANTITIES,
      total_value: 60000,
    });
    expect(res.status).toBe(200);
    expect(scansDb.getScanById('scan-source-1').quantities[0].source).toBe('scan');
  });

  test('keeps an explicit source value instead of overwriting it', async () => {
    const res = await request(app).post('/confirm').send({
      scan_id: 'scan-source-2',
      category: 'mi-goi',
      container: 'ke-a',
      quantities: [{ ...QUANTITIES[0], source: 'oos_confirmation' }],
      total_value: 60000,
    });
    expect(res.status).toBe(200);
    expect(scansDb.getScanById('scan-source-2').quantities[0].source).toBe('oos_confirmation');
  });
});
