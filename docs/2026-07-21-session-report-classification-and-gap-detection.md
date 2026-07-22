# Báo cáo phiên làm việc — 2026-07-21: Gap Detection, Box Fragmentation, Classification Accuracy

## Bối cảnh xuất phát

Đầu phiên, ShelfSense đã có: catalog 40 SKU thật (ảnh + giá + embedding SigLIP2), YOLO nano
fine-tune (recall 0.818), pipeline logic (`classify.py`, `confidence.py`, `aggregate.py`,
`scan.py`) — nhưng tất cả mới test bằng model giả, chưa chạy thử thật end-to-end. Hai việc còn
treo: (1) viết hàm crop ảnh theo box YOLO, (2) chạy thử thật để xem 2 model (YOLO + SigLIP2)
bàn giao cho nhau có ổn không.

## Phần 1 — Hoàn thiện pipeline cơ bản

- **`crop_box`** (`src/pipeline/crop.py`): crop ảnh theo box, có padding tùy chỉnh, tự clamp về
  biên ảnh, trả `None` nếu box suy biến sau khi clamp.
- **`classify_crop` thêm `unknown_threshold`**: nếu similarity cao nhất vẫn quá thấp, trả
  `(None, score)` thay vì ép match sai — `run_scan` đã có sẵn cơ chế loại bỏ `sku_id=None`
  khỏi kết quả đếm, không cần sửa `scan.py`.
- **`scripts/run_scan_e2e.py`**: nối YOLO thật + SigLIP2 thật + catalog thật qua `run_scan`.
- **`scripts/visualize_scan_e2e.py`**: lưu lại từng bước (ảnh gốc, ảnh annotate, lưới crop) để
  dùng làm minh họa slide.

## Phần 2 — Out-of-stock / Gap Detection

Bàn về việc thêm tính năng khoanh vùng khoảng trống trên kệ (lấy cảm hứng từ hình ảnh
marketing của các đối thủ enterprise). Quyết định: dùng heuristic hình học (so khoảng cách
giữa 2 box liền kề với chiều rộng trung bình sản phẩm), **không** train model riêng cho
"khoảng trống" — không có data gán nhãn cho việc này. Nâng từ nice-to-have lên core feature
(đánh đổi có ý thức với rủi ro timeline, ghi rõ trong spec).

Cũng phát hiện 1 bug thật trong lúc bàn: `flags` trong `scan.py` chỉ tính cho SKU đã detect
được ít nhất 1 lần — SKU hết sạch hoàn toàn (0 detection) không bao giờ được gắn cờ `"out"`.
Đã sửa: loop `flags` qua toàn bộ catalog thay vì chỉ qua SKU đã detect.

## Phần 3 — Test thật lộ ra 2 lỗi, xử lý bằng debug có số liệu (không đoán)

**Lỗi A — Gap detection bỏ sót gap thật:** chạy thử trên ảnh kệ sữa thật, gap rõ ràng bằng mắt
nhưng thuật toán trả về 0 gap. Viết `debug_gap_detection.py` để in ra từng bước tính toán thay
vì đoán. Kết luận: 1 box rác (YOLO detect nhầm chữ mờ trên shelf-talker thành sản phẩm) đã chẻ
khoảng trống thật thành 2 mảnh nhỏ, không mảnh nào đủ lớn để vượt ngưỡng.

**Lỗi B — Sản phẩm bị detect chẻ đôi/ba:** 1 hộp vật lý bị YOLO detect thành 2-3 box, làm sai
số lượng đếm. Đo IoU giữa các cặp box nghi ngờ (29 candidate, 4 ảnh): IoU gần 0 (0.000-0.03)
xuyên suốt — xác nhận đây là "2 mảnh tách rời của cùng 1 vật" (fragmentation), khác hẳn "2 box
trùng nhau" (duplicate, IoU cao 0.5-0.7, đã gặp riêng). Vì IoU gần 0, sửa bằng chỉnh tham số
`iou` của NMS **không có tác dụng** — NMS chỉ xử lý được case chồng lấn cao.

**Sửa cả 2 lỗi bằng 4 việc**, wiring đúng thứ tự trong `run_scan`:
1. `merge_adjacent_fragments` (`box_merge.py`) — ghép mảnh vỡ dựa trên x-overlap cao + y liền
   kề + aspect ratio bất thường, không dùng row-clustering (2 mảnh của 1 vật có thể khác hàng).
2. `filter_anomalous_boxes` (`box_filter.py`) — lọc box rác quá hẹp so với trung bình hàng.
3. Recalibrate `width_multiplier` của gap detection: 1.5 → 0.9 (số liệu thật cho thấy gap do
   thiếu đúng 1 sản phẩm ≈ 1.0x chiều rộng trung bình, không phải 1.5x như giả định ban đầu).
