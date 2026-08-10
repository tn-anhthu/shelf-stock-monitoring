# ROI-crop (CLIPSeg) threshold benchmark: 2026-07-28

## Phương pháp

Không đoán ngưỡng. Đo trên 5 ảnh demo gốc (`data/scan_viz/input/test{1..5}.HEIC`):

1. Ground truth ROI mỗi ảnh = bounding box của crop tay (`input_crop/test{n}_crop.HEIC`)
   định vị lại trong ảnh gốc bằng template matching (`cv2.matchTemplate`, match
   confidence 0.91–1.00 cho cả 5 ảnh, xem `GROUND_TRUTH` trong script benchmark).
2. Chạy CLIPSeg (`CIDAS/clipseg-rd64-refined`) 1 lần/ảnh cho keep-prompts
   (`product`, `store shelf`, `shelf edge`) và exclude-prompts (`floor`, `ceiling`,
   `person`, `empty aisle background`), cache probability map, sweep threshold
   trên map đã cache (không chạy lại model mỗi threshold).
3. Với mỗi threshold trong {0.30..0.70, bước 0.05}: `combine_keep_exclude` → mask
   → `largest_connected_component_bbox` (min_area_ratio=0.05) → so IoU với ground
   truth. Chọn threshold có avg IoU cao nhất, ưu tiên ít fallback hơn khi hòa.

## Kết quả

| threshold | avg IoU | fallback | test1 | test2 | test3 | test4 | test5 |
|---|---|---|---|---|---|---|---|
| 0.30 | 0.761 | 0/5 | 0.681 | 0.838 | 0.709 | 0.803 | 0.773 |
| 0.35 | 0.764 | 0/5 | 0.684 | 0.841 | 0.711 | 0.811 | 0.773 |
| 0.40 | 0.769 | 0/5 | 0.688 | 0.845 | 0.714 | 0.828 | 0.772 |
| 0.45 | 0.779 | 0/5 | 0.718 | 0.850 | 0.716 | 0.845 | 0.767 |
| 0.50 | 0.787 | 0/5 | 0.744 | 0.858 | 0.720 | 0.859 | 0.756 |
| **0.55** | **0.795** | **0/5** | 0.728 | 0.888 | 0.725 | 0.891 | 0.746 |
| 0.60 | 0.783 | 0/5 | 0.595 | 0.931 | 0.738 | 0.938 | 0.715 |
| 0.65 | 0.752 | 0/5 | 0.479 | 0.974 | 0.750 | 0.938 | 0.618 |
| 0.70 | 0.789 | **1/5** | None | 0.938 | 0.770 | 0.942 | 0.504 |

**Chọn threshold = 0.55**: avg IoU cao nhất (0.795), fallback rate 0/5. Từ 0.60 trở
lên, IoU tiếp tục tăng ở test2/test4 (kệ chụp thẳng, ít phối cảnh) nhưng sập mạnh ở
test1/test5 (kệ chụp nghiêng góc rộng, connected component co lại quá nhỏ, mất cả
phần kệ thật ở rìa) và 0.70 gây fallback hẳn ở test1 (mask dưới ngưỡng diện tích tối
thiểu). 0.55 là điểm cân bằng tốt nhất đo được, không phải số đoán.

## Giới hạn quan trọng phát hiện được (không phải do threshold)

IoU cao ở test2 (0.888) và test4 (0.891) tại 0.55 nghe có vẻ tốt, nhưng khi chạy
YOLO thật trên ảnh đã auto-crop (xem báo cáo so sánh chính), **test2 và test5 vẫn
lọt kệ hàng xóm** (Kimchi, Ice Tea Sweet Peach ở test2; nền/tay người ở test5) dù
IoU với ground-truth không tệ. Nguyên nhân: keep-prompt "product"/"store shelf" chấm
điểm cao như nhau cho CẢ kệ mục tiêu VÀ kệ hàng xóm (kệ hàng xóm cũng là "sản phẩm
trên kệ" về mặt ngữ nghĩa), và exclude-prompt hiện tại (floor/ceiling/person/empty
background) không có prompt nào loại trừ được "kệ khác cạnh kệ chính", nên 2 kệ bị
nối liền thành 1 connected-component duy nhất khi không có khoảng sàn/trần rõ ràng
ngăn cách trong khung hình. Đây là giới hạn thiết kế prompt, không phải lỗi threshold,
fallback hiện tại (mask rỗng/quá nhỏ) không bắt được case này vì mask vẫn hợp lệ,
chỉ là "quá rộng". Xem báo cáo so sánh auto-crop vs crop tay để chi tiết từng ảnh.
