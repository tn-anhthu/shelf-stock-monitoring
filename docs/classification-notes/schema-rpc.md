# Schema `benjamintli/retail-product-checkout` (RPC) — xác nhận 18/7/2026

Lệnh dùng: `hf_hub_download` + `load_dataset('parquet', data_files=<shard path>, split='train')`
trên `train-00000-of-00019.parquet` và `test-00000-of-00011.parquet`.

**Các split:** `train` (19 shard), `test` (11 shard), `validation` (3 shard) — không có
split "exemplar" riêng. **Split `train` dùng làm nguồn catalog** (mỗi ảnh 1 sản phẩm,
gom theo category), **split `test` dùng làm nguồn test classification** (8-9 sản phẩm/ảnh
theo cảnh tính tiền thật, có ground-truth bbox + category từng sản phẩm).

**Cấu trúc field:**
```
{'image': Image, 'objects': {'bbox': [[float32; 4]], 'category': ClassLabel}}
```

`objects.bbox` = `(x, y, w, h)` **tọa độ pixel tuyệt đối, gốc góc trên-trái** (cùng quy
ước với `harryrobert/SKU-110k-reformat` ở Phase 1). Ví dụ từ `train-00000`:
`[1171.68, 1047.6, 399.85, 284.1]`.

`objects.category` = số nguyên (`ClassLabel`) cho mỗi object; tổng cộng 200 category có
tên, theo đúng phân loại gốc của paper RPC. Ví dụ: category index 111 = `"112_canned_food"`.
Lấy toàn bộ danh sách tên qua `ds.features['objects']['category'].feature.names`.

**Đặc điểm split `train`** (kiểm tra trên 5 ảnh đầu của `train-00000`):
- Đúng 1 object/ảnh (1 sản phẩm, chụp sạch)
- Kích thước ảnh ví dụ: (2592, 1944)
- Cả 5 ảnh mẫu đều thuộc category 111 (`112_canned_food`)

**Đặc điểm split `test`** (kiểm tra trên 5 ảnh đầu của `test-00000`):
- 8-9 object/ảnh (cảnh tính tiền, nhiều sản phẩm)
- Có ground-truth bbox + category từng object
- Đại diện đúng tình huống tính tiền thật, nhiều SKU trong 1 khung hình

**Lưu ý quan trọng:** `load_dataset(..., streaming=True)` trên dataset này bị treo hơn 10
phút, không có output gì (cả cách load mặc định lẫn dùng `data_files=` cho 1 shard) —
trong khi `hf_hub_download` tải trực tiếp đúng file shard đó chỉ mất vài giây. **Không
dùng streaming cho dataset này** — tải trực tiếp từng file shard thay vào đó.

**Tổng số file trong repo:** 35 (`.gitattributes`, `README.md`, 19 shard `train-*.parquet`,
11 shard `test-*.parquet`, 3 shard `validation-*.parquet`).
