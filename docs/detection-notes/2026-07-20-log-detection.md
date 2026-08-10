# Nhật ký Detection (Phase 1)

> **Superseded 2026-08-10:** production checkpoint moved from YOLOv8n (`n_2000`) to
> YOLO26n — see `docs/superpowers/plans/2026-08-10-yolo26n-migration.md`. The
> checkpoint path/metrics below are historical (YOLOv8n-era), left unedited.

**Trạng thái hiện tại:** checkpoint đang dùng là `runs/train_1a/n_2000/weights/best.pt`
(YOLOv8 nano, train trên 2000 ảnh) — **precision=0.758, recall=0.818**, đo trên bộ eval
cố định 50 ảnh (`Voxel51/sku110k_test`, IoU=0.5) qua `src.detection.train.evaluate`. Đạt
ngưỡng recall ≥ 0.6 đã quyết định ban đầu.

File này gộp lại toàn bộ quá trình quyết định của Phase 1 theo mốc thời gian, thay cho 4
file riêng lẻ trước đó (đã xóa sau khi gộp xong).

## 17/7/2026 — Benchmark model có sẵn (1b, 1c) — KHÔNG đạt

Thử 2 hướng không cần tự train trước khi quyết định fine-tune riêng:

| Model | Precision | Recall | Thời gian/ảnh | Đạt ngưỡng (recall ≥ 0.45)? |
|---|---|---|---|---|
| 1b — `foduucom/product-detection-in-shelf-yolov8` | 0.723 | 0.174 | 0.15s | KHÔNG ĐẠT |
| 1c — `IDEA-Research/grounding-dino-tiny` (zero-shot) | 0.718 | 0.093 | 2.34s | KHÔNG ĐẠT |

Cả 2 đều fail nặng ở recall (bỏ sót phần lớn sản phẩm trên kệ dày đặc SKU-110K, trung
bình ~121-150 vật thể/ảnh) dù precision không tệ (~0.72) — nghĩa là khi model có đoán ra
box thì thường đúng, nhưng đoán ra quá ít box. Đã kiểm tra trực quan (so ground-truth vs
box dự đoán) xác nhận đây không phải lỗi code, mà do model được train trên ảnh kệ hàng
thưa hơn nhiều so với SKU-110K.

**Quyết định:** quay lại kế hoạch gốc — tự fine-tune YOLO nano trên SKU-110K.

## 17/7/2026 — Fine-tune YOLO nano (800 ảnh, 10 epoch) — ĐẠT

