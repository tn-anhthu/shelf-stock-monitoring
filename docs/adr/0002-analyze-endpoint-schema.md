# ADR-002: `POST /analyze` request/response schema

**Status:** Accepted (2026-07-28)
**Liên quan:** [ADR-001](0001-migrate-node-api-frontend.md) (kiến trúc 3 tầng ml-service/api/web)

## Context

ADR-001 chốt trình tự triển khai "contract-first": chốt JSON schema của `POST /analyze` trước khi implement, để `api` (mock `ml-service`) và `web` phát triển song song không bị chặn bởi CV pipeline thật. Tài liệu này chốt schema đó.

## Kiến trúc luồng dữ liệu

```
web  --multipart(store_id, shelf_id, image)-->  api  POST /analyze
                                                   |
                                                   | multipart(image) --> ml-service POST /predict
                                                   |                       <-- { image, boxes }
                                                   |
                                                   | join boxes.sku_id với data/catalog/catalog_seed.csv
                                                   | aggregate boxes -> quantities theo sku_id
                                                   | tính flag_status, total_value
                                                   v
                                                 { scan_id, store_id, shelf_id, timestamp, status,
                                                   error_message, image, boxes, quantities, warnings,
                                                   total_value }
```

**Nguyên tắc phân tầng:** `ml-service` chỉ biết về pixel: box, sku_id (nếu nhận diện được), confidence. Nó KHÔNG biết giá hay `shelf_full_qty` (đó là dữ liệu nghiệp vụ/catalog, không phải CV). `api` chịu trách nhiệm join catalog và aggregate `quantities` từ `boxes`, `quantities` không phải nguồn dữ liệu độc lập.

## `ml-service`: `POST /predict`

Request: `multipart/form-data`, field `image` (file).

Response:
```json
{
  "image": { "width": 1200, "height": 900 },
  "boxes": [
    {
      "box_id": "string",
      "bbox": [0, 0, 0, 0],
      "type": "product | gap",
      "sku_id": "string | null",
      "sku_name": "string | null",
      "confidence": 0.0,
      "is_unknown": false
    }
  ],
  "warnings": {
    "low_confidence_regions": [],
    "edge_crop_regions": [],
    "blur_detected": false
  }
}
```

`image.width/height` đọc từ ảnh thật (Pillow), không phải mock. `boxes`/`warnings` ở giai đoạn hiện tại là mock cố định, không phụ thuộc nội dung ảnh.

`ml-service` không biết `unit_price`/`shelf_full_qty`/`subtotal`/`quantities`/`total_value`, các trường đó chỉ xuất hiện ở response của `api`, không xuất hiện ở đây.

## `api`: `POST /analyze`

### Request

`multipart/form-data`:
- `store_id` (string, bắt buộc)
- `shelf_id` (string, bắt buộc)
- `image` (file, bắt buộc)

Lý do chọn multipart thay vì base64 JSON: khớp trực tiếp với `<input type="file">` ở `web`, không cần encode/decode base64 ở client; `api` forward multipart nguyên trạng sang `ml-service`.

### Response

```json
{
  "scan_id": "string (uuid)",
  "store_id": "string",
  "shelf_id": "string",
  "timestamp": "ISO 8601 string",
  "status": "ok | failed | partial",
  "error_message": "string | null",
  "image": { "width": 0, "height": 0 },
  "boxes": [
    {
      "box_id": "string",
      "bbox": [0, 0, 0, 0],
      "type": "product | gap",
      "sku_id": "string | null",
      "sku_name": "string | null",
      "confidence": 0.0,
      "is_unknown": false
    }
  ],
  "quantities": [
    {
      "sku_id": "string",
      "sku_name": "string",
      "facing_count": 0,
      "depth": 1,
      "total_quantity": 0,
      "shelf_full_qty": 0,
      "unit_price": 0,
      "subtotal": 0,
      "flag_status": "ok | low | out"
    }
  ],
  "warnings": {
    "low_confidence_regions": [],
    "edge_crop_regions": [],
    "blur_detected": false
  },
  "total_value": 0
}
```

### Field notes

- `boxes`: passthrough gần như nguyên trạng từ `ml-service`, chỉ thêm `sku_name` nếu `ml-service` không tự điền (mock hiện tại đã điền sẵn).
- `quantities`: aggregate server-side, group theo `sku_id` trên các box có `type: "product"` và `sku_id != null` (box `type: "gap"` hoặc `is_unknown: true` không vào `quantities`, không có SKU để định giá). `facing_count` = số box cùng `sku_id`. `depth` = 1 (cố định ở giai đoạn hiện tại, pipeline CV chưa ước lượng depth). `total_quantity` = `facing_count * depth`. `unit_price`/`shelf_full_qty`/`subtotal` join từ `catalog_seed.csv` theo `sku_id`.
- `total_value` = tổng `subtotal` của `quantities`.
- `warnings`: passthrough từ `ml-service`.

### `flag_status` (hằng số, không hardcode rải rác, xem `api/src/config/flagStatus.js`)

- `out`: `total_quantity == 0`
- `low`: `total_quantity < LOW_STOCK_RATIO * shelf_full_qty` (`LOW_STOCK_RATIO = 0.3`)
- `ok`: còn lại

