const os = require('node:os');
const path = require('node:path');
const fs = require('node:fs');
const crypto = require('node:crypto');
const request = require('supertest');
const app = require('../src/app');
const { scansDb } = require('../src/services/scansDb');
const { getUploadsDir } = require('../src/config/uploadsDir');

let testUploadsDir;

beforeAll(() => {
  testUploadsDir = path.join(os.tmpdir(), `shelf-uploads-test-${crypto.randomUUID()}`);
  process.env.UPLOADS_DIR = testUploadsDir;
});

afterAll(() => {
  delete process.env.UPLOADS_DIR;
  fs.rmSync(testUploadsDir, { recursive: true, force: true });
});

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

  test('discards a non-array boxes value instead of persisting it, storing [] for a new scan', async () => {
    const res1 = await request(app).post('/confirm').send({
      scan_id: 'scan-boxes-2',
      category: 'mi-goi',
      container: 'ke-a',
      quantities: QUANTITIES,
      total_value: 60000,
      boxes: 'oops',
    });
    expect(res1.status).toBe(200);
    expect(scansDb.getScanById('scan-boxes-2').boxes).toEqual([]);

    const res2 = await request(app).post('/confirm').send({
      scan_id: 'scan-boxes-3',
      category: 'mi-goi',
      container: 'ke-a',
      quantities: QUANTITIES,
      total_value: 60000,
      boxes: { not: 'an array' },
    });
    expect(res2.status).toBe(200);
    expect(scansDb.getScanById('scan-boxes-3').boxes).toEqual([]);
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

  test('rejects a scan_id with characters outside [A-Za-z0-9_-] with 400', async () => {
    const res = await request(app).post('/confirm').send({
      scan_id: '../../etc/passwd',
      category: 'mi-goi',
      container: 'ke-a',
      quantities: QUANTITIES,
      total_value: 60000,
    });
    expect(res.status).toBe(400);
    expect(scansDb.getScanById('../../etc/passwd')).toBeNull();
  });
});

describe('POST /confirm/:scanId/image', () => {
  const FAKE_IMAGE = Buffer.from([0x89, 0x50, 0x4e, 0x47]);

  test('stores the uploaded image and returns saved: true', async () => {
    await request(app).post('/confirm').send({
      scan_id: 'img-scan-1',
      category: 'mi-goi',
      container: 'ke-a',
      quantities: QUANTITIES,
      total_value: 60000,
    });

    const res = await request(app)
      .post('/confirm/img-scan-1/image')
      .field('width', '4032')
      .field('height', '3024')
      .attach('image', FAKE_IMAGE, 'shelf.jpg');

    expect(res.status).toBe(200);
    expect(res.body).toEqual({ saved: true, image_path: 'img-scan-1.jpg' });

    const saved = scansDb.getScanById('img-scan-1');
    expect(saved.image_path).toBe('img-scan-1.jpg');
    expect(saved.image_width).toBe(4032);
    expect(saved.image_height).toBe(3024);

    const filePath = path.join(getUploadsDir(), 'img-scan-1.jpg');
    expect(fs.existsSync(filePath)).toBe(true);
    expect(Buffer.compare(fs.readFileSync(filePath), FAKE_IMAGE)).toBe(0);
  });

  test('always names the stored file <scanId>.jpg, ignoring the client-supplied filename/extension', async () => {
    await request(app).post('/confirm').send({
      scan_id: 'img-scan-ext',
      category: 'mi-goi',
      container: 'ke-a',
      quantities: QUANTITIES,
      total_value: 60000,
    });

    await request(app)
      .post('/confirm/img-scan-ext/image')
      .field('width', '100')
      .field('height', '100')
      .attach('image', FAKE_IMAGE, 'photo.png');

    expect(fs.existsSync(path.join(getUploadsDir(), 'img-scan-ext.jpg'))).toBe(true);
    expect(fs.existsSync(path.join(getUploadsDir(), 'img-scan-ext.png'))).toBe(false);
  });

  test('returns 404 and does not write a file for a scan_id that does not exist', async () => {
    const res = await request(app)
      .post('/confirm/does-not-exist/image')
      .field('width', '100')
      .field('height', '100')
      .attach('image', FAKE_IMAGE, 'shelf.jpg');

    expect(res.status).toBe(404);
    expect(fs.existsSync(path.join(getUploadsDir(), 'does-not-exist.jpg'))).toBe(false);
  });

  test('returns 400 when width/height are missing', async () => {
    await request(app).post('/confirm').send({
      scan_id: 'img-scan-2',
      category: 'mi-goi',
      container: 'ke-a',
      quantities: QUANTITIES,
      total_value: 60000,
    });

    const res = await request(app).post('/confirm/img-scan-2/image').attach('image', FAKE_IMAGE, 'shelf.jpg');
    expect(res.status).toBe(400);
    expect(scansDb.getScanById('img-scan-2').image_path).toBeNull();
  });

  test('returns 400 when no image file is attached', async () => {
    await request(app).post('/confirm').send({
      scan_id: 'img-scan-3',
      category: 'mi-goi',
      container: 'ke-a',
      quantities: QUANTITIES,
      total_value: 60000,
    });

    const res = await request(app).post('/confirm/img-scan-3/image').field('width', '100').field('height', '100');
    expect(res.status).toBe(400);
  });

  test('GET /uploads/:file serves the uploaded image bytes back', async () => {
    await request(app).post('/confirm').send({
      scan_id: 'img-scan-4',
      category: 'mi-goi',
      container: 'ke-a',
      quantities: QUANTITIES,
      total_value: 60000,
    });
    await request(app)
      .post('/confirm/img-scan-4/image')
      .field('width', '100')
      .field('height', '100')
      .attach('image', FAKE_IMAGE, 'shelf.jpg');

    const res = await request(app).get('/uploads/img-scan-4.jpg');
    expect(res.status).toBe(200);
    expect(Buffer.compare(res.body, FAKE_IMAGE)).toBe(0);
  });

  test('rejects a scan_id with characters outside [A-Za-z0-9_-] before multer writes anything', async () => {
    // Snapshot the dir first -- earlier tests in this file already wrote
    // files there, so the assertion must be "nothing new appeared", not
    // "the dir is empty".
    const before = fs.readdirSync(getUploadsDir());

    const res = await request(app)
      .post('/confirm/img@scan!1/image')
      .field('width', '100')
      .field('height', '100')
      .attach('image', FAKE_IMAGE, 'shelf.jpg');

    expect(res.status).toBe(400);
    // Proves the reject happened before multer's diskStorage callbacks ran --
    // no file landed under any name derived from this scan_id.
    expect(fs.readdirSync(getUploadsDir())).toEqual(before);
  });
});
