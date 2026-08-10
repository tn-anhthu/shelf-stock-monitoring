# Nhật ký Detection (Phase 1)

> **Superseded 2026-08-10:** production checkpoint moved from YOLOv8n (`n_2000`) to
> YOLO26n, see `docs/superpowers/plans/2026-08-10-yolo26n-migration.md` (gitignored,
> local-only; not available in a fresh clone). The checkpoint path/metrics below are
> historical (YOLOv8n-era), left unedited.
>
> **Current production checkpoint:** YOLO26n fine-tuned on the *full* SKU-110K train
> split (8219 images, 30 epochs, `patience=5`), expected locally at
> `sku110k_yolo26n_results/weights/best.pt`: this is what `ml-service/app.py`'s
> `WEIGHTS_PATH` points at. That directory is gitignored (like `runs/` was for the
> old checkpoint), so it isn't in the repo; obtain/reproduce it by re-running the
> training notebook `yolo26n-on-sku-110k.ipynb` (Kaggle GPU, `yolo26n.pt` base),
> that notebook is itself not yet committed to git as of this note.

**Trạng thái hiện tại:** checkpoint đang dùng là `runs/train_1a/n_2000/weights/best.pt` (YOLOv8 nano, train trên 2000 ảnh), **precision=0.758, recall=0.818**, đo trên bộ eval cố định 50 ảnh (`Voxel51/sku110k_test`, IoU=0.5) qua `src.detection.train.evaluate`. Đạt
ngưỡng recall ≥ 0.6 đã quyết định ban đầu.

## 17/7/2026: Benchmark model có sẵn (1b, 1c), KHÔNG đạt

Thử 2 hướng không cần tự train trước khi quyết định fine-tune riêng:

| Model | Precision | Recall | Thời gian/ảnh | Đạt ngưỡng (recall ≥ 0.45)? |
|---|---|---|---|---|
| 1b, `foduucom/product-detection-in-shelf-yolov8` | 0.723 | 0.174 | 0.15s | KHÔNG ĐẠT |
| 1c, `IDEA-Research/grounding-dino-tiny` (zero-shot) | 0.718 | 0.093 | 2.34s | KHÔNG ĐẠT |

Cả 2 đều fail nặng ở recall (bỏ sót phần lớn sản phẩm trên kệ dày đặc SKU-110K, trung bình ~121-150 vật thể/ảnh) dù precision không tệ (~0.72), nghĩa là khi model có đoán ra box thì thường đúng, nhưng đoán ra quá ít box. Đã kiểm tra trực quan (so ground-truth vs box dự đoán) xác nhận đây không phải lỗi code, mà do model được train trên ảnh kệ hàng thưa hơn nhiều so với SKU-110K.

**Quyết định:** quay lại kế hoạch gốc, tự fine-tune YOLO nano trên SKU-110K.

## 17/7/2026: Fine-tune YOLO nano (800 ảnh, 10 epoch), ĐẠT

Train 800 ảnh / 10 epoch (giảm từ đề xuất ban đầu 8219 ảnh / 30 epoch, xem phần "Quyết định quy mô train" bên dưới), eval trên đúng bộ 50 ảnh dùng cho 1b/1c.

| Model | Precision | Recall | Đạt ngưỡng (recall ≥ 0.6)? |
|---|---|---|---|
| 1a (fine-tune lần này) | 0.745 | 0.782 | ĐẠT |
| 1b (đối chiếu) | 0.723 | 0.174 | KHÔNG ĐẠT |
| 1c (đối chiếu) | 0.718 | 0.093 | KHÔNG ĐẠT |

**Quyết định quy mô train:** 1 tiến trình đầy đủ cần ~24h. Chạy quy mô nhỏ hơn (800/10 epoch) chỉ mất 39 phút.

