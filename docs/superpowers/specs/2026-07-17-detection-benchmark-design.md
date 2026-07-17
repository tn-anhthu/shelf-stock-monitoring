# Design: Detection Benchmark Sprint (Phase 1a-pre)

**Ngày:** 2026-07-17
**Trạng thái:** Đã duyệt bởi Anh Thư — sẵn sàng chuyển sang writing-plans
**Phạm vi:** Chỉ phase Detection (Phase 1 trong pipeline 4 bước). Đây là **spec đầu tiên trong chuỗi spec cho toàn dự án** — mỗi phase (Classification, Depth multiplier, Pricing) sẽ có spec riêng, viết sau khi phase trước đã có kết quả/quyết định rõ ràng, vì output của mỗi phase ảnh hưởng input/giả định của phase sau.

## Bối cảnh

Dự án "Inventory-based Lending Signal" chọn hướng dense-shelf khó (kiểu SKU-110K, hàng trăm SKU chồng chéo) trong 5 tuần (2+2+1 buffer). Kế hoạch gốc trong README là fine-tune YOLO nano trên SKU-110K ngay từ đầu. Khi rà lại, phát hiện 2 điều cần điều chỉnh:

1. **Có các phương án thay thế việc tự train** — dùng checkpoint community đã train sẵn trên SKU-110K, hoặc dùng detector zero-shot (Grounding DINO) không cần train — nên cần benchmark trước khi cam kết train riêng, để tránh đốt hết buffer 2 tuần đầu vào 1 hướng chưa chắc cần thiết.
2. **README ghi sai vai trò của Autodistill**: SKU-110K dataset đã có sẵn bounding-box ground truth (1 class "object"), nên **không cần Autodistill để label chính dataset này**. Autodistill (Grounding DINO + SAM) chỉ cần thiết sau này nếu tự chụp ảnh kệ hàng Việt Nam để fine-tune thêm (ảnh đó chưa có label sẵn). README cần được sửa lại điểm này.

## Mục tiêu của sprint này

Quyết định — dựa trên số liệu định lượng, không cảm tính — nên dùng cách nào cho Phase 1 (Detection/localization) trước khi bước sang Phase 2 (Classification):

- **1b**: dùng checkpoint community đã train sẵn trên SKU-110K (vd. `foduucom/product-detection-in-shelf-yolov8` trên Hugging Face), bỏ qua bước train.
- **1c**: dùng Grounding DINO zero-shot (open-vocabulary), không cần checkpoint riêng, không cần train.
- **1a (fallback)**: nếu cả 1b và 1c đều không đạt ngưỡng, quay lại kế hoạch gốc — tự fine-tune YOLO nano trên SKU-110K.

## Ngoài phạm vi (out of scope) của sprint này

- Classification (CLIP/SigLIP2 + catalog), Depth multiplier UI, Pricing aggregation — sẽ có spec riêng sau khi Phase 1 xong, vì cách detect được chọn (1a/1b/1c) ảnh hưởng tới format box output mà Phase 2 nhận vào.
- Ảnh kệ hàng thật tự chụp (Việt Nam) — sprint này benchmark trên subset SKU-110K trước; sẽ chụp ảnh thật ở sprint kế tiếp sau khi có hướng detect rõ.
- Auto-labeling bằng Autodistill — chỉ cần khi có ảnh tự chụp chưa có label, không cần cho sprint này.

## Setup

- Stream subset nhỏ SKU-110K (~50-100 ảnh có ground-truth box) qua Hugging Face `datasets`, không tải full 13.6GB.
- Chạy inference bằng `device='mps'` trên MacBook Pro M4, 16GB RAM.
- Code nằm ở `src/detection/benchmark/` (script chạy 1b, script chạy 1c, script tính metric — tách riêng để dễ so sánh/tái sử dụng).

## Quy trình benchmark

1. Load subset SKU-110K + ground-truth boxes.
2. Chạy 1b (YOLOv8 checkpoint có sẵn) trên subset → lưu predicted boxes.
3. Chạy 1c (Grounding DINO, prompt "product" / "item on shelf") trên subset → lưu predicted boxes.
4. Tính Precision, Recall, AP theo chuẩn COCO tại IoU=0.5 cho cả 2, so với ground-truth.
5. Đo thời gian inference/ảnh cho cả 2 trên M4 (yếu tố phụ, dùng để phân định khi cả 2 đều đạt ngưỡng).

## Ngưỡng quyết định (pass/fail)

Tham chiếu: baseline gốc trên SKU-110K đạt AP@0.5 ≈ 0.56, một số nghiên cứu gần đây đạt ≈ 0.61 ([nguồn](https://docsaid.org/en/papers/retail-product/sku-110k/)). Mục tiêu Phase 1 không phải đạt SOTA mà là "đếm được đa số sản phẩm" — sai số một phần sẽ được bù bằng message xác nhận confidence-thấp ở bước human-in-the-loop (đã chốt trong README).

- **Recall@IoU0.5 ≥ 0.45–0.5** → coi là đủ dùng, đi tiếp với model đó.
- Nếu **cả 1b và 1c đều dưới ngưỡng** → fallback sang 1a (tự train YOLO trên SKU-110K), dùng phần thời gian còn lại của 2 tuần đầu.
- Nếu **cả 2 đều đạt ngưỡng** → chọn model nhanh hơn/nhẹ hơn trên M4 (dự đoán là 1b, vì Grounding DINO nặng hơn nhiều — cần đo thật để xác nhận, không giả định).

## Rủi ro đã biết

- Checkpoint 1b là community-trained, **chưa có xác nhận chính thức từ Ultralytics** ([issue #23669](https://github.com/ultralytics/ultralytics/issues/23669)) — license và chất lượng chưa kiểm chứng, phải đọc model card và test kỹ trước khi dùng ngoài mục đích thử nghiệm cá nhân.
- Hiệu năng Grounding DINO trên dense/overlapping retail shelf **chưa có benchmark công khai nào được tìm thấy** — kết quả từ sprint này sẽ là dữ liệu gốc (chưa có cái để đối chiếu).
- Benchmark chạy trên ảnh SKU-110K (siêu thị nước ngoài), không phải ảnh tạp hóa/Winmart Việt Nam thật — kết quả có thể không transfer hoàn toàn; đây là lý do sprint sau cần test lại trên ảnh tự chụp.

## Kết quả bàn giao (deliverables)

- Script benchmark tái sử dụng được (`src/detection/benchmark/`).
- Bảng số liệu Precision/Recall/AP/thời gian inference cho 1b và 1c.
- Quyết định bằng văn bản: chọn 1a, 1b hay 1c cho phần còn lại của Phase 1.
- Cập nhật README: sửa lại mô tả vai trò của Autodistill (chỉ cần cho ảnh tự chụp, không cần cho SKU-110K).

## Testing

- Unit test cho hàm tính Precision/Recall/AP (so với 1 bộ box giả lập biết trước đáp số) — đảm bảo số liệu benchmark đáng tin.
- Kiểm tra thủ công: visualize predicted boxes đè lên vài ảnh mẫu để xác nhận metric khớp với quan sát bằng mắt (tránh bug âm thầm trong code tính IoU).

## Bước tiếp theo sau spec này

Sau khi sprint benchmark này xong và có quyết định (1a/1b/1c), viết spec kế tiếp cho phần còn lại của Phase 1 (nếu fallback 1a) hoặc bắt đầu spec cho Phase 2 (Classification) nếu 1b/1c đạt ngưỡng.
