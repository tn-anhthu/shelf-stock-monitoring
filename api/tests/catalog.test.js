const request = require('supertest');
const app = require('../src/app');

describe('GET /catalog', () => {
  test('returns catalog entries with sku_id, name, price, shelf_full_qty', async () => {
    const res = await request(app).get('/catalog');

    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
    expect(res.body.length).toBeGreaterThan(0);

    const choco = res.body.find((item) => item.sku_id === 'choco_pie_org');
    expect(choco).toMatchObject({
      sku_id: 'choco_pie_org',
      name: 'Bánh chocopie Orion hộp 217.8g (6 cái)',
      price: 30000,
      shelf_full_qty: 10,
    });
  });
});
