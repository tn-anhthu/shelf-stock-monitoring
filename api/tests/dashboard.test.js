const request = require('supertest');
const app = require('../src/app');
const { scansDb } = require('../src/services/scansDb');
const { catalog } = require('../src/services/catalog');
const { computeKpis, computeStatusBreakdown, computeAttentionList, buildDashboardPayload } = require('../src/services/dashboard');

const QUANTITIES = [
  {
    sku_id: 'a',
    sku_name: 'A',
    facing_count: 8,
    depth: 1,
    total_quantity: 8,
    shelf_full_qty: 10,
    unit_price: 100,
    subtotal: 800,
    flag_status: 'ok',
  },
  {
    sku_id: 'b',
    sku_name: 'B',
    facing_count: 2,
    depth: 1,
    total_quantity: 2,
    shelf_full_qty: 10,
    unit_price: 200,
    subtotal: 400,
    flag_status: 'low',
  },
  {
    sku_id: 'c',
    sku_name: 'C',
    facing_count: 0,
    depth: 1,
    total_quantity: 0,
    shelf_full_qty: 5,
    unit_price: 50,
    subtotal: 0,
    flag_status: 'out',
  },
];

describe('dashboard service', () => {
  test('computeKpis sums subtotal, counts SKUs, computes stock health and missed opportunity', () => {
    const kpis = computeKpis(QUANTITIES);
    expect(kpis.total_value).toBe(1200);
    expect(kpis.total_sku_count).toBe(3);
    expect(kpis.stock_health_pct).toBe(33);
    // b: (10-2)*200=1600, c: (5-0)*50=250
    expect(kpis.missed_opportunity_total).toBe(1850);
  });

  test('computeStatusBreakdown counts ok/low/out', () => {
    expect(computeStatusBreakdown(QUANTITIES)).toEqual({ ok: 1, low: 1, out: 1 });
  });

  test('computeAttentionList sorts out before low, by missed_value desc within group', () => {
    const list = computeAttentionList(QUANTITIES);
    expect(list.map((q) => q.sku_id)).toEqual(['c', 'b']);
    expect(list[0].missed_value).toBe(250);
    expect(list[1].missed_value).toBe(1600);
  });

  test('buildDashboardPayload includes missing_items computed from scanRow.boxes and catalog', () => {
    const scanRow = {
      scan_id: 's',
      confirmed_at: 't',
      quantities: QUANTITIES,
      boxes: [
        { box_id: 'p1', type: 'product', bbox: [0, 10, 90, 60], sku_id: 'a', is_unknown: false, excluded_from_count: false, needs_review: false },
        { box_id: 'g1', type: 'gap', bbox: [100, 10, 200, 60], sku_id: null, is_unknown: false, excluded_from_count: false, needs_review: false },
      ],
    };
    const payload = buildDashboardPayload(scanRow, catalog);
    expect(Array.isArray(payload.missing_items)).toBe(true);
  });
});

describe('GET /dashboard', () => {
  test('400 when category/container missing or not active', async () => {
    const res1 = await request(app).get('/dashboard');
    expect(res1.status).toBe(400);

    const res2 = await request(app).get('/dashboard').query({ category: 'mi-goi', container: 'ke-b' });
    expect(res2.status).toBe(400);

    const res3 = await request(app).get('/dashboard').query({ category: 'banh-keo', container: 'ke-a' });
    expect(res3.status).toBe(400);
  });

  test('returns has_data: false when the active shelf has no scan yet', async () => {
    const res = await request(app).get('/dashboard').query({ category: 'sua', container: 'ke-a' });
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ has_data: false });
  });

  test('returns computed payload for the latest scan on an active shelf', async () => {
    scansDb.insertScan({
      scanId: 'dash-scan-1',
      category: 'mi-goi',
      container: 'ke-a',
      quantities: QUANTITIES,
      totalValue: 1200,
    });

    const res = await request(app).get('/dashboard').query({ category: 'mi-goi', container: 'ke-a' });
    expect(res.status).toBe(200);
    expect(res.body.has_data).toBe(true);
    expect(res.body.scan_id).toBe('dash-scan-1');
    expect(res.body.kpis.total_value).toBe(1200);
    expect(res.body.status_breakdown).toEqual({ ok: 1, low: 1, out: 1 });
    expect(res.body.attention_list.map((q) => q.sku_id)).toEqual(['c', 'b']);
    expect(res.body.full_table).toHaveLength(3);
  });

  test('returns missing_items derived from the scan boxes', async () => {
    const boxes = [
      { box_id: 'p1', type: 'product', bbox: [0, 10, 90, 60], sku_id: 'choco_pie_org', is_unknown: false, excluded_from_count: false, needs_review: false },
      { box_id: 'g1', type: 'gap', bbox: [100, 10, 200, 60], sku_id: null, is_unknown: false, excluded_from_count: false, needs_review: false },
    ];
    scansDb.insertScan({
      scanId: 'dash-scan-2',
      category: 'nuoc-giai-khat',
      container: 'tu-a',
      quantities: [{ sku_id: 'choco_pie_org', sku_name: 'A', facing_count: 1, depth: 1, total_quantity: 1, shelf_full_qty: 10, unit_price: 30000, subtotal: 30000, flag_status: 'low' }],
      totalValue: 30000,
      boxes,
    });

    const res = await request(app).get('/dashboard').query({ category: 'nuoc-giai-khat', container: 'tu-a' });
    expect(res.status).toBe(200);
    const item = res.body.missing_items.find((m) => m.gap_box_id === 'g1');
    expect(item).toBeDefined();
    expect(item.nearby_skus).toEqual([{ sku_id: 'choco_pie_org', sku_name: expect.any(String) }]);
  });

  test('returns missing_items: [] when the latest scan has no boxes stored (pre-migration scan)', async () => {
    scansDb.insertScan({ scanId: 'dash-scan-3', category: 'mi-goi', container: 'ke-a', quantities: QUANTITIES, totalValue: 1200 });
    const res = await request(app).get('/dashboard').query({ category: 'mi-goi', container: 'ke-a' });
    expect(res.body.missing_items).toEqual([]);
  });
});
