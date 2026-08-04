# ADR-001: Migrate ShelfSense demo layer từ Streamlit/Gradio sang Node.js API + tách frontend

**Status:** Accepted (2026-07-28)
**Liên quan:** Spec gốc, Mục 2 (Trong scope), Mục 6 (Frontend Requirements)

## Context (Bối cảnh)

Spec ban đầu (Mục 2) đã chốt: chạy local qua Streamlit/Gradio, không deploy public.
Kiến trúc này là 1 process Python duy nhất — Streamlit tự vẽ UI và gọi model trong cùng runtime.

Từ lúc chốt spec, phát sinh 1 mục tiêu bổ sung chưa có trong bản gốc: dùng ShelfSense
làm minh chứng năng lực software engineering (JS, API design, testing) để phục vụ hồ sơ
ứng tuyển 1 chương trình training SE. Đây là constraint mới cần đưa vào scope, dẫn tới
việc phải xem lại lựa chọn kiến trúc ban đầu.

## Decision (Quyết định)

Tách kiến trúc thành 2 tầng:

1. **ML service (Python)** — giữ nguyên 100% model logic hiện có, không sửa.
2. **API layer (Node.js/Express)** — đứng giữa ML service và UI, expose 1 endpoint `POST /analyze`.

UI chuyển từ Streamlit (tự vẽ trong cùng process) sang 1 trang HTML/CSS/JS thuần, gọi API qua `fetch`.
Bổ sung test tự động (Jest + Supertest) cho tầng API.

**Không đổi:** vẫn chạy local, KHÔNG deploy public — ràng buộc gốc ở Mục 2 giữ nguyên.
Thay đổi chỉ nằm ở số lượng process nội bộ (1 → 2), không mở rộng scope deploy.

**Trình tự triển khai:** contract-first — chốt JSON schema request/response của `POST /analyze`
trước (dựa theo bảng Feature Spec, mục 4 của spec chính), implement `api` với `ml-service` trả
mock data cố định trước, cho phép `web` phát triển song song không bị chặn bởi 2 backlog CV core
(duplicate detection IoU, LLM verify parallelization) và ROI-crop chưa đóng hẳn ở `ml-service`.
Nối `ml-service` thật vào `api` sau khi backend CV ổn định hơn.

## Rationale (Vì sao)

**Kỹ thuật:**
- Streamlit gắn UI và logic xử lý trong cùng 1 process → khó viết test tự động cho
  phần logic tách biệt khỏi framework UI.
- Tách ra 1 API contract (request/response JSON) rõ ràng tạo điểm mở để sau này gọi
  ShelfSense từ nhiều loại client khác (không chỉ 1 trang demo), nếu sản phẩm mở rộng
  hướng tới tích hợp với hệ thống quản lý kho sẵn có của cửa hàng.
- Kiến trúc 2 tầng gần với pattern thực tế (model-serving layer + application layer)
  hơn 1 script gộp chung UI + logic.

**Không thuần kỹ thuật (nói thẳng):**
- Đây cũng là cơ hội để thực hành JS/API/testing thật trên chính project mình hiểu sâu
  nhất về mặt model — phục vụ mục tiêu học tập song song với mục tiêu sản phẩm. Đây không
  phải lựa chọn thuần kỹ thuật 100%, cần ghi rõ để không tạo hiểu lầm sau này.

## Consequences (Đánh đổi)

- (–) Setup phức tạp hơn: 2 process (Python + Node) thay vì 1, tốn thêm thời gian dev
  so với Streamlit chạy là có UI ngay.
- (–) Thêm 1 lớp network call nội bộ (Node → Python) — thêm 1 điểm có thể lỗi, cần xử lý
  error handling giữa 2 service.
- (+) Có test tự động cho phần logic quan trọng nhất (API contract).
- (+) Có thêm minh chứng năng lực ngoài Computer Vision trong portfolio.
- Scope MVP không đổi: vẫn 1 luồng chính (upload ảnh → trả kết quả), không thêm feature
  mới ngoài việc đổi tầng kiến trúc nội bộ.

## Cấu trúc thư mục (bổ sung 2026-07-28)

`ml-service/` là wrapper MỎNG, KHÔNG di chuyển `src/`, `scripts/`, `tests/` hiện có — giữ đúng
tinh thần "ml-service giữ nguyên 100% model logic, không sửa" ở mục Decision. Cụ thể:

```
shelfsense/            # repo root, không đổi
├── src/                # giữ nguyên chỗ cũ — catalog/, classification/, detection/, pipeline/
├── scripts/            # giữ nguyên — debug/experiment scripts
├── tests/              # giữ nguyên — 169 test hiện có, không sửa import path
├── data/, docs/         # giữ nguyên
├── ml-service/
│   └── app.py          # FastAPI/Flask mỏng, `from src.pipeline.scan import run_scan`
├── api/                 # Node.js/Express
└── web/                 # HTML/CSS/JS thuần
```

Để `ml-service/app.py` import được `src` dù chạy từ đâu: thêm 1 `pyproject.toml`/`setup.cfg`
tối thiểu ở repo root, `pip install -e .`, không sửa nội dung bên trong `src/`. Lý do không gộp
`src`/`scripts` vào trong `ml-service/`: di chuyển file là rủi ro không cần thiết (phá import
path của 169 test đang pass + path reference trong docs/specs/ADR đã viết) để đổi lấy 1 cấu trúc
thư mục gọn hơn về thẩm mỹ — không tương xứng, đặc biệt dưới áp lực rollback/checkpoint đã đặt ra
ở trên.

## Rollback / Checkpoint (bổ sung 2026-07-28)

Mục tiêu phụ (luyện full-stack) không được phép làm trễ mục tiêu chính (demo CV pipeline hoạt
động đúng) — đặt sẵn 1 mốc kiểm tra thay vì để quyết định "có nên bỏ" phát sinh giữa lúc gấp gáp
sát deadline:

- **Mốc kiểm tra:** đầu tuần 5 (~2026-08-17, theo lịch buffer tuần 5 đã có trong spec chính,
  mục 9 các quyết định trước).
- **Điều kiện:** nếu tới mốc này mà `api` + `web` chưa nối được với `ml-service` thật (chỉ chạy
  được với mock data), dừng đầu tư tiếp vào tầng Node/API cho mục đích demo.
- **Fallback:** ưu tiên demo bằng đường ngắn nhất có thể chạy được — kể cả nghĩa là dùng lại 1
  script Python gọi trực tiếp pipeline (không qua Node/API) cho buổi trình bày. Document rõ tầng
  Node/API là "proof of concept kỹ năng, chưa hoàn thiện end-to-end" thay vì cố hoàn thiện bằng
  mọi giá sát deadline và rủi ro cả buổi demo không chạy được gì.
- Đây là cùng nguyên tắc "thứ tự cắt nếu trễ" đã có trong README của project — áp dụng cụ thể
  cho quyết định kiến trúc này.
