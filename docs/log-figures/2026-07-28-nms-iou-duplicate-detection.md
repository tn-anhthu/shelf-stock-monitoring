# NMS iou tuning cho case "nhiều box IoU cao trên 1 vật": 2026-07-28

## Bối cảnh đối chiếu

Case này đã có 2 nguồn tài liệu trước đó cần đối chiếu trước khi đo lại:

- Session report 2026-07-21 (đã bị xoá khỏi repo) dòng 44: ghi nhận case
  "duplicate, IoU cao 0.5-0.7" trên ảnh demo thật (kệ sữa Vinamilk), hướng sửa
  đề xuất ban đầu là chỉnh `iou` trong `model.predict()`.
- `scripts/debug_duplicate_boxes.py`: đã đo sẵn IoU/containment cho đúng case
  Vinamilk này (box73/74/86/89, test2), kết luận containment cao (0.9+) trong
  khi IoU chỉ 0.4–0.68 (dưới NMS default 0.7), nên khuyến nghị dùng containment
  filter thay vì hạ `iou`. `filter_contained_boxes` (đã production) được xây từ
  khuyến nghị đó.

**Kiểm tra lại filter_contained_boxes trên đúng 4 box này: chỉ loại được 1/4
(drop box86), còn 3 box (73/74/89) vẫn sống sót trên cùng 1 hộp vật lý.** Case
này CHƯA giải quyết xong, đúng như báo cáo của user, không phải đã fix.

*Lưu ý cấu trúc tài liệu: `docs/specs/mvp-design.md` hiện tại (151 dòng) đã được
rút gọn, không còn "mục 9" dạng nhật ký quyết định như bản cũ
(`2026-07-20-shelfsense-mvp-design.md`, đã bị xoá khỏi repo), nội dung lịch sử
case này nằm ở file session-report nêu trên, không phải trong spec hiện hành.*

## Bước 1: Ảnh nào có hiện tượng?

Đo trên raw `detect_1a` output (ảnh gốc thật, không crop), tìm mọi cặp box có
IoU trong [0.3, 0.7] rồi tính containment ratio. Containment ≥0.8 = "1 vật lý bị
detect nhiều box" (duplicate signature); containment thấp hơn = nghi ngờ 2 sản
phẩm khác nhau đặt sát nhau.

| ảnh | số cặp IoU∈[0.3,0.7] | trong đó duplicate-signature (containment≥0.8) |
|---|---|---|
| test1 | 3 | 3 |
| test2 | 12 | 12 |
| test3 | 20 | 17 (3 cặp containment 0.67–0.80, xem bước 3) |
| test4 | 3 | 3 |
| test5 | 4 | 4 |

**Hiện tượng xảy ra ở CẢ 5 ẢNH, không riêng test2/Vinamilk**: test2 (case đã
biết) không phải nặng nhất; test3 (kệ sữa/sữa chua nhiều lốc xếp chồng) có tới
20 cặp. Đã đối chiếu, KHÔNG nhầm với `test2_vinamilk_check/` (case catalog-gap
sugar/no đường, khác hoàn toàn) hay `merge_adjacent_fragments` (case IoU gần 0).

## Bước 2: Phân bố IoU: NMS không thể tách 2 nhóm bằng 1 ngưỡng

IoU của các cặp duplicate-signature trải dài **0.307 – 0.699**: chồng lấn gần
như toàn bộ dải [0.3, 0.7]. Đây đã là dấu hiệu xấu cho hướng chỉnh 1 ngưỡng
`iou` toàn cục.

## Bước 3: Sweep `iou` thật trên 5 ảnh gốc

Gọi trực tiếp `model.predict(..., iou=X)` (không qua wrapper, để test nhiều giá
trị) trên `data/scan_viz/input/test{1-5}.HEIC`, kiểm tra 2 điều mỗi threshold:
(a) các cặp duplicate đã biết có bị NMS gộp lại (chỉ còn 1 box) không; (b) các
cặp containment-thấp hơn có bị gộp oan không.

| ảnh | iou cần để lọc hết dupe đã biết | ghi chú |
|---|---|---|
| test1 | 0.4 | |
| test2 | 0.6 | |
| test3 | **0.5 chưa đủ, cần ≤0.3** (2 cặp: 1 cặp còn sống ở 0.4, cặp còn lại tận 0.3 mới hết) | |
| test4 | 0.5 | |
| test5 | 0.5 | |

**test3 xuất hiện over-suppression SỚM HƠN mức cần để lọc hết dupe:** ở
`iou=0.6`, 1 trong 2 cặp "containment thấp hơn" (0.791) đã bị NMS gộp oan,
trong khi phải hạ tới `iou=0.3` mới lọc hết dupe khó nhất của cùng ảnh. Tức là
**không có giá trị `iou` nào vừa lọc hết dupe vừa không gộp oan, ngay trên
cùng 1 ảnh.**

