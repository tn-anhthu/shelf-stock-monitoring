# Model Research Summary — EDA, Baseline Comparison, Evaluation (ShelfSense Detection & Classification)

> **Superseded 2026-08-10:** production checkpoint moved from YOLOv8n (`n_2000`) to
> YOLO26n — see `docs/superpowers/plans/2026-08-10-yolo26n-migration.md`. The
> model/metrics discussed below are historical (YOLOv8n-era), left unedited.

**Mục đích file này:** ShelfSense không làm việc research/train model qua notebook — toàn bộ quá trình explore data, chọn baseline, đo đạc, và evaluate-trước-khi-merge được ghi trực tiếp thành log/spec `.md` theo từng quyết định, gắn liền với code thật (`src/`, `scripts/`) thay vì gói trong 1 file `.ipynb`. File này là bản tổng hợp — không lặp lại nội dung, chỉ tóm tắt + trỏ đúng vào nguồn gốc để dễ review theo đúng trình tự 1 notebook thường có: **data/EDA → baseline → iterate → error analysis → visualization/component research → thử nghiệm bị revert → trạng thái hiện tại.**

**Biểu đồ:** phần data/EDA, baseline, error analysis ở dưới giờ có bản visualize kèm theo — xem `docs/reports/eda-visualization.md` (5 chart: phân bố confidence score thật, accuracy-vs-threshold có caveat, baseline vs fine-tune, root-cause flagged-box, catalog composition — kèm 3 gap phát hiện thêm trong lúc vẽ).

---

## 1. Data & EDA (schema, không có sẵn EDA thống kê dạng biểu đồ)

- **Train set:** `harryrobert/SKU-110k-reformat` — 8219 ảnh train / 588 validation / 2936 test. Field: `{'image', 'image_id', 'width', 'height', 'objects': {'id', 'bbox' (x,y,w,h) tuyệt đối kiểu COCO, 'category', 'area'}}`.
  → `docs/detection-notes/schema-sku110k-train.md`
- **Eval set (benchmark cố định, không dùng để train):** `Voxel51/sku110k_test` — ground truth ở `sample["ground_truth"]["detections"][].bounding_box`, toạ độ **tương đối** (khác hệ với train set — không dùng chung hàm xử lý, đã ghi rõ trong doc gốc).
  → `docs/detection-notes/schema-sku110k.md`
- Catalog thật (144 SKU, phân bố nhóm hàng + giá) — xem chart trong `docs/reports/eda-visualization.md` mục 5.

## 2. Baseline comparison (trước khi quyết định fine-tune riêng)

Đo 2 hướng "dùng model có sẵn, không cần tự train" trước, làm baseline để so sánh:

| Model | Precision | Recall | Thời gian/ảnh | Đạt ngưỡng (recall ≥ 0.45)? |
|---|---|---|---|---|
| 1b — `foduucom/product-detection-in-shelf-yolov8` | 0.723 | 0.174 | 0.15s | KHÔNG ĐẠT |
| 1c — `IDEA-Research/grounding-dino-tiny` (zero-shot) | 0.718 | 0.093 | 2.34s | KHÔNG ĐẠT |

Cả 2 fail nặng ở recall trên kệ dày đặc SKU-110K (~121-150 vật thể/ảnh) → quyết định tự fine-tune YOLOv8 nano.

→ Toàn bộ bảng, phương pháp đo, và lý do fail: `docs/detection-notes/detection-log.md`
→ Chart: `docs/reports/eda-visualization.md` mục 3

## 3. Fine-tune & iteration (so với baseline ở mục 2)

| Model | Precision | Recall | Đạt ngưỡng (recall ≥ 0.6)? |
|---|---|---|---|
| 1a — fine-tune (800 ảnh/10 epoch) | 0.745 | 0.782 | ĐẠT |
| 1b — baseline đối chiếu | 0.723 | 0.174 | KHÔNG ĐẠT |
| 1c — baseline đối chiếu | 0.718 | 0.093 | KHÔNG ĐẠT |

Sau đó tăng quy mô train (800→2000 ảnh, cùng kiến trúc nano vì thử YOLOv8s bị nghẽn RAM 16GB):

| Metric | Baseline (800 ảnh, nano) | 2000 ảnh, nano | Thay đổi |
|---|---|---|---|
| Precision | 0.745 | 0.758 | +0.013 |
| Recall | 0.782 | **0.818** | **+0.036** |

Checkpoint chính thức hiện dùng trong production: `runs/train_1a/n_2000/weights/best.pt` (precision=0.758, recall=0.818, đo trên đúng bộ eval 50 ảnh cố định).

→ Toàn bộ log iteration (kể cả 2 lần thử KHÔNG áp dụng — mosaic augmentation và YOLOv8s, đều nghẽn RAM 16GB): `docs/detection-notes/detection-log.md`

## 4. Post-detection error analysis (đo lỗi thật trên ảnh test, không đoán)

Quét 297 box (308 gốc → 297 sau merge/filter) trên 5 ảnh test thật, phân loại nguyên nhân 25 box bị hệ thống tự flag "NEEDS REVIEW":

| Loại lỗi | Tỷ lệ | Hướng xử lý |
|---|---|---|
| Box gộp nhầm ≥2 SKU khác nhau (case Binggrae) | 1/297 (~0.34%) | Hiếm — không train lại, giữ nguyên `filter_contained_boxes` |
| Box gộp nhầm 2 đơn vị cùng 1 SKU | 2/297 | Theo dõi thêm |
| Duplicate detection cùng 1 SKU (chủ yếu bao bì bóng/phản chiếu) | 19/297 (~76% số box bị flag) | Ưu tiên cao nhất — đã xử lý bằng confidence-based dedup (mục 6) |
| False-positive thật (crop mờ, box dính tay người chụp) | 2/297 | Cần filter heuristic riêng, chưa làm |

