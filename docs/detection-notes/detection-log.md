# Nhật ký Detection (Phase 1)

**Trạng thái hiện tại:** checkpoint đang dùng là `runs/train_1a/n_2000/weights/best.pt` (YOLOv8 nano, train trên 2000 ảnh) — **precision=0.758, recall=0.818**, đo trên bộ eval cố định 50 ảnh (`Voxel51/sku110k_test`, IoU=0.5) qua `src.detection.train.evaluate`. Đạt
ngưỡng recall ≥ 0.6 đã quyết định ban đầu.

## 17/7/2026 — Benchmark model có sẵn (1b, 1c) — KHÔNG đạt

Thử 2 hướng không cần tự train trước khi quyết định fine-tune riêng:

| Model | Precision | Recall | Thời gian/ảnh | Đạt ngưỡng (recall ≥ 0.45)? |
|---|---|---|---|---|
| 1b — `foduucom/product-detection-in-shelf-yolov8` | 0.723 | 0.174 | 0.15s | KHÔNG ĐẠT |
| 1c — `IDEA-Research/grounding-dino-tiny` (zero-shot) | 0.718 | 0.093 | 2.34s | KHÔNG ĐẠT |

Cả 2 đều fail nặng ở recall (bỏ sót phần lớn sản phẩm trên kệ dày đặc SKU-110K, trung bình ~121-150 vật thể/ảnh) dù precision không tệ (~0.72) — nghĩa là khi model có đoán ra box thì thường đúng, nhưng đoán ra quá ít box. Đã kiểm tra trực quan (so ground-truth vs box dự đoán) xác nhận đây không phải lỗi code, mà do model được train trên ảnh kệ hàng thưa hơn nhiều so với SKU-110K.

**Quyết định:** quay lại kế hoạch gốc — tự fine-tune YOLO nano trên SKU-110K.

## 17/7/2026 — Fine-tune YOLO nano (800 ảnh, 10 epoch) — ĐẠT

Train 800 ảnh / 10 epoch (giảm từ đề xuất ban đầu 8219 ảnh / 30 epoch — xem phần "Quyết định quy mô train" bên dưới), eval trên đúng bộ 50 ảnh dùng cho 1b/1c.

| Model | Precision | Recall | Đạt ngưỡng (recall ≥ 0.6)? |
|---|---|---|---|
| 1a (fine-tune lần này) | 0.745 | 0.782 | ĐẠT |
| 1b (đối chiếu) | 0.723 | 0.174 | KHÔNG ĐẠT |
| 1c (đối chiếu) | 0.718 | 0.093 | KHÔNG ĐẠT |

**Quyết định quy mô train:** 1 tiến trình đầy đủ cần ~24h. Chạy quy mô nhỏ hơn (800/10 epoch) chỉ mất 39 phút.

**Thử cải thiện thêm (không dùng):** thử bật lại mosaic augmentation (`--close-mosaic 5`) với 1500 ảnh/15 epoch — bị kill giữa epoch 1 vì tốc độ mỗi batch tăng dần từ ~3s lên ~34s/it, kèm cảnh báo chia-cho-0/tràn số trong code augment. 

* **Nguyên nhân:** máy 16GB RAM dùng chunggiữa CPU/GPU trên chip Apple Silicon — mosaic ghép 4 ảnh SKU-110K (vốn đã rất dày đặc) vào 1 batch, đẩy bộ nhớ dùng gần chạm mức 16GB, gây swap.

*Phát hiện giới hạn "16GB RAM là bottleneck" của máy*

**Phase 1 (Detection) coi như hoàn tất tại đây** theo tiêu chí ban đầu.

## 20/7/2026 — Checkpoint bị mất, train lại — kết quả khớp y hệt

Khi bắt đầu implementation plan cho ShelfSense MVP, phát hiện file checkpoint `best.pt` không còn tồn tại trên máy. Train lại đúng cấu hình cũ (800/10 epoch nano).

**Kết quả khớp chính xác với lần đầu:** 
- precision=0.745 ; recall=0.782 ; tp=5513 ; fp=1891 ; fn=1537 : xác nhận train lại đúng model cũ.


## 20/7/2026 — Thử cải thiện: tăng ảnh train + đổi model

**Thử 1 — YOLOv8s (small), 2000 ảnh, 15 epoch — BỎ, không khả thi:** tăng đồng thời cả dữ liệu (800→2000) và model (nano→small). Tốc độ mỗi batch dao động cực mạnh (3.7s đến 60s/it) ngay từ epoch 1. Bộ nhớ dùng mỗi batch lên tới 15-17G. **Lặp đúng mẫu lỗi swap RAM đã gặp ngày 17/7 với mosaic**, guyên nhân kích hoạt là model to hơn thay vì mosaic. Ước tính 15 epoch sẽ mất 15-20+ tiếng. Dừng thử nghiệm.

**Thử 2 — YOLOv8n (nano), 2000 ảnh, 10 epoch — ÁP DỤNG:** giữ nguyên kiến trúc nano đã validate, chỉ tăng dữ liệu train. Chạy mượt, không nghẽn bộ nhớ, mất ~57 phút.

| Metric | Baseline (800 ảnh, nano) | Lần này (2000 ảnh, nano) | Thay đổi |
|---|---|---|---|
| Precision | 0.745 | 0.758 | +0.013 |
| Recall | 0.782 | **0.818** | **+0.036** |
| tp/fp/fn | 5513/1891/1537 | 5765/1837/1285 | tp tăng, fp và fn đều giảm |

Cả precision và recall đều tăng, không đánh đổi — chỉ cần thêm dữ liệu, không cần model lớn hơn. Recall vượt mốc 0.8.