**Kiểm tra bằng mắt cả 3 cặp "containment thấp hơn" đã flag ở test3** (nghi ngờ
là 2 sản phẩm khác nhau, containment 0.672–0.796), **cả 3 đều KHÔNG PHẢI 2 sản
phẩm khác nhau**: chúng là 2 lốc Yakult xếp chồng (box38/box40, box40/box42) và
1 chai Betagen với box thứ 2 chỉ chụp phần nắp/cổ chai (box20/box44), tức là
detector vẽ box lệch/không khít trên 1 chồng 2 đơn vị vật lý thật, không phải
lỗi trùng lặp sạch. Ảnh minh hoạ đã lưu, ví dụ rõ nhất (Yakult 2 lốc chồng,
box đỏ = lốc trên + đường nối, box xanh = lốc dưới):

```
box38=(127,2191,1001,2716)  box40=(127,2039,985,2615)  iou=0.617 containment=0.791
-> cả 2 box đều lệch nửa lốc, KHÔNG box nào khớp đúng 1 lốc, nếu NMS gộp còn 1
   box, sẽ MẤT 1 lốc thật khỏi kết quả đếm (từ 2 lốc thật -> chỉ còn đại diện 1 box)
```

**Kết luận quan trọng hơn dự kiến ban đầu:** rủi ro không chỉ là "2 SKU khác
nhau bị gộp nhầm" (như lo ngại gốc trong session report 2026-07-21), mà là
**bất kỳ 2 đơn vị vật lý thật nào xếp sát/chồng nhau (kể cả cùng SKU) đều có
thể bị NMS gộp nhầm nếu hạ `iou` đủ thấp để bắt được case Vinamilk**, vì
regression của detector không đủ chính xác để tách 2 đơn vị chồng nhau ra 2 box
khít, làm mất số lượng đếm được thật, không khác gì hậu quả của việc gộp nhầm
2 SKU khác nhau.

## Bảng trước/sau (số box thừa còn lại theo signature-based check)

| ảnh | iou mặc định hiện tại (0.7, không set), dupe-pair sống sót | iou hạ đủ để lọc hết dupe của ảnh đó | over-suppression xảy ra ở ảnh nào |
|---|---|---|---|
| test1 | 3/3 pairs sống | 0.4 | không phát hiện (không có cặp containment-thấp nào trong band để kiểm) |
| test2 | 3/3 pairs sống (mẫu; case Vinamilk gốc) | 0.6 | không phát hiện (không có cặp containment-thấp nào trong band để kiểm) |
| test3 | 2/2 pairs mẫu sống | **không có giá trị nào đủ**: 0.6 đã gộp oan, 0.3-0.5 vẫn còn dupe | **CÓ, xác nhận ở 0.6** |
| test4 | 2/2 pairs sống | 0.5 | không phát hiện |
| test5 | 2/2 pairs sống | 0.5 | không phát hiện |

*Lưu ý: test1/2/4/5 "không phát hiện over-suppression" chỉ vì bước 1 không tìm
thấy cặp containment-thấp nào trong dải IoU đang xét ở các ảnh đó để kiểm tra,
không phải bằng chứng những ảnh này an toàn tuyệt đối khi hạ `iou` toàn cục,
chỉ là ngoài phạm vi mẫu đã đo được.*

## Giá trị `iou` chọn: GIỮ NGUYÊN mặc định (không set, tức 0.7 của ultralytics)

Không đổi tham số `iou` trong `model.predict()`. Căn cứ: test3 (dùng chung 1
tham số `iou` toàn cục cho mọi ảnh, đúng cách `detect_1a` gọi hiện tại) chứng
minh trực tiếp bằng đo thật rằng không tồn tại 1 giá trị `iou` nào thoả cả 2
điều kiện cùng lúc trên cùng 1 ảnh, khớp với kết luận phân tích tĩnh của
`debug_duplicate_boxes.py` trước đó, giờ được xác nhận thêm bằng thực nghiệm
chạy model thật trên cả 5 ảnh, không chỉ suy luận từ 1 case.

**Không mở rộng sang hướng khác** (không đụng LLM verify parallelization, không
tự ý implement fix mới cho `filter_contained_boxes`) theo đúng phạm vi yêu cầu,
việc `filter_contained_boxes` chỉ xử lý được 1/4 box của case Vinamilk (còn
3/4 sống sót) là dữ kiện đã đo được, để lại cho quyết định tiếp theo của user,
không tự ý làm thêm trong việc này.