**Thử cải thiện thêm (không dùng):** thử bật lại mosaic augmentation (`--close-mosaic 5`) với 1500 ảnh/15 epoch, bị kill giữa epoch 1 vì tốc độ mỗi batch tăng dần từ ~3s lên ~34s/it, kèm cảnh báo chia-cho-0/tràn số trong code augment. 

* **Nguyên nhân:** máy 16GB RAM dùng chung giữa CPU/GPU trên chip Apple Silicon, mosaic ghép 4 ảnh SKU-110K (vốn đã rất dày đặc) vào 1 batch, đẩy bộ nhớ dùng gần chạm mức 16GB, gây swap.

*Phát hiện giới hạn "16GB RAM là bottleneck" của máy*

**Phase 1 (Detection) coi như hoàn tất tại đây** theo tiêu chí ban đầu.

## 20/7/2026: Checkpoint bị mất, train lại, kết quả khớp y hệt

Khi bắt đầu implementation plan cho ShelfSense MVP, phát hiện file checkpoint `best.pt` không còn tồn tại trên máy. Train lại đúng cấu hình cũ (800/10 epoch nano).

**Kết quả khớp chính xác với lần đầu:** 
- precision=0.745 ; recall=0.782 ; tp=5513 ; fp=1891 ; fn=1537 : xác nhận train lại đúng model cũ.


## 20/7/2026: Thử cải thiện: tăng ảnh train + đổi model

**Thử 1, YOLOv8s (small), 2000 ảnh, 15 epoch, BỎ, không khả thi:** tăng đồng thời cả dữ liệu (800→2000) và model (nano→small). Tốc độ mỗi batch dao động cực mạnh (3.7s đến 60s/it) ngay từ epoch 1. Bộ nhớ dùng mỗi batch lên tới 15-17G. **Lặp đúng mẫu lỗi swap RAM đã gặp ngày 17/7 với mosaic**, nguyên nhân kích hoạt là model to hơn thay vì mosaic. Ước tính 15 epoch sẽ mất 15-20+ tiếng. Dừng thử nghiệm.

**Thử 2, YOLOv8n (nano), 2000 ảnh, 10 epoch, ÁP DỤNG:** giữ nguyên kiến trúc nano đã validate, chỉ tăng dữ liệu train. Chạy mượt, không nghẽn bộ nhớ, mất ~57 phút.

| Metric | Baseline (800 ảnh, nano) | Lần này (2000 ảnh, nano) | Thay đổi |
|---|---|---|---|
| Precision | 0.745 | 0.758 | +0.013 |
| Recall | 0.782 | **0.818** | **+0.036** |
| tp/fp/fn | 5513/1891/1537 | 5765/1837/1285 | tp tăng, fp và fn đều giảm |

Cả precision và recall đều tăng, không đánh đổi, chỉ cần thêm dữ liệu, không cần model lớn hơn. Recall vượt mốc 0.8.

**Lưu ý về số liệu:** số liệu ultralytics tự in ra lúc train (mAP50=0.835, precision=0.868, recall=0.778) đo trên bộ validation nội bộ khác (100 ảnh từ `validation` split), **không so sánh trực tiếp được** với bảng trên, bảng trên dùng đúng `evaluate.py` trên đúng bộ 50 ảnh cố định, cùng phương pháp với baseline.

**Quyết định cuối cùng:** dùng `runs/train_1a/n_2000/weights/best.pt` làm checkpoint chính thức cho pipeline (`src/pipeline/scan.py` nhận `detect_fn` qua injection, không hard-code đường dẫn checkpoint, nên đổi checkpoint không cần sửa code).

**Cải tiến kèm theo:** `src/detection/train/data.py` được sửa để bỏ qua tải lại ảnh đã có sẵn trên đĩa, các lần thử nghiệm tiếp theo với cùng `n_train`/`n_val` sẽ không tốn lại ~20-30 phút tải mạng.

## 04/08/2026: Backlog: `cluster_rows` chain theo y-center, không theo row average, CHƯA FIX