**Lưu ý về số liệu:** số liệu ultralytics tự in ra lúc train (mAP50=0.835, precision=0.868, recall=0.778) đo trên bộ validation nội bộ khác (100 ảnh từ `validation` split), **không so sánh trực tiếp được** với bảng trên — bảng trên dùng đúng `evaluate.py` trên đúng bộ 50 ảnh cố định, cùng phương pháp với baseline.

**Quyết định cuối cùng:** dùng `runs/train_1a/n_2000/weights/best.pt` làm checkpoint chính thức cho pipeline (`src/pipeline/scan.py` nhận `detect_fn` qua injection, không hard-code đường dẫn checkpoint, nên đổi checkpoint không cần sửa code).

**Cải tiến kèm theo:** `src/detection/train/data.py` được sửa để bỏ qua tải lại ảnh đã có sẵn trên đĩa — các lần thử nghiệm tiếp theo với cùng `n_train`/`n_val` sẽ không tốn lại ~20-30 phút tải mạng.

## 04/08/2026 — Backlog: `cluster_rows` chain theo y-center, không theo row average — CHƯA FIX

Trong lúc audit checkpoint bug (`full` → `n_2000`, xem phần đầu file) và recalibrate lại
`ROW_CLUSTER_TOLERANCE_RATIO`/`Y_GAP_TOLERANCE_RATIO` trong `src/pipeline/scan.py`, xác nhận
lại 1 nghi vấn đã gặp nhiều lần nhưng chưa bao giờ được ghi thành issue riêng — 3 case cụ thể:

1. **Hảo Hảo crop (test1, đầu phiên brainstorm 04/08)** — test qua UI (crop tay qua
   `CropStep.jsx`) cho kết quả tệ hẳn so với script raw: 1 box bao trọn 2 hộp Hảo Hảo đỏ cạnh
   nhau đáng lẽ phải tách riêng (xem `docs/superpowers/specs/2026-08-04-adaptive-box-tolerance-design.md`
   mục 1). `filter_anomalous_boxes` (dùng chung `cluster_rows`) là nghi phạm.
2. **Yakult test3 cũ (checkpoint `full`)** — `row_cluster_tolerance` vượt 21.0-21.5px làm
   `cluster_rows` gộp gần hết 1 hàng kệ Yakult thành 1 nhóm, tạo gap ảo trải gần hết hàng (lý
   do ban đầu khiến `ROW_CLUSTER_TOLERANCE_RATIO` phải giữ safety margin chặt — xem lịch sử
   comment cũ trong `src/pipeline/scan.py` trước lần sửa hôm nay).
3. **2 gap test3 hôm nay (checkpoint `n_2000`, sau khi recalibrate)** — trace bằng
   `scripts/debug_stage_trace.py` cho cả 2 vùng gap: box bị flag NEEDS REVIEW đều là raw YOLO
   detection nguyên vẹn (IoU=1.000 với raw), không phải do `merge_adjacent_fragments` tạo ra —
   đều là chai cao bất thường (h≈727-793px so với median ảnh ~520px) nằm ở ranh giới 2 hàng.

**Root cause (đã đọc code xác nhận, không chỉ suy đoán):** `src/pipeline/row_clustering.py::cluster_rows`
so sánh box mới với y-center của **box cuối cùng vừa được thêm vào hàng** (`rows[-1][-1]`),
không phải với y-center trung bình của cả hàng:

```python
if rows and box_y_center(box) - box_y_center(rows[-1][-1]) <= tolerance:
    rows[-1].append(box)
```

Đây là hiệu ứng "chaining" kinh điển (giống single-linkage clustering): 1 hàng có thể trôi xa
tuỳ ý so với điểm bắt đầu, miễn mỗi box kế tiếp nằm trong `tolerance` so với box *ngay trước
nó* — không so với cả hàng. Một chuỗi box (vd. chai cao bắc cầu giữa 2 hàng kệ thật) có thể lần
lượt thoả điều kiện tolerance từng cặp một, trong khi cả hàng gộp lại đã trải rộng hơn 1 hàng
kệ vật lý thật nhiều.

**Trạng thái: CHƯA FIX.** Cố tình không gộp vào lần recalibrate tolerance hôm nay — đây là lỗi
thuật toán (chain theo điểm liền kề thay vì trung bình/centroid cả cụm), không phải lỗi chọn
sai giá trị tolerance, nên sửa tolerance không giải quyết được gốc rễ. Cần brainstorm riêng
hướng sửa (vd. so với y-center trung bình của cả hàng thay vì box cuối, hoặc đổi sang thuật
toán clustering khác) trước khi động vào `cluster_rows`, vì hàm này được `gap_detection.py`,
`box_filter.py` (2 hàm) dùng chung — sửa sai có thể ảnh hưởng dây chuyền. Ghi lại ở đây theo
đúng kỷ luật "đo trước khi quyết, ghi lại trước khi quên" đã áp dụng xuyên suốt file này, để
không bị quên giữa các phiên làm việc.

## Bài học rút ra cho các lần sau

**16GB RAM (unified memory) là giới hạn cứng của máy, xuất hiện lặp lại 2 lần** (mosaic + nhiều ảnh ngày 17/7, model lớn hơn ngày 20/7) — dấu hiệu nhận biết: tốc độ mỗi batch dao động mạnh/tăng dần bất thường (không phải chậm đều), kèm cột bộ nhớ báo gần 16G. Khi gặp dấu hiệu này, dừng ngay, không đợi hết epoch — nhiều khả năng không tự hết mà crash máy.