4. Thứ tự đúng: `merge → filter → detect_gaps`, dùng chung 1 danh sách box đã làm sạch cho cả
   nhánh classify lẫn gap detection.

Kết quả: 92/92 test pass, xác nhận bằng ảnh render thật (gap khớp 100% ô trống thật ở ảnh kệ
sữa; loại đúng gap giả do lon 7Up bị chẻ ở ảnh tủ Pepsi).

**Case ngoài phạm vi phát hiện được lúc test:** ảnh tủ lạnh đặt sát nhau khiến hệ thống detect
lẫn sản phẩm của tủ bên cạnh, gây gap giả ở đúng ranh giới 2 tủ. Đây là giới hạn phạm vi input
("1 ảnh = 1 đơn vị kệ/tủ trọn vẹn"), không phải bug — ghi vào Future Work, xử lý bằng kỷ luật
chụp ảnh chứ không phải thêm code.

## Phần 4 — Giới hạn thật của SigLIP2 zero-shot classification

Test thật lộ ra: SigLIP2 nhầm lẫn nghiêm trọng giữa các SKU có hình dạng bao bì giống nhau —
đặc biệt 2 nhóm khó:
- **Khác hãng, hình dạng giống nhau:** Pepsi/7Up/Mountain Dew (lon hình trụ tương tự)
- **Cùng hãng, khác vị:** Vinamilk có đường vs không đường (bao bì gần như giống hệt)

Số liệu cho thấy 2 SKU cùng hãng khác vị còn giống nhau hơn cả 2 SKU khác hãng trong không
gian embedding (0.926 vs 0.860) — đúng bản chất: cùng brand giữ nguyên bố cục/tông màu, chỉ
khác vài chữ nhỏ mà image-embedding thuần không nắm bắt được.

**Thử fix bằng text-embedding fusion (Task D) — thất bại, dừng đúng lúc:** thêm nhánh text
encoder của SigLIP2 (dùng field `name` có sẵn, không cần cột catalog mới), blend với
image score. Test trên cả tên tiếng Việt lẫn tiếng Anh: cosine similarity ở mức nhiễu
(0.001-0.18), không tách được đúng/sai cho cả 2 nhóm khó, thậm chí làm nhóm (a) tệ hơn. Dừng
hẳn hướng này — không phải bug code, là giới hạn thật của model cho domain/ngôn ngữ này.

**Thử LLM escalation (Claude Haiku 4.5 API) — thành công:** với đúng 2 nhóm khó, cho LLM xem
crop + shortlist candidate, LLM phân loại đúng 100% cho các case thật nằm trong scope demo
(chỉ sai 2/9 case dùng ảnh tủ lạnh UAE để stress-test, do sản phẩm thật — Mountain Dew — không
có trong catalog, ngoài phạm vi demo Việt Nam). Chi phí không đáng kể (~$0.01/lần gọi).

Phát hiện thêm: điều kiện escalate (chỉ dựa khoảng cách top1/top2 sát nhau) chưa đủ — cần kết
hợp ngưỡng điểm tuyệt đối để phân biệt "2 SKU đã biết cạnh tranh nhau" khỏi "sản phẩm ngoài
catalog, không SKU nào khớp tốt".

## Quyết định đang chờ

So sánh 2 hướng dùng LLM:
- **Escalation-only:** SigLIP2 vẫn là lớp chính, LLM chỉ xử lý case mơ hồ — giữ tốc độ, giữ
  tinh thần "chạy local, không phụ thuộc API" của định vị sản phẩm ban đầu.
- **LLM làm chính:** đơn giản hóa kiến trúc, độ chính xác đo được cao hơn hẳn ở đúng chỗ khó —
  đổi lại chậm hơn (vài giây/detection thay vì tức thời), phụ thuộc mạng/API, và cần cân nhắc
  việc này có làm nhạt phần "chứng minh kỹ năng CV tự xây" mà đồ án hướng tới hay không (điểm
  này chỉ Thư biết rõ theo rubric khóa học).

Chưa chốt — đang chờ Thư quyết định hướng nào trước khi Claude Code implement `escalate_to_llm`.

## Việc còn treo (chưa làm)

1. Chốt kiến trúc LLM (escalation-only vs primary) rồi implement `escalate_to_llm` + TDD.
2. Cập nhật `scripts/visualize_scan_e2e.py` để dùng `merge_adjacent_fragments` +
   `filter_anomalous_boxes` mới (hiện tại script slide vẫn dùng box thô, chưa phản ánh pipeline
   đã cải thiện).
3. Sau khi lõi pipeline ổn định, quay lại roadmap Tuần 3-4 (Streamlit/Gradio UI).
