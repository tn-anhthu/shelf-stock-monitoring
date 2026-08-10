# ADR-003: Chuyển `web` từ HTML/CSS/JS thuần sang React + Vite + Tailwind

**Status:** Accepted (2026-07-29)
**Liên quan:** [ADR-001](0001-migrate-node-api-frontend.md) (sửa đổi 1 phần quyết định UI), [ADR-002](0002-analyze-endpoint-schema.md) (schema `POST /analyze` giữ nguyên)

## Context

ADR-001 chốt `web` là "1 trang HTML/CSS/JS thuần, gọi API qua fetch", phù hợp khi `web` chỉ có 1 form + 2 bảng kết quả tĩnh. Scope `web` giờ mở rộng thành wizard 4 bước (Upload → Crop → Edit → Confirm), có state chuyển tiếp giữa các bước (ảnh gốc, ảnh đã crop, kết quả `/analyze`, bảng `quantities` đang sửa dở), và sẽ có component dùng lại ở nhiều trang khi Dashboard/Landing được thêm ở các spec sau (sidebar, card, bảng editable). Quản lý state này bằng tay trong vanilla JS (DOM query + gán lại `innerHTML` mỗi bước) sẽ khó bảo trì hơn khi số bước và số component dùng chung tăng lên.

## Decision

Đổi `web` sang React + Vite + Tailwind CSS. Đây là sửa đổi 1 phần quyết định UI ở ADR-001 (giữ nguyên phần "tách frontend khỏi ml-service/api", đổi phần "HTML/CSS/JS thuần" thành React). `api`/`ml-service` không đổi. `api/src/app.js` tiếp tục serve build output tĩnh của `web` (giờ là `web/dist` sau `vite build`) qua `express.static`.

Không thêm React Router ở lần này, vì mới có 1 trang (Scan), route/switch trang bằng state đơn giản là đủ, tránh 1 lớp trừu tượng chưa cần dùng.

## Rationale

**Kỹ thuật:**
- Wizard 4 bước có state chuyển tiếp giữa các bước (ảnh, kết quả phân tích, bảng đang sửa), React state/props quản lý luồng này rõ ràng hơn thao tác DOM tay.
- Các trang sau (Dashboard, Landing) sẽ dùng lại sidebar, card, bảng editable, nên tách component ngay từ đầu để tránh phải viết lại khi thêm trang.
- Tailwind cho tốc độ style nhanh hơn viết CSS thuần tay cho nhiều component/trạng thái UI (loading, error, disabled, banner) so với `style.css` hiện tại.

**Không thuần kỹ thuật:**
- Tiếp tục phục vụ mục tiêu portfolio song song mục tiêu sản phẩm. React/Vite/Tailwind là bộ công cụ frontend phổ biến, không phải lựa chọn kỹ thuật thuần.

## Consequences

- (–) Thêm 1 bước build (`vite build`) trước khi `api` serve được `web`, trong khi vanilla trước đây chạy thẳng không cần build.
- (–) Thêm `node_modules`/dependency cho `web` (trước đây `web` không có `package.json`).
- (+) State quản lý tập trung, dễ mở rộng khi thêm bước/trang.
- (+) Component tái dùng được cho Dashboard/Landing (ngoài scope lần này).
- Không đổi: contract `POST /analyze` (ADR-002), kiến trúc 3 tầng ml-service/api/web (ADR-001), không deploy public.