> **ĐÍNH CHÍNH (06/08/2026):** entry này đã được điều tra lại kỹ và **kết luận bị đảo ngược**
>: không case nào trong 3 case nêu dưới đây (và cả 4 case tìm thêm sau đó qua sweep) còn tái
> hiện được như một lỗi thật của `cluster_rows` dưới hệ thống hiện tại (checkpoint `n_2000`,
> tolerance đã recalibrate). Xem phần "## 06/08/2026: ĐÍNH CHÍNH" bên dưới để biết chi tiết đầy
> đủ và quyết định cuối cùng (đã revert fix). Phần dưới đây giữ nguyên làm lịch sử: lý luận lúc
> đó hợp lý với dữ liệu có trong tay khi đó, chỉ có kết luận cuối là sai.

Trong lúc audit checkpoint bug (`full` → `n_2000`, xem phần đầu file) và recalibrate lại
`ROW_CLUSTER_TOLERANCE_RATIO`/`Y_GAP_TOLERANCE_RATIO` trong `src/pipeline/scan.py`, xác nhận
lại 1 nghi vấn đã gặp nhiều lần nhưng chưa bao giờ được ghi thành issue riêng, 3 case cụ thể:

1. **Hảo Hảo crop (test1, đầu phiên brainstorm 04/08)**: test qua UI (crop tay qua
   `CropStep.jsx`) cho kết quả tệ hẳn so với script raw: 1 box bao trọn 2 hộp Hảo Hảo đỏ cạnh
   nhau đáng lẽ phải tách riêng (xem `docs/superpowers/specs/2026-08-04-adaptive-box-tolerance-design.md`
   mục 1). `filter_anomalous_boxes` (dùng chung `cluster_rows`) là nghi phạm.
2. **Yakult test3 cũ (checkpoint `full`)**: `row_cluster_tolerance` vượt 21.0-21.5px làm
   `cluster_rows` gộp gần hết 1 hàng kệ Yakult thành 1 nhóm, tạo gap ảo trải gần hết hàng (lý
   do ban đầu khiến `ROW_CLUSTER_TOLERANCE_RATIO` phải giữ safety margin chặt, xem lịch sử
   comment cũ trong `src/pipeline/scan.py` trước lần sửa hôm nay).
3. **2 gap test3 hôm nay (checkpoint `n_2000`, sau khi recalibrate)**: trace bằng
   `scripts/debug_stage_trace.py` cho cả 2 vùng gap: box bị flag NEEDS REVIEW đều là raw YOLO
   detection nguyên vẹn (IoU=1.000 với raw), không phải do `merge_adjacent_fragments` tạo ra,
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
nó*, không so với cả hàng. Một chuỗi box (vd. chai cao bắc cầu giữa 2 hàng kệ thật) có thể lần
lượt thoả điều kiện tolerance từng cặp một, trong khi cả hàng gộp lại đã trải rộng hơn 1 hàng
kệ vật lý thật nhiều.

**Trạng thái: ĐÃ ĐIỀU TRA LẠI, ĐÃ REVERT, xem "## 06/08/2026, ĐÍNH CHÍNH" bên dưới.** Lúc viết
entry này (04/08), quyết định là cố tình không gộp fix vào lần recalibrate tolerance hôm đó, vì
tin rằng đây là lỗi thuật toán (chain theo điểm liền kề thay vì trung bình/centroid cả cụm),
không phải lỗi chọn sai giá trị tolerance. Fix (so với y-center trung bình của cả hàng + span
cap) sau đó **đã được implement (commit `4a9ffed`)**, nhưng điều tra lại kỹ hơn ngày 06/08/2026
chạy trực tiếp trên hệ thống thật (checkpoint `n_2000`, tolerance đã recalibrate) thay vì chỉ
suy luận từ code, cho thấy cả 3 case nêu trên đều **không tái hiện được như lỗi thật của
`cluster_rows`**, và fix mới còn làm hỏng thêm ít nhất 3 hàng kệ thật vốn đã đúng. Đã revert
`4a9ffed`. Phần lý luận gốc bên trên (root cause, cơ chế chaining) vẫn đúng về mặt kỹ thuật, cơ
chế "chain theo box liền kề" đó có tồn tại trong code, chỉ là trên dữ liệu thật, hiện tượng đó
chưa từng thực sự bắc cầu 2 hàng kệ vật lý khác nhau thành 1 nhóm sai. Ghi lại ở đây theo đúng kỷ
luật "đo trước khi quyết, ghi lại trước khi quên" đã áp dụng xuyên suốt file này, để không bị
quên giữa các phiên làm việc.

