# Schema `harryrobert/SKU-110k-reformat` (bộ train) — xác nhận 17/7/2026

Dùng để **train** (khác với `Voxel51/sku110k_test` chỉ dùng để eval — xem
`schema-sku110k.md`).

Lệnh kiểm tra: `get_dataset_split_names('harryrobert/SKU-110k-reformat')`, sau đó
`load_dataset('harryrobert/SKU-110k-reformat', split='train', streaming=True)`, lấy
sample đầu.

**Các split:** `train` (8219 ảnh), `validation` (588 ảnh), `test` (2936 ảnh) — số lượng
này khớp chính xác với số liệu chính thức của SKU-110K.

**Cấu trúc field:**
```
{'image': Image, 'image_id': int64, 'width': int32, 'height': int32,
 'objects': {'id': [int64], 'bbox': [[float32; 4]], 'category': [int64], 'area': [float32]}}
```

`objects.bbox` = `(x, y, w, h)` **tọa độ pixel tuyệt đối, gốc ở góc trên-trái** (kiểu
COCO — khác với `Voxel51/sku110k_test` dùng tọa độ *tương đối*, **không dùng chung hàm**
`parse_fiftyone_detections` cho 2 dataset này). `category` là 1 giá trị hằng số cho mọi
object — SKU-110K không phân loại sản phẩm, chỉ khoanh vùng ("object"), giống bộ eval.

**Không dùng để eval:** split `test` của repo này (2936 ảnh, trùng số lượng với
`Voxel51/sku110k_test`) chưa xác nhận có phải ảnh khác hay không — dự án chỉ dùng
`train`/`validation` từ repo này để train, còn eval luôn cố định dùng
`Voxel51/sku110k_test` qua `src/detection/benchmark/data.py`, không đổi.
