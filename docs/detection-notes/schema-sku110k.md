# Schema `Voxel51/sku110k_test` (bộ eval) — xác nhận 17/7/2026

Dùng để **đánh giá** detection (không dùng để train). Giữ nguyên tên field/code bằng
tiếng Anh vì đối chiếu trực tiếp với code.

## Thử load bằng `datasets.load_dataset` — không có nhãn

```python
from datasets import load_dataset
ds = load_dataset('Voxel51/sku110k_test', split='test', streaming=True)
sample = next(iter(ds))
print(sample.keys())
```

Kết quả: `dict_keys(['image'])` — dataset này **không lộ ground-truth qua thư viện
`datasets` thông thường**. `data.py` không dùng được cách này để lấy nhãn.

## Thử `fiftyone.utils.huggingface.load_from_hub` — đúng nhưng tải quá nhiều

FiftyOne đọc được `Detection` object có `bounding_box` đúng format, nhưng
`load_from_hub(..., max_samples=3)` thực tế tải **hơn 2.2GB** (vẫn đang tăng khi bị dừng)
vào `~/fiftyone` và `~/.cache/huggingface`, bao gồm 2 model embedding không liên quan
(`BAAI/bge-m3`, `sentence-transformers/all-MiniLM-L6-v2`) để dựng lại "brain runs" (index
similarity/visualization) đã lưu sẵn — không liên quan gì đến việc benchmark detection.
`max_samples` không giới hạn được lượng tải xuống đĩa. Vi phạm ràng buộc "không tải cả bộ
dữ liệu, chỉ stream/lấy 1 phần" → **không dùng cách này**.

## Cấu trúc repo thật (qua `huggingface_hub.HfApi().dataset_info(...)`)

```
.gitattributes
README.md
brain/radio_viz.json      (195 KB  — FiftyOne brain artifact, không dùng)
data/test_*.jpg           (2936 file ảnh)
fiftyone.yml               (102 B)
metadata.json              (11 KB)
samples.json                (~7.7 GB — toàn bộ nhãn, 1 file duy nhất)
sku110k.gif                 (41.7 MB)
```

`samples.json` là 1 file JSON `{"samples": [ {...}, {...}, ... ]}`, mỗi phần tử ứng với 1
ảnh. Cấu trúc 1 phần tử (lấy qua HTTP Range request, chỉ ~2KB đầu):

```json
{
  "filepath": "data/test_0.jpg",
  "ground_truth": {
    "_cls": "Detections",
    "detections": [
      {
        "_cls": "Detection",
        "label": "object",
        "bounding_box": [0.049, 0.774, 0.043, 0.073]
      }
    ]
  }
}
```

**Field chứa box ground-truth:** `sample["ground_truth"]["detections"]`, mỗi phần tử có
`bounding_box` = `[x, y, w, h]` **tương đối theo kích thước ảnh (0-1)**, gốc tọa độ ở
góc trên-trái. `label` luôn là `"object"` — SKU-110K không phân loại sản phẩm, chỉ khoanh
vùng ("class-agnostic"), đúng với mục đích chỉ dùng cho detection của dự án này.

## Cách lấy dữ liệu đã chọn: stream `samples.json` bằng `ijson`, chỉ tải đúng ảnh cần

Endpoint HF hỗ trợ Range request và `samples.json` là 1 mảng JSON, nên
`requests.get(url, stream=True)` + `ijson.items(resp.raw, 'samples.item')` đọc được N
bản ghi đầu rồi dừng (đóng kết nối) mà không tải hết 7.7GB. Đã kiểm chứng: lấy 5 sample
đầu mất ~13s, không tải file đầy đủ. Với mỗi `filepath` trong N sample đó,
`huggingface_hub.hf_hub_download(repo_id=..., repo_type='dataset', filename=sample['filepath'])`
chỉ tải đúng 1 ảnh đó (vài MB, ảnh gốc ~2448x3264). Cách này tránh được cả 2 vấn đề trên
(`datasets` không có nhãn, `fiftyone` tải không kiểm soát), giữ dung lượng tải tỉ lệ
thuận với `n`. `data.py` được viết theo đúng cách này.
