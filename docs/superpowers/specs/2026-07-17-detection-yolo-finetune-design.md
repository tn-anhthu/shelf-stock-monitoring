# Design: Detection — Fine-tune YOLO nano trên SKU-110K (Phase 1a)

**Ngày:** 2026-07-17
**Trạng thái:** Đã duyệt bởi Anh Thư — sẵn sàng chuyển sang writing-plans
**Phạm vi:** Phần còn lại của Phase 1 (Detection), sau khi sprint benchmark trước quyết định fallback về 1a.

## Bối cảnh

Sprint benchmark trước (`docs/superpowers/specs/2026-07-17-detection-benchmark-design.md`, kết quả tại
`docs/detection-notes/2026-07-17-detection-benchmark-results.md`) đã chạy 1b (checkpoint community) và
1c (Grounding DINO zero-shot) trên 50 ảnh SKU-110K thật. Cả hai đều **fail** ngưỡng recall≥0.45:

- 1b: precision=0.723, recall=0.174
- 1c: precision=0.718, recall=0.093

Cả hai có precision khá cao nhưng bỏ sót phần lớn sản phẩm trên các ảnh kệ hàng dày đặc — đúng như quy
tắc quyết định trong spec trước đã dự liệu, giờ quay lại kế hoạch gốc: **tự fine-tune YOLO nano trên
SKU-110K (1a)**.

## Mục tiêu của sprint này

Train một model YOLO nano riêng cho bài toán này (thay vì dùng checkpoint/zero-shot có sẵn), rồi thi lại
đúng bộ 50 ảnh đã dùng benchmark 1b/1c để có số liệu so sánh trực tiếp, từ đó quyết định model này có đủ
tốt để dùng cho Phase 1 hay không.

## Ngoài phạm vi (out of scope) của sprint này

- Classification, Depth multiplier UI, Pricing aggregation — vẫn chờ Phase 1 xong.
- Ảnh kệ hàng tự chụp Việt Nam — vẫn dùng SKU-110K (nước ngoài) cho sprint này; ảnh thật để sprint sau.
- Auto-labeling bằng Autodistill — SKU-110K đã có label sẵn, không cần.
- Train xong nhiều vòng để tối ưu tối đa (hyperparameter tuning sâu) — mục tiêu là đạt ngưỡng đủ dùng,
  không phải SOTA.

## Nguồn dữ liệu train

Không cần thu thập thêm ảnh. Repo `harryrobert/SKU-110k-reformat` trên Hugging Face (đã verify
2026-07-17 qua `datasets.get_dataset_split_names`/`load_dataset`) có đúng 3 split khớp số liệu SKU-110K
chính thức — `train` (8219 ảnh), `validation` (588 ảnh), `test` (2936 ảnh) — và expose label trực tiếp
qua `datasets` thường (không cần trick streaming/`ijson` như dataset dùng ở sprint trước):

```python
features: {
  'image': Image, 'image_id': int64, 'width': int32, 'height': int32,
  'objects': {'id': [int64], 'bbox': [[float32; 4]], 'category': [int64], 'area': [float32]}
}
```

`objects.bbox` = `[x, y, w, h]` pixel tuyệt đối (COCO-style, top-left origin), `category` luôn cùng 1
giá trị (class-agnostic "object"). Dùng `train` split để train, `validation` split cho việc theo dõi
loss trong lúc train (không phải bộ eval cuối). **Bộ eval cuối (để so với 1b/1c) vẫn là đúng 50 ảnh đầu
của `Voxel51/sku110k_test`** đã dùng ở sprint trước, qua loader đã có sẵn
(`src/detection/benchmark/data.py`) — không tạo loader eval mới.

## Setup

- Package mới: `src/detection/train/`, tách biệt khỏi `src/detection/benchmark/`.
- Venv mới: `.venv-train`, dùng `ultralytics` bản mới nhất (không ghim bản cũ 8.0.43 như benchmark —
  bản đó chỉ cần cho tương thích checkpoint 1b, không liên quan tới việc train).
- `device='mps'` trên M4 cho pilot; quyết định máy cho lần train thật dựa trên tốc độ đo được ở pilot
  (xem "Quy trình" bên dưới).

## Quy trình

1. **Data pipeline** (`src/detection/train/data.py`): stream N ảnh từ `harryrobert/SKU-110k-reformat`
   (train + validation split), convert `objects.bbox` (COCO `[x,y,w,h]` pixel) sang format YOLO
   (`.txt`: `class x_center y_center width height`, normalized 0-1, class luôn là `0`), ghi ảnh + label
   ra đĩa local theo cấu trúc `ultralytics` yêu cầu (`images/train`, `images/val`, `labels/train`,
   `labels/val`), sinh file `data.yaml` (`nc: 1, names: ['object']`).