(4 nhóm cộng = 24/297 — lệch 1 box so với tổng "25 flagged" ghi trong doc gốc, xem lưu ý ở `docs/reports/eda-visualization.md` mục 4.)

→ Bảng gốc + phương pháp đo: `docs/reports/week-02/2026-07-30.md`
→ Đo sâu case 0.34% (đo lại độc lập, xác nhận đúng con số): `docs/log-figures/2026-07-28-binggrae-multi-sku-trigger.md`
→ Điều tra sâu case Vinamilk 1L split-box (root cause raw YOLO chẻ dọc hộp, không phải merge logic sai): ghi trong `docs/reports/week-02/2026-07-30.md`
→ Chart: `docs/reports/eda-visualization.md` mục 4

## 5. Component-level research & benchmarks (giai đoạn chọn/tune từng thành phần)

- `docs/log-figures/2026-07-28-llm-verify-same-object.md` — implement + chạy thật LLM escalation cho case IoU-duplicate.
- `docs/log-figures/2026-07-28-nms-iou-duplicate-detection.md` — tune ngưỡng IoU của Non-Max Suppression cho case nhiều box trùng cao trên 1 vật.
- `docs/log-figures/2026-07-28-roi-crop-component-selection.md` — thử chọn lại component segmentation (center-bias + sharpness) cho ROI-crop.
- `docs/log-figures/2026-07-28-roi-crop-threshold-benchmark.md` — đo threshold ROI-crop trên 5 ảnh demo gốc, so với ground truth crop tay (template matching).
- `docs/log-figures/2026-07-28-binggrae-multi-sku-trigger.md` — đo trigger cho case đa-SKU-trong-1-box (chỉ đo, chưa implement — tần suất quá thấp).

## 6. Fix đã ship (so với baseline hành vi cũ, có test regression)

- **Fragment merge + anomalous box filter + gap-detection recalibration** (tuần 1) — 92/92 test pass, xác nhận bằng ảnh render thật. → `docs/reports/week-01/2026-07-21.md`
- **Confidence-based same-item dedup** — dùng cosine score đã qua LLM verify để chọn giữ box đúng khi 1 vật lý bị detect ra 2 box, thay vì đoán theo hình học (đã cân nhắc và loại 2 hướng khác trước khi chọn). → `docs/superpowers/specs/2026-08-05-same-item-dedup-design.md`
- **Adaptive tolerance theo box size** thay vì absolute pixel — tránh lệch khi ảnh bị crop đổi resolution. → `docs/superpowers/specs/2026-08-04-adaptive-box-tolerance-design.md`

## 7. Thử nghiệm bị REVERT sau khi re-verify (bằng chứng "đo trước khi quyết", không phải ship-and-forget)

- **ROI-crop tự động bằng CLIPSeg zero-shot segmentation** — validate ban đầu "4/5 ảnh tốt", nhưng test lại phát hiện segmentation lẹm vào sản phẩm quá nhiều → xoá hẳn code (`src/pipeline/roi_crop.py`), quay về crop tay trong UI. → `docs/superpowers/specs/2026-08-04-remove-roi-crop-design.md`
- **`cluster_rows` chaining fix** — implement dựa trên 3 case nghi ngờ có lý luận kỹ thuật đúng, nhưng khi chạy lại trên hệ thống thật (checkpoint + tolerance hiện tại) thì **cả 3 case đều không tái hiện được**, và fix mới gây hỏng thêm ít nhất 3 hàng kệ thật vốn đã đúng → revert, giữ lại test coverage mới làm regression guard. → `docs/detection-notes/detection-log.md` (mục 04/08 và đính chính 06/08), báo cáo đầy đủ ở `docs/detection-notes/2026-08-06-cluster-rows-diagnostic-report.md` và `docs/detection-notes/2026-08-06-cluster-rows-old-algorithm-reverification.md`.

## 8. Trạng thái hiện tại & vấn đề chưa xử lý

- Checkpoint production: `runs/train_1a/n_2000/weights/best.pt` — precision 0.758 / recall 0.818.
- Chưa xử lý: YOLO detect tràn ngoài kệ chính (5/5 ảnh test), Gemini API lỗi 503 không có retry/backoff, Node API `aggregateQuantities` chưa đọc cờ `excluded_from_count` (bảng số lượng FE đếm dư dù ảnh đã flag đúng).
- **Mới phát hiện khi làm EDA (mục biểu đồ):** 297 box hiện hành (test1-5 catalog_v2) không có ground-truth `correct` → không tính được accuracy classification thật cho bộ eval đang dùng; `CONFIDENCE_THRESHOLD=0.5` gần như không bao giờ kích hoạt trên phân bố score thật (chỉ 1/297 dưới ngưỡng).
→ Chi tiết + checklist tuần: `docs/reports/week-03/2026-08-06.md`
→ Chi tiết phát hiện EDA: `docs/reports/eda-visualization.md`

## Đọc theo timeline (nếu cần narrative đầy đủ thay vì tổng hợp)

`docs/reports/week-01/2026-07-21.md` → `docs/reports/week-02/2026-07-30.md` → `docs/reports/week-03/2026-08-06.md`