Train 800 ảnh / 10 epoch (giảm từ đề xuất ban đầu 8219 ảnh / 30 epoch — xem phần "Quyết
định quy mô train" bên dưới), eval trên đúng bộ 50 ảnh dùng cho 1b/1c.

| Model | Precision | Recall | Đạt ngưỡng (recall ≥ 0.6)? |
|---|---|---|---|
| 1a (fine-tune lần này) | 0.745 | 0.782 | ĐẠT |
| 1b (đối chiếu) | 0.723 | 0.174 | KHÔNG ĐẠT |
| 1c (đối chiếu) | 0.718 | 0.093 | KHÔNG ĐẠT |

**Quyết định quy mô train:** ước tính ban đầu cho 8219 ảnh/30 epoch bị nhiễu do lỗi thao
tác (chạy trùng 1 tiến trình `resume=True` đè lên tiến trình gốc + máy bị sleep giữa
chừng), khiến ước tính lên tới 65-195 tiếng. Đo lại sạch từ 1 tiến trình duy nhất cho ra
~24 tiếng cho quy mô đầy đủ — vẫn vượt ngân sách ~4 tiếng đã đặt ra. Theo hướng dẫn của
người dùng, chạy quy mô rút gọn 800/10 epoch — thực tế chỉ mất 39 phút, đạt ngưỡng thoải
mái.

**Thử cải thiện thêm (không dùng):** thử bật lại mosaic augmentation (`--close-mosaic 5`)
với 1500 ảnh/15 epoch — bị kill giữa epoch 1 vì tốc độ mỗi batch tăng dần từ ~3s lên
~34s/it, kèm cảnh báo chia-cho-0/tràn số trong code augment. **Nguyên nhân: máy có 16GB
RAM dùng chung (unified memory) giữa CPU/GPU trên chip Apple Silicon — mosaic ghép 4 ảnh
SKU-110K (vốn đã rất dày đặc) vào 1 batch, đẩy bộ nhớ dùng gần chạm mức 16GB, gây swap.**
Không mất gì vì epoch 1 chưa từng hoàn thành. Không theo đuổi tiếp vì 1a đã đạt ngưỡng
thoải mái (0.782 vs 0.6).

*(Đây là lần đầu tiên phát hiện giới hạn "16GB RAM là nút thắt cổ chai" của máy — mẫu lỗi
này lặp lại ở thử nghiệm YOLOv8s ngày 20/7, xem bên dưới.)*

**Phase 1 (Detection) coi như hoàn tất tại đây** theo tiêu chí ban đầu.

## 20/7/2026 — Checkpoint bị mất, train lại — kết quả khớp y hệt

Khi bắt đầu implementation plan cho ShelfSense MVP, phát hiện file checkpoint
`best.pt` không còn tồn tại trên máy (chưa từng được lưu lại bền vững). Train lại đúng
cấu hình cũ (800/10 epoch nano).

**Sự cố môi trường:** lần chạy đầu tiên bị crash ngay vì venv sai —
`.venv-benchmark` (ultralytics 8.0.43) không tương thích MPS với bản torch mới hiện tại.
Nguyên nhân gốc: venv đúng cho training (`.venv-train`, ultralytics ≥8.3) cũng bị mất
khỏi máy, không chỉ riêng checkpoint. Tạo lại `.venv-train` (ultralytics 8.4.102), train
lại thành công.

**Kết quả khớp chính xác với lần đầu:** precision=0.745, recall=0.782, tp=5513 fp=1891
fn=1537 — xác nhận đây là train lại đúng model cũ, không phải model khác.

**Đọc 2 biểu đồ trông "đáng ngờ" lúc review kết quả:**
- Đường cong precision-confidence bị "rớt" mạnh ở vùng confidence 0.9-0.95 rồi bật lại —
  đây là nhiễu do mẫu quá ít ở vùng confidence cao (chỉ có vài box đạt confidence đó trên
  100 ảnh validation), không phải lỗi model. Điểm vận hành thật của pipeline
  (`conf=0.25`) nằm ở vùng ổn định của đường cong, khớp đúng với precision đo được.
- Confusion matrix có ô (Predicted=object, True=background) = 1.00 — đây là artifact
  toán học đặc trưng của confusion matrix cho bài toán detection: cột "background" không
  có ô true-negative nào để so sánh, nên tự động normalize ra 1.00 bất kể fp là 1891 hay
  1. Đối chiếu với số liệu thô (tp/fp/fn) trong `results_1a.json` xác nhận không có gì
  bất thường.

## 20/7/2026 — Thử cải thiện: tăng ảnh train + đổi model

**Thử 1 — YOLOv8s (small), 2000 ảnh, 15 epoch — BỎ, không khả thi:** tăng đồng thời cả dữ
liệu (800→2000) và model (nano→small). Tốc độ mỗi batch dao động cực mạnh (3.7s đến
60s/it) ngay từ epoch 1. Bộ nhớ dùng mỗi batch lên tới 15-17G, gần chạm trần 16GB —
**lặp lại đúng mẫu lỗi swap RAM đã gặp ngày 17/7 với mosaic**, chỉ khác nguyên nhân kích
hoạt (model to hơn thay vì mosaic). Ước tính 15 epoch sẽ mất 15-20+ tiếng. Dừng thử
nghiệm.

**Thử 2 — YOLOv8n (nano), 2000 ảnh, 10 epoch — ÁP DỤNG:** giữ nguyên kiến trúc nano đã
validate, chỉ tăng dữ liệu train. Chạy mượt, không nghẽn bộ nhớ, mất ~57 phút.

| Metric | Baseline (800 ảnh, nano) | Lần này (2000 ảnh, nano) | Thay đổi |
|---|---|---|---|
| Precision | 0.745 | 0.758 | +0.013 |
| Recall | 0.782 | **0.818** | **+0.036** |
| tp/fp/fn | 5513/1891/1537 | 5765/1837/1285 | tp tăng, fp và fn đều giảm |

Cả precision và recall đều tăng, không đánh đổi — chỉ cần thêm dữ liệu, không cần model
lớn hơn. Recall vượt mốc 0.8.

**Lưu ý về số liệu:** số liệu ultralytics tự in ra lúc train (mAP50=0.835, precision=0.868,
recall=0.778) đo trên bộ validation nội bộ khác (100 ảnh từ `validation` split), **không
so sánh trực tiếp được** với bảng trên — bảng trên dùng đúng `evaluate.py` trên đúng bộ 50
ảnh cố định, cùng phương pháp với baseline.

**Quyết định cuối cùng:** dùng `runs/train_1a/n_2000/weights/best.pt` làm checkpoint
chính thức cho pipeline (`src/pipeline/scan.py` nhận `detect_fn` qua injection, không
hard-code đường dẫn checkpoint, nên đổi checkpoint không cần sửa code).

**Cải tiến kèm theo:** `src/detection/train/data.py` được sửa để bỏ qua tải lại ảnh đã có
sẵn trên đĩa — các lần thử nghiệm tiếp theo với cùng `n_train`/`n_val` sẽ không tốn lại
~20-30 phút tải mạng.

## Bài học rút ra cho các lần sau

**16GB RAM (unified memory) là giới hạn cứng của máy, xuất hiện lặp lại 2 lần** (mosaic
+ nhiều ảnh ngày 17/7, model lớn hơn ngày 20/7) — dấu hiệu nhận biết: tốc độ mỗi batch
dao động mạnh/tăng dần bất thường (không phải chậm đều), kèm cột bộ nhớ báo gần 16G. Khi
gặp dấu hiệu này, dừng ngay, không đợi hết epoch — nhiều khả năng không tự hết mà chỉ tệ
hơn theo thời gian.
