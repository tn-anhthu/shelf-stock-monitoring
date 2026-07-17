# Design: Classification Benchmark Sprint (Phase 2)

**Ngày:** 2026-07-17
**Trạng thái:** Đã duyệt bởi Anh Thư — sẵn sàng chuyển sang writing-plans
**Phạm vi:** Chỉ phase Classification (Phase 2 trong pipeline 4 bước), tiếp nối sau khi Phase 1
(Detection) đã xong — YOLO nano fine-tune (1a) đạt recall 0.782 trên 50 ảnh eval, đạt ngưỡng
0.6 (xem `docs/detection-notes/2026-07-17-yolo-finetune-results.md`).

## Bối cảnh

README đã chốt hướng cho Phase 2 từ đầu dự án: "crop từng box, dùng VLM embedding zero-shot
(CLIP/SigLIP2) để match với catalog sản phẩm (retrieval-based, không cần train riêng cho từng
SKU mới)". Không cần train (khác Phase 1 phải fine-tune YOLO) — chỉ cần encode catalog 1 lần,
encode crop, so cosine similarity, lấy category gần nhất. Mục tiêu chính của sprint này là chọn
model embedding nào (CLIP hay SigLIP2) dựa trên số liệu thật, không đoán mò.

SKU-110K (dùng ở Phase 1) chỉ có 1 class chung "object" — không có nhãn sản phẩm cụ thể, nên
không dùng được để benchmark classification. Cần nguồn dữ liệu khác vừa làm catalog (ảnh
exemplar sạch từng sản phẩm) vừa làm test set (ảnh scene thật có nhãn category đúng).

## Mục tiêu của sprint này

Quyết định — dựa trên số liệu định lượng — nên dùng CLIP hay SigLIP2 làm embedding model cho
Phase 2, và đo được retrieval accuracy thật là bao nhiêu trước khi tích hợp vào pipeline đầy đủ.

## Ngoài phạm vi (out of scope) của sprint này

- Full 200 category của RPC dataset — sprint này dùng subset nhỏ (~20-30 category) để benchmark
  trước, giống cách Phase 1 dùng subset 50 ảnh SKU-110K trước khi cam kết scale lớn hơn.
- Ảnh kệ hàng Việt Nam thật — vẫn ở Future Work theo README; sprint này dùng RPC (nước ngoài).
- End-to-end nối với detect thật của Phase 1 — benchmark này dùng **ground-truth crop của RPC**,
  không dùng box do YOLO 1a detect ra. Lý do: YOLO 1a chỉ được train/eval trên SKU-110K (ảnh kệ
  dày đặc); chạy nó trên ảnh RPC (checkout counter, domain khác hẳn) sẽ trộn lẫn sai số detect
  với sai số classification, không tách biệt được lỗi nằm ở đâu. End-to-end thật sự chỉ có ý
  nghĩa khi có ảnh kệ hàng Việt Nam thật để cả hai phase cùng chạy trên 1 domain.
- Mở rộng catalog ngoài RPC, Depth multiplier UI, Pricing aggregation — spec riêng sau.

## Setup

- Dataset: RPC (Retail Product Checkout) — có cả exemplar images (ảnh sạch, từng sản phẩm
  riêng, làm catalog) và checkout scene images (nhiều sản phẩm, có ground-truth box + category,
  làm test set). Tên/schema chính xác trên Hugging Face sẽ verify live trước khi code — theo
  đúng nguyên tắc đã áp dụng ở Phase 1 (verify SKU-110K schema thật trước khi giả định).
- Model: `openai/clip-vit-base-patch32` (CLIP) và `google/siglip2-base-patch16-224` (SigLIP2),
  qua Hugging Face `transformers` — tên checkpoint chính xác verify live khi implement.
- Chạy inference bằng `device='mps'` trên MacBook Pro M4, 16GB RAM. Encode-only (không có
  backward pass) nên tải RAM nhẹ hơn nhiều so với training ở Phase 1.
- Code nằm ở `src/classification/benchmark/` (mirror cấu trúc `src/detection/benchmark/`).

## Kiến trúc