## 06/08/2026: ĐÍNH CHÍNH: `cluster_rows` chaining case điều tra lại, KHÔNG tái hiện, đã REVERT fix

Entry 04/08/2026 phía trên kết luận `cluster_rows` có lỗi chaining thật (chain theo box liền kề
thay vì trung bình cả hàng) và liệt kê 3 case cụ thể làm bằng chứng. Fix được implement ngay sau
đó ở commit `4a9ffed` (so với y-center trung bình của cả hàng + hard cap span tối đa
`tolerance * max_span_multiplier`). Hôm nay (06/08/2026), điều tra lại toàn bộ, chạy trực tiếp
trên hệ thống thật (checkpoint `n_2000`, tolerance đã recalibrate ngày 04/08,
`row_cluster_tolerance` ≈23.4291px cho test3.HEIC, ≈18.9501px cho test1.HEIC) thay vì chỉ suy
luận từ code, để xác nhận lại 3 case gốc trước khi coi fix là xong việc.

**Kết quả: không case nào trong 3 case gốc còn tái hiện được như lỗi thật của `cluster_rows`
dưới hệ thống hiện tại:**

1. **Hảo Hảo crop (test1)**: không phải lỗi `cluster_rows`. Box `box45_both_cups` là singleton
   row dưới CẢ 2 thuật toán (cũ và mới), khoảng cách y-center thật vượt tolerance ở cả 2 phía
   (38.4px và 179.7px so với tolerance=18.9501px), không có box trung gian nào để "bắc cầu" qua.
   Case này thực ra được xử lý (đúng) bởi `filter_contained_boxes` (logic
   containment/leftover-coverage), không liên quan gì đến `cluster_rows`.
2. **Yakult checkpoint `full` cũ (test3)**: không tái hiện với checkpoint `n_2000`. Đây là
   artifact của checkpoint `full` (đã sửa riêng, xem phần đầu file), box position khác hẳn giữa
   2 checkpoint. Chạy thuật toán cũ trực tiếp trên `n_2000` + tolerance hiện tại: 0 gap ảo quanh
   hàng Yakult.
3. **2 gap test3 (h≈727-793px)**: đã được Task 3 xác nhận trước đó là duplicate detection
   (2 box trùng lặp của cùng 1 chai, containment 96.8%), không phải ranh giới 2 hàng thật; điều
   tra lại lần này tái xác nhận độc lập (đây chính là "old row 4" bên dưới, 1 hàng thật duy
   nhất, giống hệt nhau ở cả 2 thuật toán).

**4 candidate tìm thêm qua sweep hệ thống (Task 3, trước đó), "old row 4/5/9/18" của test3,
cũng đã được kiểm tra lại:**

- **Row 4** và **Row 9**: 2 hàng kệ thật, cả thuật toán cũ và mới nhóm **giống hệt nhau** (0 khác
  biệt). Row 9 (hàng Yakult) có kèm 1 fragment trùng lặp của item ở hàng dưới, nhưng cả 2 thuật
  toán đều KHÔNG bao giờ gộp hàng Yakult với hàng thật khác nằm dưới nó, đã re-verify trực tiếp
  trên toàn bộ dải yc∈[1950,2750].
