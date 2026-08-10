# ROI-crop: center-bias + sharpness component selection: 2026-07-28

## Bối cảnh

Sau benchmark threshold (0.55, xem `2026-07-28-roi-crop-threshold-benchmark.md`),
CLIPSeg-only đạt 3/5 ảnh (test1, test3, test4: 0 box thừa/0 gap giả). test2, test5
vẫn lọt kệ hàng xóm. Giả thuyết cần test: có thể `largest_connected_component_bbox`
đang chọn nhầm component (kệ hàng xóm to hơn/rõ hơn kệ mục tiêu) trong khi vẫn có
component đúng nằm trong danh sách, nếu vậy, chọn lại bằng center-bias (ưu tiên
gần tâm ảnh) + độ nét (Laplacian variance, kệ gần focal plane hơn thường nét hơn)
có thể sửa được.

## Bước 1: Điều tra tiền đề: có thực sự tồn tại ≥2 component để chọn không?

Trước khi implement bất kỳ logic chọn nào, đo trực tiếp: với mask
`combine_keep_exclude` ở mọi threshold trong {0.35, 0.40, ..., 0.80} (rộng hơn
hẳn khoảng benchmark trước, 0.30–0.70), đếm số connected component ≥ 2% diện tích
ảnh, cho cả 5 ảnh gốc.

**Kết quả: mọi ảnh, mọi threshold, luôn ≤ 1 component ≥ 2% diện tích.** Không có
ảnh nào tách thành ≥2 component ở bất kỳ threshold nào đo được:

| test | 0.35 | 0.45 | 0.55 | 0.65 | 0.75/0.80 |
|---|---|---|---|---|---|
| test1 | 1 | 1 | 1 | 1 | 0 (t=0.75) |
| test2 | 1 | 1 | 1 | 1 | 1 |
| test3 | 1 | 1 | 1 | 1 | 1 |
| test4 | 1 | 1 | 1 | 1 | 1 |
| test5 | 1 | 1 | 1 | 1 | 1 |

Với test2/test5 cụ thể, area của component duy nhất giảm dần đều khi threshold
tăng (test2: 97.2% ở t=0.35 → 26.7% ở t=0.80; test5: 73.7% → 2.8%) nhưng **không
bao giờ vỡ ra thành 2 mảnh**, kệ mục tiêu và kệ hàng xóm luôn dính liền thành 1
khối liên thông, ngay cả khi component co lại rất nhỏ (test5 ở t=0.80 chỉ còn
2.8% diện tích, vẫn là 1 khối duy nhất).

**Kết luận bước 1: việc chọn component (center-bias/độ nét) không có gì để chọn,
luôn chỉ có đúng 1 candidate.** Vấn đề nằm ở tầng mask (2 kệ bị nối liền do
không có khoảng sàn/trần rõ ràng ngăn cách trong khung hình), không phải ở tầng
chọn component. Đây là bằng chứng trực tiếp, không suy đoán.

## Bước 2: Vẫn implement cơ chế chọn component (theo yêu cầu), xác nhận không đổi

Dù bước 1 dự đoán cơ chế này sẽ là no-op trên 5 ảnh demo, vẫn implement đầy đủ
theo yêu cầu (infrastructure tổng quát, có thể hữu ích cho ảnh khác sau này):

- `list_connected_components(mask, min_area_ratio)`: liệt kê MỌI component ≥
  ngưỡng diện tích (không chỉ lấy component to nhất).
- `center_bias_score(bbox, image_size)`: 1.0 nếu tâm bbox trùng tâm ảnh, giảm
  tuyến tính về 0.0 ở góc ảnh (điểm xa tâm nhất có thể).
- `laplacian_sharpness(image, bbox)`: `cv2.Laplacian(...).var()` trên vùng ảnh
  gốc trong bbox, proxy độ nét.