2. **Pilot** (`src/detection/train/train.py`, chạy với N nhỏ ~300-500 ảnh train + một ít ảnh validation,
   5-10 epoch): xác nhận toàn bộ pipeline chạy được trên M4 `mps` — data load đúng, training loop không
   lỗi, model lưu ra được — không kỳ vọng recall tốt ở bước này, chỉ để bắt lỗi sớm (kiểu lỗi từng gặp:
   op không hỗ trợ MPS, sai format bbox) trước khi tốn nhiều giờ train thật.
3. **Quyết định nơi train thật:** từ thời gian pilot đo được (giây/ảnh/epoch), ước lượng thời gian nếu
   scale lên số ảnh/epoch cho lần train thật. Nếu ước lượng trong khoảng vài giờ → tiếp tục trên M4. Nếu
   quá lâu → chuyển sang Colab (cùng code `src/detection/train/`, chỉ đổi `device` và cách đưa data vào
   môi trường Colab — không thiết kế lại pipeline).
4. **Train thật:** chạy `train.py` với số ảnh/epoch đã quyết định ở bước 3.
5. **Eval** (`src/detection/train/evaluate.py`): load `best.pt` vừa train, viết wrapper
   `detect_1a(model, image) -> List[Box]` theo đúng interface đã dùng cho 1b/1c
   (`src/detection/benchmark/run_checkpoint_1b.py` là ví dụ), chạy qua đúng 50 ảnh eval cũ, tính
   precision/recall bằng `src/detection/benchmark/metrics.py` (tái sử dụng, không viết lại).
6. **Quyết định:** recall ≥ 0.6 trên 50 ảnh đó → chốt dùng 1a cho Phase 1, viết Phase 1 xong, chuyển
   sang spec Phase 2 (Classification). Recall < 0.6 → ghi lại số liệu thật, bàn hướng tiếp (train thêm
   ảnh/epoch, hay xem xét lại toàn bộ hướng dense-shelf).

## Ngưỡng quyết định (pass/fail)

- **Recall ≥ 0.6** trên đúng 50 ảnh test đã dùng cho 1b/1c → đạt, dùng model này cho Phase 1.
- Recall < 0.6 → không tự động fallback tiếp (không còn phương án "1d") — dừng lại báo cáo số liệu và
  bàn hướng tiếp theo với người quyết định, vì đây đã là phương án cuối trong 3 phương án (1a/1b/1c) đã
  cân nhắc.

## Rủi ro đã biết

- Training dùng nhiều loại phép tính hơn hẳn inference — rủi ro gặp thêm op không hỗ trợ trên MPS (đã
  từng gặp với `aten::_cummax_helper` ở sprint benchmark, dù đó là lúc chạy 1c chứ không phải training).
  Pilot (bước 2) chính là để bắt rủi ro này sớm, với chi phí thời gian thấp.
- Thời gian train thật trên M4 cho 8219 ảnh SKU-110K chưa được đo — có thể chênh lệch lớn so với ước
  lượng từ pilot nếu training không scale tuyến tính theo số ảnh/epoch (ví dụ do overhead tải data hoặc
  nhiệt độ máy giảm hiệu năng khi chạy lâu). Ước lượng ở bước 3 nên coi là cận dưới, không phải con số
  chắc chắn.
- `harryrobert/SKU-110k-reformat`'s `test` split (2936 ảnh) trùng số lượng với `Voxel51/sku110k_test`
  nhưng **chưa xác nhận là cùng đúng những ảnh** — không dùng split test của repo này cho eval, tránh
  data leakage nếu train vô tình đụng ảnh test; chỉ dùng `train`/`validation` của repo này.

## Kết quả bàn giao (deliverables)

- Package train tái sử dụng được (`src/detection/train/`), venv riêng (`.venv-train`).
- Model đã train (`best.pt`) + log training.
- Số liệu precision/recall/thời gian inference của 1a trên đúng 50 ảnh eval cũ, so sánh trực tiếp với
  1b/1c trong cùng 1 bảng.
- Quyết định bằng văn bản: 1a có đạt ngưỡng recall≥0.6 hay không, và bước tiếp theo cho Phase 1.

## Testing

- Unit test cho hàm convert bbox COCO → YOLO (`.txt` normalized) — dùng số giả lập biết trước đáp số,
  không cần mạng, theo đúng pattern đã dùng cho `parse_fiftyone_detections` ở sprint trước.
- Pilot (bước 2 ở Quy trình) đóng vai trò smoke test tích hợp cho toàn bộ pipeline train.
- Eval (bước 5) tái dùng `metrics.py` đã có unit test từ sprint trước — không viết lại logic tính
  precision/recall.

## Bước tiếp theo sau spec này

Nếu 1a đạt recall≥0.6: Phase 1 (Detection) coi như xong, viết spec Phase 2 (Classification — CLIP/SigLIP2
+ catalog). Nếu không đạt: viết báo cáo số liệu, bàn với người quyết định về hướng tiếp theo trước khi
viết spec mới (không tự ý mở rộng scope thêm phương án khác mà không có quyết định rõ ràng).
