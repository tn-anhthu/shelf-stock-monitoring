# ShelfSense

Trợ lý kiểm kê kệ hàng bằng ảnh chụp, dành cho cửa hàng/siêu thị mini không có ngân sách lắp camera cố định hay hợp đồng SaaS enterprise.

Nhân viên chụp 1 ảnh mảng kệ bằng điện thoại thường → hệ thống tự khoanh vùng, đếm số lượng từng sản phẩm, phát hiện sản phẩm sắp hết/hết hàng → hiển thị trên dashboard, khôngcần đếm tay hay dò thủ công xem kệ đang thiếu gì.

> Đây là dự án portfolio, không phải sản phẩm thương mại thật

## 1. Vấn đề

Kiểm kê tồn kho trên kệ hiện chủ yếu làm thủ công: nhân viên đếm tay từng sản phẩm, dễ bỏ sót vị trí trống dẫn đến mất doanh thu, và không có công cụ theo dõi tình trạng kệ hàng nếu không đầu tư hạ tầng lớn.

Các giải pháp thị trường hiện có (Trax, Simbe Robotics/Tally, Focal Systems, AiFi, Scandit ShelfView...) giải quyết đúng bài toán này nhưng nhắm vào chuỗi bán lẻ lớn/FMCG enterprise - cần camera cố định, robot tự hành, hợp đồng dài hạn, hoặc catalog train riêng theo từng khách hàng. Cửa hàng/siêu thị mini không có ngân sách và quy mô để tiếp cận các giải pháp này.

**Khác biệt kỹ thuật của ShelfSense:** chỉ cần 1 ảnh chụp bằng điện thoại thường, dùng zero-shot classification (SigLIP2 retrieval) thay vì train riêng theo catalog của từng cửa hàng - thêm sản phẩm mới vào catalog không cần train lại model, khác với hướng closed-set classifier của nhiều đối thủ enterprise.


## 2. Research Question


**1. Zero-shot embedding retrieval (SigLIP2) có đủ chính xác để thay thế closed-set classifier trong catalog thay đổi liên tục không?**

Đã có câu trả lời một phần. Không hoàn toàn đủ — SigLIP2 nhầm nghiêm trọng giữa các SKU hình dạng bao bì giống nhau (khác hãng: Pepsi/7Up/Mountain Dew; cùng hãng khác vị: Vinamilk có/không đường). Cosine similarity giữa cặp SKU cùng hãng khác vị (0.926) còn cao hơn cặp khác hãng (0.860); bản chất do image-embedding thuần không nắm bắt được khác biệt nhỏ về chữ/nhãn.

**2. Có thể phát hiện khoảng trống kệ (gap) chỉ bằng heuristic hình học, không cần train model riêng, hay không?**

Đã có câu trả lời, đã hiệu chỉnh. Có thể, nhưng ngưỡng ban đầu (1.5× chiều rộng trung bình sản phẩm) sai theo số liệu thật, phải hạ xuống 0.9×; heuristic chỉ hoạt động đúng sau khi thêm bước merge box vỡ (`merge_adjacent_fragments`) và lọc box rác (`filter_anomalous_boxes`) trước khi tính gap.

**3. Khi embedding retrieval không đủ phân biệt, dùng LLM làm lớp verify có khả thi về chi phí/độ chính xác không, và nên escalate có chọn lọc hay verify toàn bộ?**

Đang chỉnh sửa. Đã xác nhận LLM escalation cho kết quả đúng hơn trên case thật trong scope demo, chi phí thấp — khả thi về mặt kỹ thuật. Kiến trúc đã chốt là **LLM verify mọi match** (không chỉ escalation-only), vì điểm số SigLIP2 không đáng tin để tự quyết định "khi nào cần hỏi LLM" — SigLIP2 vẫn giữ vai trò retrieval rút gọn top-K candidate, LLM luôn là bên quyết định cuối. Đánh đổi chính là thời gian (mọi detection đều gọi API), chưa phải chi phí.