- `score_components`: chuẩn hoá min-max từng tín hiệu (area, center, sharpness)
  trên tập candidate rồi cộng có trọng số, chuẩn hoá vì 3 tín hiệu khác thang đo
  hẳn nhau (tỉ lệ, điểm [0,1], phương sai Laplacian thô).
- **Trọng số dùng: (1.0, 1.0, 1.0), bằng nhau.** Đây **không phải số đo được từ
  5 ảnh demo** như threshold, vì không có ảnh demo nào từng sinh ra ≥2 candidate
  để mà đo trọng số tối ưu trên đó. Trọng số bằng nhau là lựa chọn mặc định có
  lý do (không có căn cứ để ưu tiên tín hiệu nào hơn tín hiệu nào khi chưa có dữ
  liệu thật), được validate đúng đắn về mặt cơ chế bằng test case tổng hợp
  (`tests/pipeline/test_roi_crop.py::test_select_best_component_picks_centered_sharp_blob_over_big_offcenter_blurry_one`,
  1 blob to/lệch tâm/mờ giả lập vs 1 blob nhỏ hơn/giữa tâm/nét, cơ chế chọn
  đúng cái nhỏ-nét-giữa tâm), **không phải benchmark trên ảnh thật**.

## Bước 3: Chạy lại `crop_to_roi` (đã gắn scoring) trên 5 ảnh gốc thật

| ảnh | bbox trước (largest-only) | bbox sau (center-bias+sharpness) | đổi? |
|---|---|---|---|
| test1 | (409, 94, 3024, 3864) | (409, 94, 3024, 3864) | không |
| test2 | (0, 91, 3024, 3836) | (0, 91, 3024, 3836) | không |
| test3 | (0, 70, 3024, 3958) | (0, 70, 3024, 3958) | không |
| test4 | (32, 179, 2828, 4016) | (32, 179, 2828, 4016) | không |
| test5 | (0, 254, 3024, 3859) | (0, 254, 3024, 3859) | không |

Bbox **giống hệt 100%**: đúng như dự đoán ở bước 1. Vì input luôn chỉ có 1
candidate, không cần chạy lại YOLO để đo box thừa/gap giả, kết quả chắc chắn y
hệt lần benchmark auto-crop trước (test1: 1 box rìa/1 gap; test2: 8 box rìa/11
gap (2 off-shelf); test3: 5 box rìa/2 gap; test4: 0 box rìa/3 gap; test5: 4 box
rìa/4 gap (2 off-shelf)).

## Kết luận: DỪNG theo đúng điều kiện đã thống nhất

Vòng thử cuối cùng (center-bias + sharpness) **không giải quyết được test2/test5**,
vì lý do đã xác định rõ và đo được: mask không bao giờ tách thành nhiều component
để mà chọn. Đây không phải lỗi implement hay lỗi trọng số, vấn đề nằm ở tầng
CLIPSeg mask (semantic segmentation không phân biệt được "kệ đang chụp" khỏi
"kệ hàng xóm cùng chiều cao mắt người, không có khoảng sàn/trần ngăn cách") mà
bước chọn component ở SAU mask không thể sửa được.

**Theo đúng cam kết trước khi làm vòng này: dừng lại, không thử prompt engineering
thêm, không thêm tín hiệu thứ 3.** Xác nhận trạng thái cuối: **ROI-crop preprocessing
đạt 3/5 ảnh demo (60%)**, là tính năng **giảm rủi ro** (loại bỏ hoàn toàn box thừa
rìa + gap giả trên phần lớn ảnh thật), **không phải giải pháp triệt để** cho mọi
trường hợp, 2 case còn lại (kệ đảo/kệ trưng bày độc lập, có kệ khác cùng chiều
cao mắt người lọt 2 bên khung hình) dựa vào **edge-crop warning** (mục 7 spec,
kiểm tra hình học sau detect, banner cảnh báo cùng cơ chế low-confidence) và
**kỷ luật chụp ảnh của nhân viên** làm lưới an toàn thứ hai, không đầu tư thêm
vào ROI-crop cho hướng segmentation này.