- **Row 5** và **Row 18**: 2 hàng kệ thật (xác nhận bằng mắt qua ảnh annotate), nhưng thuật toán
  **MỚI** (row-mean + span-cap) lại **tách sai** thành nhiều nhóm (row 5: 3+2, row 18: 5+4+3),
  trong khi thuật toán cũ giữ đúng thành 1 nhóm.
- **Case thứ 5, phát hiện thêm trong lúc điều tra lại Hảo Hảo (test1)**: 4 hộp mì Hảo Hảo cạnh
  nhau (bao gồm `box41`, cùng ảnh với case 1 ở trên nhưng là 1 hàng khác), cũng là 1 hàng kệ
  thật, cũng bị thuật toán MỚI tách sai thành 2 nhóm, tạo gap ảo mà thuật toán cũ không có.

**Quyết định: đã REVERT commit `4a9ffed`.** `src/pipeline/row_clustering.py` đã trở về đúng
thuật toán single-linkage gốc (so với box cuối cùng của hàng, không phải trung bình cả hàng),
byte-identical với bản trước `4a9ffed`. Không tìm được case thật nào, dưới hệ thống hiện tại, mà
thuật toán cũ bắc cầu sai 2 hàng kệ vật lý khác nhau thành 1 nhóm, ngược lại, thuật toán mới bị
xác nhận đang làm hỏng ít nhất 3 hàng kệ thật vốn đã đúng.

**Giữ lại từ đợt điều tra này** (không phải revert sạch hoàn toàn, có 2 thứ hữu ích được giữ):

- `tests/pipeline/test_row_clustering.py` giờ có bộ test regression trên dữ liệu ảnh thật (trước
  đó module này hoàn toàn chưa có test), bảo vệ đúng hành vi đã confirm-correct của thuật toán
  (đã revert), để nếu sau này có ai vô tình implement lại "fix" chaining (hoặc gây regression
  khác) sẽ bị bắt ngay.
- `scripts/verify_cluster_rows_fix.py` được giữ nguyên làm công cụ verify hình học tổng quát
  (geometry-only, không tốn token/API), hữu ích cho các lần điều tra `cluster_rows`/gap detection
  sau này, dù `--sweep` mode của nó (thêm ở Task 3 của plan cũ) giờ sẽ raise `TypeError` nếu gọi
  vì `cluster_rows` đã revert, không còn nhận `max_span_multiplier`, biết và chấp nhận, không
  sửa (mục đích của tham số đó, calibrate span cap, không còn áp dụng sau khi revert).

**Nguồn:** 2 báo cáo điều tra đầy đủ (bằng chứng thật 100%, không có số liệu ước lượng):
`docs/detection-notes/2026-08-06-cluster-rows-diagnostic-report.md` và
`docs/detection-notes/2026-08-06-cluster-rows-old-algorithm-reverification.md`.

**Commit revert:** commit có message `revert(pipeline): restore original cluster_rows algorithm
after re-investigation`, không ghi SHA cụ thể ở đây (SHA của chính commit này thay đổi nếu nội
dung file này thay đổi, nên ghi cứng vào đây sẽ luôn lệch); xem
`git log --oneline -- src/pipeline/row_clustering.py` để lấy đúng SHA hiện tại.

## Bài học rút ra cho các lần sau

**16GB RAM (unified memory) là giới hạn cứng của máy, xuất hiện lặp lại 2 lần** (mosaic + nhiều ảnh ngày 17/7, model lớn hơn ngày 20/7), dấu hiệu nhận biết: tốc độ mỗi batch dao động mạnh/tăng dần bất thường (không phải chậm đều), kèm cột bộ nhớ báo gần 16G. Khi gặp dấu hiệu này, dừng ngay, không đợi hết epoch, nhiều khả năng không tự hết mà crash máy.

## 10/08/2026: Migrate sang YOLO26n, đổi checkpoint production