**4. Các loại lỗi detection (box bị chẻ, box trùng, box rác) ảnh hưởng thế nào đến độ chính xác đếm số lượng và gap detection, và có cần xử lý khác nhau theo từng loại lỗi không?**

Đang chỉnh sửa. Đo IoU thật trên 29 candidate/4 ảnh xác nhận 2 loại lỗi có bản chất khác nhau: box bị chẻ (fragmentation, IoU ≈ 0.000–0.03) so với box trùng (duplicate, IoU 0.5–0.7) -> cần 2 cách sửa riêng biệt (merge theo x-overlap/y-gap/aspect ratio cho fragmentation; chỉnh tham số `iou` của NMS cho duplicate).

Đối chiếu tài liệu: RQ1 và RQ3 liên quan trực tiếp đến paper #3 (ew-shot recognition) và paper #4 (Enhanced OOS Detection) — cả hai đều đối mặt vấn đề tương tự (phân biệt SKU dễ nhầm, catalog không cố định) và có thể dùng làm cơ sở đối chiếu khi viết phần thảo luận cho báo cáo cuối.

## 3. Scope

Giới hạn nhóm hàng FMCG có bao bì (nước giải khát, mì gói, bánh kẹo...), catalog ~100 SKU thật của 1 kệ cụ thể tại 1 siêu thị tiện lợi, làm demo target. Chạy local qua Streamlit/Gradio, lưu trữ bằng SQLite — không deploy public, không dùng cloud DB.

Chi tiết đầy đủ (persona, user stories, feature spec, acceptance criteria, backend/frontendrequirements) xem
[`docs/specs/mvp-design.md`](docs/specs/mvp-design.md).

## 4. Pipeline

1. **Detection** — YOLOv8 nano fine-tune trên SKU-110K để khoanh vùng từng sản phẩm trên ảnh kệ (dense/overlapping objects).
2. **Classification** — crop từng box, dùng SigLIP2 embedding zero-shot để match với catalog sản phẩm (retrieval-based, không cần train riêng cho từng SKU mới).
3. **Gap detection** — khoanh vùng khoảng trống giữa các sản phẩm đã detect trong cùng 1 hàng kệ bằng heuristic hình học (so khoảng cách giữa box liền kề với chiều rộng trung bình sản phẩm trong hàng).
4. **Depth multiplier (human-in-the-loop)** — nhân viên tự nhập tay số lớp sản phẩm xếp sâu phía sau mỗi vị trí (không tự động suy luận độ sâu).
5. **Aggregate & Pricing** — cộng dồn số lượng theo SKU, nhân giá theo catalog → tổng giá trị tồn kho, cờ Đủ/Sắp hết/Hết hàng theo ngưỡng từng SKU.
6. **Low-confidence warning** — banner cảnh báo khi confidence trung bình 1 khu vực thấp, gợi ý chụp lại (tối đa 1 vòng, không có luồng xác nhận đa bước).

Kết quả AI đề xuất chỉ là draft — chỉ ghi vào tồn kho chính thức sau khi nhân viên xác nhận.

## Roadmap

Roadmap 5 tuần (20/7 → 23/8/2026):

| Tuần | Mục tiêu chính | Deliverable | Rủi ro |
|---|---|---|---|
| 1 (20–26/7) | Catalog + database | Catalog SKU (ảnh, tên, giá, ngưỡng) + schema SQLite + script embedding catalog | Chuẩn bị catalog trễ → giới hạn cứng 15-20 SKU |
| 2 (27/7–2/8) | Ghép pipeline lõi (chưa UI) | Script: ảnh → detect → classify → confidence flag → depth (giả lập) → pricing → ghi SQLite | Rủi ro cao nhất — làm sớm, không dồn cuối |
| 3 (3–9/8) | Frontend Path 1 + Path 2 | Streamlit/Gradio: scan, annotate, bảng kết quả, nhập depth, xác nhận, banner low-confidence | Ưu tiên chạy được trước, đẹp sau |
| 4 (10–16/8) | Frontend Path 3 + Dashboard | Màn thêm SKU, dashboard tổng (bảng, tổng giá trị, cờ) | Có thể rút gọn Path 3 nếu trễ |
| 5 (17–23/8) | Buffer, test, báo cáo | Test end-to-end, sửa bug, (nếu dư) trend chart, demo video, hoàn thiện báo cáo | Buffer bắt buộc, không nhét feature mới |

