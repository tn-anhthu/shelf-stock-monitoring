# ShelfSense

Trợ lý kiểm kê kệ hàng bằng ảnh chụp, dành cho cửa hàng/siêu thị mini không có ngân sách
lắp camera cố định hay hợp đồng SaaS enterprise.

Nhân viên chụp 1 ảnh mảng kệ bằng điện thoại thường → hệ thống tự khoanh vùng, đếm số
lượng từng sản phẩm, phát hiện sản phẩm sắp hết/hết hàng → hiển thị trên dashboard, không
cần đếm tay hay dò thủ công xem kệ đang thiếu gì.

> Đây là dự án portfolio/học thuật, không phải sản phẩm thương mại thật — mục tiêu là
> luyện tư duy hệ thống + kỹ năng computer vision, không nhắm tạo doanh thu hay chạy
> production thật.

## Vấn đề

Kiểm kê tồn kho trên kệ hiện chủ yếu làm thủ công: nhân viên đếm tay từng sản phẩm, dễ bỏ
sót vị trí trống dẫn đến mất doanh thu, và không có công cụ theo dõi tình trạng kệ hàng nếu
không đầu tư hạ tầng lớn.

Các giải pháp thị trường hiện có (Trax, Simbe Robotics/Tally, Focal Systems, AiFi, Scandit
ShelfView...) giải quyết đúng bài toán này nhưng nhắm vào chuỗi bán lẻ lớn/FMCG enterprise —
cần camera cố định, robot tự hành, hợp đồng dài hạn, hoặc catalog train riêng theo từng
khách hàng. Cửa hàng/siêu thị mini không có ngân sách và quy mô để tiếp cận các giải pháp
này.

**Khác biệt kỹ thuật của ShelfSense:** chỉ cần 1 ảnh chụp bằng điện thoại thường, dùng
zero-shot classification (SigLIP2 retrieval) thay vì train riêng theo catalog của từng cửa
hàng — thêm sản phẩm mới vào catalog không cần train lại model.

## Scope

Giới hạn nhóm hàng FMCG có bao bì (nước giải khát, mì gói, bánh kẹo...), catalog ~15-30 SKU
thật của 1 kệ cụ thể tại 1 siêu thị gần nhà, dùng làm demo target. Chạy local qua
Streamlit/Gradio, lưu trữ bằng SQLite — không deploy public, không dùng cloud DB.

Chi tiết đầy đủ (persona, user stories, acceptance criteria, roadmap) xem
[`docs/specs/2026-07-20-shelfsense-mvp-design.md`](docs/specs/2026-07-20-shelfsense-mvp-design.md).

## Pipeline

1. **Detection** — YOLO nano fine-tune trên SKU-110K để khoanh vùng từng sản phẩm trên ảnh
   kệ (dense/overlapping objects).
2. **Classification** — crop từng box, dùng SigLIP2 embedding zero-shot để match với catalog
   sản phẩm (retrieval-based, không cần train riêng cho từng SKU mới).
3. **Gap detection** — khoanh vùng khoảng trống giữa các sản phẩm đã detect trong cùng 1
   hàng kệ bằng heuristic hình học (so khoảng cách giữa box liền kề với chiều rộng trung
   bình sản phẩm trong hàng).
4. **Depth multiplier (human-in-the-loop)** — nhân viên tự nhập tay số lớp sản phẩm xếp sâu
   phía sau mỗi vị trí (không tự động suy luận độ sâu).
5. **Aggregate & Pricing** — cộng dồn số lượng theo SKU, nhân giá theo catalog → tổng giá
   trị tồn kho, cờ Đủ/Sắp hết/Hết hàng theo ngưỡng từng SKU.
6. **Low-confidence warning** — banner cảnh báo khi confidence trung bình 1 khu vực thấp,
   gợi ý chụp lại (tối đa 1 vòng, không có luồng xác nhận đa bước).

Kết quả AI đề xuất chỉ là draft — chỉ ghi vào tồn kho chính thức sau khi nhân viên xác nhận.

## Trạng thái hiện tại

- [x] **Detection** — benchmark harness (`src/detection/benchmark/`: metrics IoU/precision/
      recall, SKU-110K loader, checkpoint/zero-shot candidates) → cả hai candidate benchmark
      dưới ngưỡng 0.45 → fine-tune YOLO nano riêng (recall 0.782, precision 0.745, ngưỡng
      0.6 đạt). Xem `docs/detection-notes/`.
- [x] **Classification** — benchmark CLIP vs SigLIP2 zero-shot retrieval trên subset RPC —
      SigLIP2 top-1 0.676, top-5 0.952, chọn SigLIP2 cho retrieval. Xem
      `docs/classification-notes/`.
- [x] **Catalog** (`src/catalog/`) — schema SQLite (catalog/inventory/scan_history), parse
      CSV seed, fetch ảnh mẫu từ URL, build + lưu embedding SigLIP2 theo SKU, orchestrator
      seed catalog đầy đủ.
- [x] **Pipeline lõi** (`src/pipeline/`) — classify crop theo catalog, flag low-confidence,
      aggregate số lượng/giá trị/cờ tồn kho, orchestrator `run_scan`/`persist_scan` nối
      detect → classify → confidence → aggregate → ghi SQLite.
- [ ] Gap detection, row clustering, box filtering — đang hoàn thiện.
- [ ] Frontend Streamlit/Gradio (Path 1/2/3) — chưa bắt đầu, theo roadmap là việc của tuần 3-4.
- [ ] Dashboard tổng hợp.

## Setup

- MacBook Pro M4, 16GB RAM — dùng `device='mps'` cho PyTorch/YOLO khi train/infer local.
- Dataset nặng (SKU-110K) nên stream/subset thay vì tải full 13.6GB về máy.
- 3 virtualenv riêng do các bộ dependency ghim version đá nhau (không gộp được vào 1 file
  `requirements.txt` chung):
  - `.venv-benchmark` ← `requirements.txt` (ultralytics 8.0.43, ghim để đọc được checkpoint
    pickle cũ)
  - `.venv-train` ← `requirements-train.txt` (ultralytics ≥8.3, để fine-tune/evaluate)
  - `.venv-e2e` ← `requirements-e2e.txt` (kết hợp YOLO checkpoint-compatible + SigLIP2 chạy
    chung 1 process, cho `scripts/run_scan_e2e.py`)

## Future Work

- Chuẩn hóa tên SKU liên siêu thị / xử lý biến thể tên gọi giữa các nhà bán lẻ.
- Depth-multiplier tự động (suy luận độ sâu từ ảnh) thay vì nhập tay.
- VLM/OCR làm fallback nhận diện cho SKU chưa có trong catalog.
- Continual learning từ feedback người dùng.
- Lịch sử nhiều lần chụp theo thời gian + biểu đồ xu hướng.
- Multi-tenant, deploy cloud, migrate sang Postgres/Supabase khi cần multi-store thật.