Sau khi `n_2000` (YOLOv8n) đã chạy ổn định qua nhiều đợt fix pipeline (merge fragment, adaptive tolerance, same-item dedup), benchmark thử YOLO26n, dòng model NMS-free mới của Ultralytics, để xem có đáng đổi không.

**Benchmark apples-to-apples:** cả 2 checkpoint chạy `model.val()` trên đúng full test set SKU-110K (2920 ảnh, xem `compare-yolov8n-vs-yolo26n.ipynb`):

| Checkpoint | Precision | Recall | mAP50 | mAP50-95 |
|---|---|---|---|---|
| YOLOv8n (`n_2000`) | 0.866 | 0.783 | 0.843 | 0.491 |
| YOLO26n | **0.892** | **0.828** | **0.888** | **0.536** |

YOLO26n thắng cả 4 chỉ số. Val run của YOLOv8n còn log `NMS time limit 2.800s exceeded` ở mấy ảnh dày đặc nhất (NMS truyền thống ngộp trên kệ đông sản phẩm); YOLO26n dùng NMS-free head nên không gặp lỗi kiểu này.

**Lưu ý về số liệu:** bảng trên không so sánh trực tiếp được với số cũ (`precision=0.758, recall=0.818` ghi ở đầu file này). Số cũ đo bằng phương pháp khác của `evaluate.py` (50 ảnh cố định, greedy match IoU=0.5, 1 điểm confidence duy nhất), không phải mAP kiểu COCO trên toàn bộ 2920 ảnh. Cả 2 số đều đúng ở đúng bối cảnh của nó, chỉ khác thước đo, không gộp chung để so sánh.

**Kiểm tra device MPS trước khi đổi:** `device="mps"` chưa từng được xác nhận cho YOLO26n (kiến trúc dual-head khác YOLOv8n). Chạy `model.predict(..., device="mps")` trên `test1.HEIC`: 56 box, ổn định qua nhiều lần chạy, khớp ballpark ~59 box đã thấy trên notebook Kaggle. Latency steady-state ~150-165ms/ảnh trên MPS (~170-210ms/ảnh trên CPU), MPS vẫn dùng được tốt, không cần fallback CPU.

**Đổi production:** `ml-service/app.py`'s `WEIGHTS_PATH` trỏ sang `sku110k_yolo26n_results/weights/best.pt` (fine-tune trên full SKU-110K train split, 8219 ảnh, 30 epoch, `patience=5`, train qua notebook `yolo26n-on-sku-110k.ipynb` trên Kaggle GPU). Weights giữ gitignored theo đúng quy ước cũ của repo (không commit file `.pt` vào git).

**Re-calibrate tolerance (`src/pipeline/scan.py`):** đổi checkpoint là đổi luôn scale box, không thể giả định margin cũ vẫn đúng. Đo lại trên đúng 5 ảnh test:

| Ảnh | Số box (n_2000 → YOLO26n) | Median height (n_2000 → YOLO26n) |
|---|---|---|
| test1 | 60 → 56 | 420.5px → 435.7px |
| test2 | 95 → 88 | 344.8px → 340.3px |
| test3 | 54 → 37 (-31%) | 519.9px → 566.9px (+9.0%) |
| test4 | 39 → 39 | 711.5px → 715.7px |
| test5 | 60 → 51 | 293.2px → 302.9px |
| **Gộp cả 5 ảnh** | 308 → 271 | 386.1px → 404.2px (+4.7%) |

