const request = require('supertest');
const app = require('../src/app');

describe('GET /shelves', () => {
  test('returns the full registry with active flags', async () => {
    const res = await request(app).get('/shelves');

    expect(res.status).toBe(200);
    expect(Array.isArray(res.body.categories)).toBe(true);
    expect(res.body.categories).toHaveLength(7);

    const miGoi = res.body.categories.find((c) => c.slug === 'mi-goi');
    expect(miGoi.active).toBe(true);
    expect(miGoi.containers.find((c) => c.id === 'ke-a').active).toBe(true);
    expect(miGoi.containers.find((c) => c.id === 'ke-b').active).toBe(false);

    const banhKeo = res.body.categories.find((c) => c.slug === 'banh-keo');
    expect(banhKeo.active).toBe(false);
  });
});