```
src/classification/benchmark/
  data.py            — load RPC subset (exemplar catalog images + checkout scene crops +
                        ground-truth category), qua HF `datasets` streaming
  embed_clip.py       — load CLIP, encode ảnh → vector
  embed_siglip2.py    — load SigLIP2, encode ảnh → vector
  catalog.py          — build catalog: encode toàn bộ exemplar images, lưu (category, embedding)
                        theo TỪNG ảnh riêng (không average nhiều exemplar/category) — so khớp
                        theo max-similarity giữa crop và từng catalog embedding, chính xác hơn
                        so với dùng 1 embedding trung bình đại diện cho cả category
  retrieve.py         — cosine similarity giữa crop embedding và toàn bộ catalog → xếp hạng
                        category theo similarity cao nhất → top-1, top-5
  metrics.py          — top-1 accuracy, top-5 accuracy (unit-tested, giống metrics.py detection)
  report.py           — chạy cả CLIP và SigLIP2 trên cùng benchmark, in bảng so sánh
```

Luồng benchmark:
1. Chọn subset ~20-30 category RPC (con số chính xác chốt khi xem thật cấu trúc dataset live).
2. Build catalog: lấy toàn bộ exemplar images của các category đã chọn → encode bằng CLIP,
   encode riêng bằng SigLIP2 (2 catalog embedding set độc lập).
3. Lấy ~50-100 ground-truth crop từ checkout scene images, chỉ thuộc các category đã chọn.
4. Với mỗi crop: encode bằng CLIP → so cosine similarity với catalog CLIP → top-1/top-5
   category. Lặp lại tương tự cho SigLIP2.
5. So top-1/top-5 predicted category với ground-truth category thật → tính accuracy cho cả
   2 model.

## Ngưỡng quyết định (pass/fail)

Đo top-1 accuracy và top-5 accuracy cho cả CLIP và SigLIP2 trên cùng benchmark, báo số liệu
thật cho người quyết định — **không chốt ngưỡng số trước** (khác Phase 1, nơi ngưỡng recall≥0.6
đã biết trước dựa trên baseline benchmark có sẵn; ở đây chưa có baseline tương đương cho
retrieval trên RPC nên sẽ bàn ngưỡng sau khi thấy số liệu thật).

- Model có top-1 accuracy cao hơn rõ rệt → chọn model đó cho Phase 2.
- Nếu 2 model gần bằng nhau → cân nhắc thêm tốc độ inference/ảnh trên M4 (yếu tố phụ).
- Nếu cả 2 đều thấp bất ngờ (vd dưới 0.5) → dừng lại, báo số liệu, bàn hướng tiếp (không tự ý
  mở rộng catalog/đổi model khác mà không có quyết định rõ ràng — theo đúng tinh thần Phase 1).

## Rủi ro đã biết

- Chưa xác nhận RPC có sẵn trên Hugging Face dưới dạng dễ stream như SKU-110K hay không — cần
  verify live đầu tiên trước khi code phần còn lại; nếu không có, cần bàn lại nguồn dataset.
- SigLIP2 là model mới hơn CLIP gốc, một số biến thể/kích cỡ có thể chưa ổn định trên MPS —
  cùng rủi ro "op không hỗ trợ trên MPS" đã gặp ở Phase 1 (Grounding DINO), nhưng encode-only
  (không train) nên rủi ro thấp hơn.
- Benchmark trên RPC (ảnh nước ngoài, đóng gói khác Việt Nam) — kết quả có thể không transfer
  hoàn toàn sang sản phẩm/bao bì Việt Nam thật; đây là lý do "ảnh VN thật" vẫn nằm ở Future Work,
  chưa phải sprint này.

## Kết quả bàn giao (deliverables)

- Script benchmark tái sử dụng được (`src/classification/benchmark/`).
- Bảng số liệu top-1/top-5 accuracy cho CLIP và SigLIP2.
- Quyết định bằng văn bản: chọn CLIP hay SigLIP2 cho phần còn lại của Phase 2.

## Testing

- Unit test cho hàm tính top-1/top-5 accuracy (so với 1 bộ dự đoán giả lập biết trước đáp số).
- Unit test cho hàm cosine similarity / retrieve (đảm bảo xếp hạng đúng thứ tự).
- Kiểm tra thủ công: in ra vài crop kèm top-5 category dự đoán cạnh ảnh exemplar catalog tương
  ứng, xác nhận bằng mắt kết quả hợp lý (tránh bug âm thầm giống cách Phase 1 dùng
  visual overlay sanity-check).

## Bước tiếp theo sau spec này

Sau khi sprint benchmark này xong và có quyết định (CLIP/SigLIP2), viết spec kế tiếp cho phần
còn lại của Phase 2 (tích hợp catalog thật, hoặc mở rộng nếu accuracy chưa đủ), hoặc bắt đầu
spec cho Phase 3 (Depth multiplier) nếu Phase 2 coi như xong.