Scale gộp chỉ lệch +4.7%, nhưng test3, đúng ảnh dùng để hiệu chỉnh "vùng nguy hiểm" ban đầu, mất tới 31% số box. Vì vậy vẫn sweep lại từ đầu thay vì tin vào con số gộp nhỏ. Kết quả: `row_cluster_tolerance` và `y_gap_tolerance` recalibrate an toàn, không có hiện tượng "collapse" nghiêm trọng nào xuất hiện trên ngưỡng mới ở cả 5 ảnh (sweep 1-120px cho row_cluster, 0.5-150px cho y_gap). Chi tiết đầy đủ, kể cả 1 điểm regress nhẹ ở test1 dưới operating point (không đổi output vì test1 vẫn 0 gap ở cả 2 checkpoint), nằm trong comment của `scan.py` (đầu file, phần `ROW_CLUSTER_TOLERANCE_RATIO`/`Y_GAP_TOLERANCE_RATIO`).

**Verify trước khi merge:** `pytest tests/ -q` 182/182 pass, test suite `ml-service` 6/6 pass, gọi thật `/predict` trên `test1.HEIC` trả về 54 box (confidence 0.556-0.886, trung bình 0.754), không lỗi.

**Quan sát phụ, chưa verify sâu (ghi lại để không quên):** so trên 5 ảnh demo thật, YOLO26n ra ít box hơn YOLOv8n ở mọi ảnh (ví dụ test3: 30 so với 73 box, nhìn trên grid so sánh downscale). Nhiều khả năng là bớt duplicate-detection trên cùng 1 vật lý, khớp với vấn đề 76% dup-same-SKU đã biết ở model cũ, không phải bớt sản phẩm thật detect được. Nhưng đây mới chỉ eyeball trên ảnh grid, chưa đối chiếu pixel-by-pixel; sweep tolerance ở trên xác nhận gián tiếp là không có dấu hiệu box thật bị mất, nhưng vẫn coi đây là giả thuyết hợp lý, chưa phải kết luận đã đo đủ.

**Quyết định:** chốt YOLO26n làm checkpoint production. Toàn bộ plan (bao gồm cả các task chưa liệt kê ở đây: audit reference cũ trong repo, archive file không dùng nữa) nằm ở `docs/superpowers/plans/2026-08-10-yolo26n-migration.md` (gitignored, chỉ có local, không có trong bản clone mới).

## Phụ lục: Schema 2 dataset SKU-110K

Gộp về đây từ 2 file riêng (`schema-sku110k.md`, `schema-sku110k-train.md`) để đỡ phân mảnh, cùng là tài liệu tham khảo cho phần Data & EDA ở trên, không phải log quyết định theo mốc thời gian như phần trên.

### Schema `Voxel51/sku110k_test` (bộ eval), xác nhận 17/7/2026

Dùng để **đánh giá** detection (không dùng để train). Giữ nguyên tên field/code bằng tiếng Anh vì đối chiếu trực tiếp với code.

#### Thử load bằng `datasets.load_dataset`: không có nhãn

```python
from datasets import load_dataset
ds = load_dataset('Voxel51/sku110k_test', split='test', streaming=True)
sample = next(iter(ds))
print(sample.keys())
```

Kết quả: `dict_keys(['image'])`, dataset này **không lộ ground-truth qua thư viện `datasets` thông thường**. `data.py` không dùng được cách này để lấy nhãn.

#### Thử `fiftyone.utils.huggingface.load_from_hub`: đúng nhưng tải quá nhiều

FiftyOne đọc được `Detection` object có `bounding_box` đúng format, nhưng `load_from_hub(..., max_samples=3)` thực tế tải **hơn 2.2GB** (vẫn đang tăng khi bị dừng) vào `~/fiftyone` và `~/.cache/huggingface`, bao gồm 2 model embedding không liên quan (`BAAI/bge-m3`, `sentence-transformers/all-MiniLM-L6-v2`) để dựng lại "brain runs" (index similarity/visualization) đã lưu sẵn, không liên quan gì đến việc benchmark detection. `max_samples` không giới hạn được lượng tải xuống đĩa. Vi phạm ràng buộc "không tải cả bộ dữ liệu, chỉ stream/lấy 1 phần" → **không dùng cách này**.