**Thứ tự cắt nếu trễ tiến độ:** bỏ trend chart (nice-to-have) → rút gọn Path 3 → rút gọn UI Path 2 (giữ logic, bớt UI đẹp). Không cắt Path 1 hay database — đây là xương sống.

## Trạng thái hiện tại

- [x] **Detection** — benchmark harness (`src/detection/benchmark/`: metrics IoU/precision/recall, SKU-110K loader, checkpoint/zero-shot candidates) → cả hai candidate benchmark dưới ngưỡng 0.45 → fine-tune YOLO nano riêng (recall 0.782, precision 0.745, ngưỡng 0.6 đạt). Xem `docs/detection-notes/`.
- [x] **Classification** — benchmark CLIP vs SigLIP2 zero-shot retrieval trên subset RPC — SigLIP2 top-1 0.676, top-5 0.952, chọn SigLIP2 cho retrieval. Xem `docs/classification-notes/`.
- [x] **Catalog** (`src/catalog/`) — schema SQLite (catalog/inventory/scan_history), parse CSV seed, fetch ảnh mẫu từ URL, build + lưu embedding SigLIP2 theo SKU, orchestrator seed catalog đầy đủ.
- [ ] **Pipeline lõi** (`src/pipeline/`) — classify crop theo catalog, flag low-confidence, aggregate số lượng/giá trị/cờ tồn kho, orchestrator `run_scan`/`persist_scan` nối detect → classify → confidence → aggregate → ghi SQLite.
- [x] **Detection post-processing** — merge box vỡ (`merge_adjacent_fragments`), lọc box rác (`filter_anomalous_boxes`), gap detection theo hàng kệ — đã wire vào `run_scan`.
- [ ] **LLM escalation** (RQ3) — experiment harness xong (multi-image reference-photo mode, hỗ trợ input HEIC); production integration (`escalate_to_llm` gắn vào `classify_crop`) đang làm.
- [ ] Frontend Streamlit/Gradio (Path 1/2/3) — chưa bắt đầu, theo roadmap là việc của tuần 3-4.
- [ ] Dashboard tổng hợp.

## Setup

- Dataset nặng (SKU-110K) nên stream/subset.
- 4 virtualenv riêng do các bộ dependency ghim version đá nhau (không gộp được vào 1 file `requirements.txt` chung):
  - `.venv-benchmark` ← `requirements/benchmark.txt` (ultralytics 8.0.43, ghim để đọc được checkpoint pickle cũ)
  - `.venv-train` ← `requirements/train.txt` (ultralytics ≥8.3, để fine-tune/evaluate)
  - `.venv-classify` ← `requirements/classify.txt` (SigLIP2/transformers, cho `src/catalog/build_embeddings.py`)
  - `.venv-e2e` ← `requirements/e2e.txt` (kết hợp YOLO checkpoint-compatible + SigLIP2 chạy chung 1 process, cho `scripts/run_scan_e2e.py`)

## Future Work

- Chuẩn hóa tên SKU liên siêu thị / xử lý biến thể tên gọi giữa các nhà bán lẻ.
- Depth-multiplier tự động (suy luận độ sâu từ ảnh) thay vì nhập tay.
- VLM/OCR làm fallback nhận diện cho SKU chưa có trong catalog.
- Continual learning từ feedback người dùng.
- Lịch sử nhiều lần chụp theo thời gian + biểu đồ xu hướng.
- Multi-tenant, deploy cloud, migrate sang Postgres/Supabase khi cần multi-store thật.