### `status`

- `"ok"`: gọi `ml-service` thành công, mọi box nhận diện được (không có `is_unknown: true`).
- `"partial"`: gọi `ml-service` thành công NHƯNG có ít nhất 1 box `is_unknown: true` (vùng có sản phẩm nhưng không khớp catalog). Dữ liệu vẫn đầy đủ và hiển thị bình thường như `"ok"`, không được xử lý giống `"failed"`, không được ẩn `boxes`/`quantities`. FE chỉ tô cảnh báo nhẹ để người dùng biết có sản phẩm chưa nhận diện được.
- `"failed"`: gọi `ml-service` lỗi (network error, timeout, non-2xx). `error_message` chứa lý do; `boxes`/`quantities` là mảng rỗng, `image` là `{width: 0, height: 0}`, `total_value` = 0.

`error_message`: `null` trừ khi `status == "failed"`.

## Ví dụ

### `status: ok`
```json
{
  "scan_id": "a1b2c3d4-0000-0000-0000-000000000001",
  "store_id": "store_01",
  "shelf_id": "shelf_A1",
  "timestamp": "2026-07-28T10:00:00.000Z",
  "status": "ok",
  "error_message": null,
  "image": { "width": 1200, "height": 900 },
  "boxes": [
    { "box_id": "b1", "bbox": [10, 10, 110, 210], "type": "product", "sku_id": "choco_pie_org", "sku_name": "Bánh chocopie Orion hộp 217.8g (6 cái)", "confidence": 0.94, "is_unknown": false },
    { "box_id": "b2", "bbox": [120, 10, 220, 210], "type": "product", "sku_id": "choco_pie_org", "sku_name": "Bánh chocopie Orion hộp 217.8g (6 cái)", "confidence": 0.91, "is_unknown": false }
  ],
  "quantities": [
    { "sku_id": "choco_pie_org", "sku_name": "Bánh chocopie Orion hộp 217.8g (6 cái)", "facing_count": 2, "depth": 1, "total_quantity": 2, "shelf_full_qty": 10, "unit_price": 30000, "subtotal": 60000, "flag_status": "low" }
  ],
  "warnings": { "low_confidence_regions": [], "edge_crop_regions": [], "blur_detected": false },
  "total_value": 60000
}
```

### `status: failed`
```json
{
  "scan_id": "a1b2c3d4-0000-0000-0000-000000000002",
  "store_id": "store_01",
  "shelf_id": "shelf_A1",
  "timestamp": "2026-07-28T10:05:00.000Z",
  "status": "failed",
  "error_message": "ml-service unreachable: connect ECONNREFUSED",
  "image": { "width": 0, "height": 0 },
  "boxes": [],
  "quantities": [],
  "warnings": { "low_confidence_regions": [], "edge_crop_regions": [], "blur_detected": false },
  "total_value": 0
}
```

### `status: partial`
```json
{
  "scan_id": "a1b2c3d4-0000-0000-0000-000000000003",
  "store_id": "store_01",
  "shelf_id": "shelf_A1",
  "timestamp": "2026-07-28T10:10:00.000Z",
  "status": "partial",
  "error_message": null,
  "image": { "width": 1200, "height": 900 },
  "boxes": [
    { "box_id": "b1", "bbox": [10, 10, 110, 210], "type": "product", "sku_id": "choco_pie_org", "sku_name": "Bánh chocopie Orion hộp 217.8g (6 cái)", "confidence": 0.94, "is_unknown": false },
    { "box_id": "b2", "bbox": [230, 10, 330, 210], "type": "product", "sku_id": null, "sku_name": null, "confidence": 0.55, "is_unknown": true }
  ],
  "quantities": [
    { "sku_id": "choco_pie_org", "sku_name": "Bánh chocopie Orion hộp 217.8g (6 cái)", "facing_count": 1, "depth": 1, "total_quantity": 1, "shelf_full_qty": 10, "unit_price": 30000, "subtotal": 30000, "flag_status": "low" }
  ],
  "warnings": { "low_confidence_regions": [], "edge_crop_regions": [], "blur_detected": false },
  "total_value": 30000
}
```

## Mock data (giai đoạn hiện tại)

`ml-service` trả `boxes` cố định, không phụ thuộc nội dung ảnh upload, gồm:
- 2 box `type: "product"`, `sku_id: "choco_pie_org"` (SKU thật trong `catalog_seed.csv`), để test facing_count aggregate và catalog join.
- 1 box `type: "product"`, `sku_id: "karo_org"`, SKU thật khác, để test có nhiều SKU trong 1 lần quét.
- 1 box `type: "product"`, `is_unknown: true`, `sku_id: null`, để test nhánh `status: "partial"`.
- 1 box `type: "gap"`, để test box không vào `quantities`.

`image.width`/`image.height` đọc thật từ file upload qua Pillow.

## Out of scope (giai đoạn này)

- `depth` ước lượng thật (đang cố định = 1).
- `ml-service` gọi pipeline CV thật (`src/pipeline/scan.py`), nối sau khi backend CV ổn định hơn, theo checkpoint rollback ở ADR-001.
- Auth, rate limiting, upload size limit ngoài giới hạn mặc định của multer.