#### Cấu trúc repo thật (qua `huggingface_hub.HfApi().dataset_info(...)`)

```
.gitattributes
README.md
brain/radio_viz.json      (195 KB, FiftyOne brain artifact, không dùng)
data/test_*.jpg           (2936 file ảnh)
fiftyone.yml               (102 B)
metadata.json              (11 KB)
samples.json                (~7.7 GB, toàn bộ nhãn, 1 file duy nhất)
sku110k.gif                 (41.7 MB)
```

`samples.json` là 1 file JSON `{"samples": [ {...}, {...}, ... ]}`, mỗi phần tử ứng với 1 ảnh. Cấu trúc 1 phần tử (lấy qua HTTP Range request, chỉ ~2KB đầu):

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

**Field chứa box ground-truth:** `sample["ground_truth"]["detections"]`, mỗi phần tử có `bounding_box` = `[x, y, w, h]` **tương đối theo kích thước ảnh (0-1)**, gốc tọa độ ở góc trên-trái. `label` luôn là `"object"`, SKU-110K không phân loại sản phẩm, chỉ khoanh vùng ("class-agnostic"), đúng với mục đích chỉ dùng cho detection của dự án này.

#### Cách lấy dữ liệu đã chọn: stream `samples.json` bằng `ijson`, chỉ tải đúng ảnh cần

Endpoint HF hỗ trợ Range request và `samples.json` là 1 mảng JSON, nên `requests.get(url, stream=True)` + `ijson.items(resp.raw, 'samples.item')` đọc được N bản ghi đầu rồi dừng (đóng kết nối) mà không tải hết 7.7GB. Đã kiểm chứng: lấy 5 sample đầu mất ~13s, không tải file đầy đủ. Với mỗi `filepath` trong N sample đó, `huggingface_hub.hf_hub_download(repo_id=..., repo_type='dataset', filename=sample['filepath'])` chỉ tải đúng 1 ảnh đó (vài MB, ảnh gốc ~2448x3264). Cách này tránh được cả 2 vấn đề trên (`datasets` không có nhãn, `fiftyone` tải không kiểm soát), giữ dung lượng tải tỉ lệ thuận với `n`. `data.py` được viết theo đúng cách này.

### Schema `harryrobert/SKU-110k-reformat` (bộ train), xác nhận 17/7/2026

Dùng để **train** (khác với `Voxel51/sku110k_test` ở mục trên, chỉ dùng để eval).

Lệnh kiểm tra: `get_dataset_split_names('harryrobert/SKU-110k-reformat')`, sau đó `load_dataset('harryrobert/SKU-110k-reformat', split='train', streaming=True)`, lấy sample đầu.

**Các split:** `train` (8219 ảnh), `validation` (588 ảnh), `test` (2936 ảnh), số lượng này khớp chính xác với số liệu chính thức của SKU-110K.

**Cấu trúc field:**
```
{'image': Image, 'image_id': int64, 'width': int32, 'height': int32,
 'objects': {'id': [int64], 'bbox': [[float32; 4]], 'category': [int64], 'area': [float32]}}
```

`objects.bbox` = `(x, y, w, h)` **tọa độ pixel tuyệt đối, gốc ở góc trên-trái** (kiểu COCO, khác với `Voxel51/sku110k_test` dùng tọa độ *tương đối*, **không dùng chung hàm** `parse_fiftyone_detections` cho 2 dataset này). `category` là 1 giá trị hằng số cho mọi object, SKU-110K không phân loại sản phẩm, chỉ khoanh vùng ("object"), giống bộ eval.

**Không dùng để eval:** split `test` của repo này (2936 ảnh, trùng số lượng với `Voxel51/sku110k_test`) chưa xác nhận có phải ảnh khác hay không, dự án chỉ dùng `train`/`validation` từ repo này để train, còn eval luôn cố định dùng `Voxel51/sku110k_test` qua `src/detection/benchmark/data.py`, không đổi.
