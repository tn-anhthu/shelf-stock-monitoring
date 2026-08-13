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
    expect(saved.quantities).toEqual(QUANTITIES);
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
});
