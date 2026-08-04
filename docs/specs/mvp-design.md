# ShelfSense MVP — Design Spec

## 1. Persona

**Nhân viên cửa hàng/siêu thị mini**: được giao nhiệm vụ kiểm kê kệ hàng định kỳ, dùng điện thoại công ty, không rành công nghệ. Không phải PM/data scientist.

Vai phụ: **Admin/quản lý cửa hàng**, người thêm sản phẩm mới vào catalog khi nhập hàng.

## 2. Scope

### Trong scope (MVP bắt buộc)
- 1 ảnh chụp toàn bộ 1 mảng kệ (nhiều hàng, nhiều SKU sát nhau — giống ảnh SKU-110K/ảnh thực tế, không phải 1 ngăn đơn lẻ)
- Giới hạn nhóm hàng: FMCG có bao bì (nước giải khát, mì gói, bánh kẹo...) — không mở rộng sang quần áo, đồ gia dụng không bao bì
- Catalog ~100 SKU thật của 1 kệ cụ thể tại 1 siêu thị tiện lợi, dùng làm demo target (không phải SKU tự chọn ngẫu nhiên) — nguồn ảnh vẫn crawl từ web (thương mại điện tử/trang thương hiệu) cho từng SKU đã ghi nhận tại kệ, không tự chụp, không dùng ảnh AI generate
- Depth-multiplier: nhân viên tự nhập tay số lớp phía sau (không tự động suy luận)
- HITL: 1 banner cảnh báo tĩnh khi confidence thấp, tối đa 1 vòng chụp lại — không có luồng xác nhận đa bước
- Edge-crop warning (2026-07-28): sau detect, nếu có box sản phẩm chạm sát mép ảnh (dấu hiệu sản phẩm bị cắt cụt ngoài khung — thường xảy ra khi kệ quá to, nhân viên không lùi được nữa) → dùng chung cơ chế banner cảnh báo với low-confidence (mục 5, Path 2), gợi ý chụp lại lùi xa hơn hoặc chụp thêm phần còn lại. Đây là bản post-capture (kiểm tra SAU khi chụp, tái dùng pipeline detect có sẵn) — cân nhắc và loại phương án khung overlay hiển thị lúc đang chụp vì Streamlit không hỗ trợ overlay lên camera preview mặc định, cần build custom component thêm, rủi ro timeline không đáng cho tính năng phụ trợ (không phải core detection logic)
- Gap detection: khoanh vùng khoảng trống giữa các sản phẩm đã detect trong cùng 1 hàng kệ bằng heuristic hình học (so khoảng cách giữa 2 box liền kề với chiều rộng trung bình sản phẩm trong hàng) — không train model riêng cho "khoảng trống". Quyết định 2026-07-21: nâng từ nice-to-have lên core, đánh đổi risk timeline có ý thức (xem docs/reports/week-01/2026-07-21.md)
- ROI-crop preprocessing (2026-07-28 — ĐÃ CHỐT, dừng đầu tư thêm): trước khi đưa ảnh vào YOLO, cắt/loại bỏ vùng nền và kệ hàng xóm nằm trọn trong khung hình (khác với edge-crop warning — vấn đề này là "chụp thừa", không phải "chụp thiếu"). Quyết định nâng lên core sau khi test tay xác nhận cơ chế: crop sạch nền trên 4/5 ảnh test → cả 2 lỗi detect box thừa rìa VÀ gap giả nối 2 kệ đều biến mất đồng thời. Implement CLIPSeg zero-shot (`src/pipeline/roi_crop.py`) đạt 3/5 ảnh, threshold benchmark chọn 0.55 (avg IoU 0.795 so ground-truth từ crop tay). 2/5 ảnh còn fail (test2, test5 — cả 2 đều là kệ đảo/kệ trưng bày độc lập, có kệ khác/dãy hàng khác cùng chiều cao mắt người ở 2 bên khung hình): xác nhận **không phải lỗi threshold**, mà là giới hạn cấu trúc của semantic segmentation — CLIPSeg chỉ trả lời được "pixel này có phải shelf không" (đúng cho cả kệ mục tiêu lẫn kệ hàng xóm), không trả lời được "pixel này thuộc kệ nào đang được nhắm chụp" (cần tín hiệu không gian/độ sâu, ngữ nghĩa text không đủ).
  Vòng cuối (kết hợp center-bias + độ nét Laplacian để chọn đúng connected component): trước khi implement, đo trực tiếp xem test2/test5 có từng sinh ≥2 component để mà chọn không — quét threshold 0.35–0.80 (rộng hơn hẳn dải benchmark), **mọi ảnh mọi threshold luôn ≤1 component ≥2% diện tích ảnh, không bao giờ tách 2 mảnh** (xem `docs/log-figures/2026-07-28-roi-crop-component-selection.md`). Kết luận: vấn đề nằm ở tầng mask (2 kệ dính liền do không có khoảng sàn/trần ngăn cách trong khung), bước chọn component ở SAU mask không có gì để chọn nên không thể sửa được — đã implement đầy đủ cơ chế (`list_connected_components`, `center_bias_score`, `laplacian_sharpness`, `select_best_component`, trọng số mặc định bằng nhau 1:1:1 vì không có candidate thật nào để đo trọng số tối ưu) và chạy lại trên cả 5 ảnh gốc: bbox **giống hệt 100%** so với trước, xác nhận đúng dự đoán.
  **Quyết định cuối: DỪNG đầu tư thêm vào ROI-crop** (không tinh chỉnh prompt thêm, không thêm tín hiệu thứ 3) — coi đây là tính năng "giảm rủi ro" (3/5 ảnh demo, 60%), không phải "giải quyết triệt để", dựa vào edge-crop warning + kỷ luật chụp ảnh làm lưới an toàn thứ hai cho 2 case còn lại. Vì demo cần nhận ảnh live, bước crop phải tự động, có fallback nếu segmentation không chắc chắn (mask quá nhỏ/rỗng/không tìm được connected component hợp lý): bỏ qua bước crop, dùng ảnh gốc — không chặn luồng scan. Lưu ý: fallback hiện tại KHÔNG bắt được case test2/test5 vì mask vẫn "hợp lệ" về mặt kỹ thuật (không rỗng, không quá nhỏ) — chỉ là gộp nhầm 2 kệ, cần biết trước khi coi tính năng này production-ready.
- Kiến trúc 3 tầng, đổi từ Streamlit/Gradio ban đầu — xem quyết định đầy đủ + rationale +
  rollback/checkpoint ở `docs/adr/0001-migrate-node-api-frontend.md`: `ml-service` (Python,
  Flask/FastAPI, `POST /predict` — chứa toàn bộ pipeline CV: ROI-crop, YOLO, SigLIP2, LLM
  verify, gap detection, không đổi logic hiện có); `api` (Node.js/Express, `POST /analyze`,
  giữ MỎNG — chỉ proxy + validate + format JSON, không lặp business logic, có test
  Jest/supertest); `web` (HTML/CSS/JS thuần, gọi `api` qua `fetch`).
- Không deploy public (giữ nguyên quyết định gốc — ADR-001 chỉ đổi số lượng process nội bộ,
  không mở rộng scope deploy)
- Lưu trữ bằng SQLite (file local)

### Ngoài scope (Future Work)
- Continual learning từ feedback người dùng
- OCR trên bao bì để phân biệt flavor/biến thể cùng brand
- VLM và OCR làm fallback nhận diện cho SKU chưa có trong catalog — đã cân nhắc 2026-07-21, quyết định gác lại: VLM tốn cost/latency và chưa giải quyết được phần giá/ngưỡng đầy kệ (SKU chưa có trong catalog vẫn thiếu metadata này dù nhận diện đúng tên); OCR có tiềm năng nhưng rủi ro accuracy trên ảnh kệ thật khác điều kiện ảnh catalog sạch — để dành làm nếu dư thời gian ở tuần 5, không phải cam kết bắt buộc
- Chuẩn hóa tên SKU liên siêu thị / xử lý biến thể tên gọi giữa các nhà bán lẻ
- Depth-multiplier tự động (suy luận độ sâu từ ảnh)
- Multi-tenant, deploy cloud, migrate sang Postgres/Supabase khi cần multi-store thật
- Lịch sử nhiều lần chụp theo thời gian + biểu đồ xu hướng — **nice-to-have**, chỉ làm nếu dư thời gian ở tuần 5, không phải cam kết bắt buộc
- Nhận diện ranh giới giữa nhiều đơn vị kệ/tủ khác nhau trong cùng 1 ảnh (ví dụ 2 tủ lạnh đặt sát nhau, ảnh vô tình lấy lẫn sản phẩm của tủ bên cạnh) — phát hiện 2026-07-21 khi stress-test gap detection trên ảnh tủ lạnh nước ngọt (xem docs/reports/week-01/2026-07-21.md). Input giả định của toàn hệ thống là "1 ảnh = đúng 1 đơn vị kệ/tủ trọn vẹn" (mục 2, dòng đầu) — ảnh lấn sang đơn vị khác là ngoài giả định này, không phải bug cần vá bằng thêm heuristic. Xử lý bằng kỷ luật chụp ảnh (nhân viên chụp đúng khung 1 tủ), hỗ trợ thêm bằng edge-crop warning (mục 2, Trong scope) để giảm rủi ro chụp lấn/chụp thiếu.
- Multi-segment capture chính thức (kệ quá to phải chụp thành nhiều ảnh nối tiếp, hệ thống tự cộng dồn/khai báo các ảnh thuộc cùng 1 kệ) — quyết định 2026-07-28: MVP giữ nguyên giả định "1 ảnh = 1 đơn vị kệ trọn vẹn" ở trên, KHÔNG build luồng khai báo/gộp nhiều ảnh thành 1 kệ. Nếu kệ quá to, nhân viên tự chụp nhiều ảnh và xác nhận riêng như các lần scan độc lập — chấp nhận rủi ro double-count nếu 2 ảnh chồng lấn vùng chụp, giảm thiểu bằng hướng dẫn "chụp nối tiếp, không chồng lấn" (không phải cơ chế tự động). Ghép ảnh thật (panorama/stitching) trước khi detect cũng bị loại — thêm hẳn 1 pipeline con (feature matching, warping, blending), rủi ro cao nhất cho timeline 6 tuần, không cân xứng với lợi ích.

## 3. User Stories

- Là nhân viên cửa hàng, tôi chụp 1 ảnh mảng kệ hàng bằng điện thoại → hệ thống tự khoanh vùng và đếm số lượng từng sản phẩm, để tôi không phải đếm tay.
- Là nhân viên cửa hàng, tôi thấy sản phẩm nào bị đánh dấu "sắp hết/hết hàng" trên dashboard → tôi biết ngay cần bổ sung sản phẩm gì.
- Là nhân viên cửa hàng, khi ảnh chụp không rõ → tôi nhận cảnh báo "nên chụp lại" thay vì hệ thống báo sai số liệu.
- Là nhân viên cửa hàng, khi ảnh có sản phẩm bị cắt cụt sát mép (do kệ quá to, không lùi được nữa) → tôi nhận cảnh báo để chụp lại hoặc chụp thêm phần còn lại, thay vì hệ thống âm thầm đếm thiếu.
- Là admin, tôi thêm 1 sản phẩm mới (ảnh mẫu + tên + giá) vào catalog khi cửa hàng nhập hàng mới → hệ thống nhận diện được sản phẩm đó ở lần chụp tiếp theo, không cần train lại model.
- Là nhân viên cửa hàng, tôi nhập tay số lớp sản phẩm xếp phía sau mỗi vị trí → hệ thống tính đúng hơn tổng số lượng thực tế.

## 4. Feature Spec

| Feature | Mô tả | Input | Output |
|---|---|---|---|
| ROI-crop preprocessing | Loại bỏ nền/kệ hàng xóm nằm trọn trong khung trước khi detect | Ảnh gốc | Ảnh đã crop theo ROI (hoặc ảnh gốc nếu segmentation không chắc chắn — xem mục 7) |
| Upload & Detect | Nhân viên upload 1 ảnh mảng kệ | Ảnh JPG/PNG (đã qua ROI-crop) | Danh sách box tọa độ (YOLO) |
| Classify | Mỗi box được match với catalog | Box crop + catalog embeddings | Tên SKU + confidence, hoặc `unknown` nếu confidence của box đó dưới ngưỡng riêng (không ép match SKU sai) |
| Depth input | Nhân viên nhập số lớp sau mỗi vị trí | Số nguyên (mặc định = 1) | Số lượng thực tế = facing × depth |
| Aggregate & Price | Cộng dồn theo SKU, nhân giá | SKU đã đếm + catalog giá | Bảng SKU/số lượng/thành tiền/tổng |
| Low-stock flag | So với ngưỡng "đầy kệ" mỗi SKU | Số lượng vs ngưỡng | Cờ: Đủ / Sắp hết / Hết hàng (áp dụng cho MỌI SKU trong catalog, kể cả SKU 0 lần detect — xem docs/reports/week-01/2026-07-21.md) |
| Gap detection | Khoanh vùng trống giữa 2 sản phẩm liền kề cùng hàng kệ | Danh sách box đã detect | Danh sách box "khoảng trống" (tọa độ), tách biệt với box sản phẩm |
| Low-confidence warning | Confidence trung bình khu vực < ngưỡng | Confidence scores | Banner "nên chụp lại khu vực X" |
| Edge-crop warning | Box sản phẩm chạm sát mép ảnh sau detect | Tọa độ box + kích thước ảnh | Banner "ảnh có thể bị cắt cụt sản phẩm ở rìa, chụp lại hoặc chụp thêm phần còn lại" (dùng chung cơ chế banner với Low-confidence warning) |
| Add new SKU | Admin thêm sản phẩm mới vào catalog | 1-2 ảnh mẫu + tên + giá | Catalog cập nhật (embedding mới) |
| Dashboard | Hiển thị ảnh có box + bảng kết quả | — | Giao diện `web` (HTML/React), dữ liệu lấy từ `api` |

## 5. Acceptance Criteria

### Path 1 — Scan kệ hàng (happy path)
- Nhân viên chọn "Chụp/Upload ảnh" và chọn 1 ảnh mảng kệ
- Sau upload, hiển thị ảnh gốc + loading state trong lúc detect + classify
- Kết quả trả về: ảnh có box khoanh, danh sách SKU nhận diện kèm confidence
- Nhân viên nhập depth (mặc định = 1) cho từng vị trí trước khi xác nhận
- Sau khi bấm "Xác nhận", hệ thống lưu kết quả vào bảng tồn kho hiện tại và cập nhật dashboard ngay

### Path 2 — Khu vực nhận diện kém (low-confidence hoặc edge-crop)
- Nếu confidence trung bình 1 khu vực dưới ngưỡng, HOẶC có box sản phẩm chạm sát mép ảnh
  (nghi bị cắt cụt), hệ thống không tự động lưu số liệu khu vực đó
- Hiển thị banner theo khu vực: "Khu vực X chưa rõ, nên chụp lại" (low-confidence) hoặc "Ảnh có thể bị cắt cụt sản phẩm ở rìa, nên chụp lại hoặc chụp thêm phần còn lại" (edge-crop), kèm nút "Chụp lại khu vực này"
- Nhân viên có thể bỏ qua cảnh báo và xác nhận số liệu hiện có
- Chỉ cho phép 1 vòng chụp lại — không lặp lại nhiều lần cho cùng khu vực

### Path 3 — Thêm SKU mới (admin/catalog)
- Admin vào "Quản lý catalog" → "Thêm sản phẩm"
- Nhập tên, giá, ngưỡng đầy kệ, upload 1-2 ảnh mẫu
- Sau khi submit và backend tính xong embedding, sản phẩm mới xuất hiện trong catalog
- Từ lần scan tiếp theo, sản phẩm mới có thể được nhận diện mà không cần deploy lại model

### General A/C (All Paths)
- Mỗi lần scan lưu kèm timestamp và ảnh gốc để truy vết
- Kết quả chỉ tính là "tồn kho chính thức" sau khi nhân viên xác nhận — số liệu AI đề xuất trước đó chỉ là draft, không tự ghi đè
- Catalog dùng để classify là bản mới nhất tại thời điểm scan
- Mọi lần scan (thành công/cảnh báo/lỗi) đều được log ở backend

## 6. Frontend Requirements

**Kiến trúc:** `web` gọi `api` (Node/Express, `POST /analyze`) qua HTTP, `api` gọi `ml-service`
(Python, `POST /predict`). Xem đầy đủ quyết định, rationale, và mốc rollback/checkpoint ở
`docs/adr/0001-migrate-node-api-frontend.md`. Trình tự triển khai: contract-first (chốt JSON
schema trước, `ml-service` trả mock data ban đầu để `web` không bị chặn bởi backlog CV chưa
đóng), nối `ml-service` thật vào sau.

- **Entry point Path 1:** trang chính "Scan kệ hàng", nút Upload, kết quả annotate hiển thị ngay trên cùng màn hình
- **Entry point Path 2:** lồng trong kết quả của Path 1, banner nằm ngay trên/dưới khu vực bị flag
- **Entry point Path 3:** trang riêng "Quản lý catalog", truy cập từ menu

**Confirmation Acceptance** *(bước người dùng xác nhận kết quả AI trước khi ghi nhận chính thức)*:
- Hiển thị rõ kết quả là "đề xuất, chưa lưu" cho đến khi xác nhận
- Bắt buộc xác nhận/sửa số liệu trước khi lưu vào tồn kho
- Có cảnh báo confidence thấp (Path 2) vẫn cho phép xác nhận không cần chụp lại

**Post UI** *(trạng thái sau khi xác nhận xong)*:
- Dashboard cập nhật ngay: bảng số lượng theo SKU, tổng giá trị tồn kho, cờ Sắp hết/Hết hàng
- Ảnh annotate + thời điểm scan lưu vào lịch sử (nếu làm phần nice-to-have)
- Giao diện phản ánh ngay catalog mới nếu vừa thêm SKU ở Path 3

## 7. Backend Requirements

**Eligibility & Validation:** validate ảnh upload hợp lệ; validate catalog không rỗng trước khi cho phép scan.

**ROI-Crop Preprocessing (2026-07-28):** trước khi gọi YOLO, chạy segmentation zero-shot (CLIPSeg, prompt theo loại vùng cần giữ/loại bỏ) trên ảnh gốc để tạo ROI mask, lấy connected component lớn nhất, crop ảnh về vùng đó. Validated bằng test tay thủ công trên 5 ảnh demo: 4/5 ảnh đạt "0 box thừa rìa, 0 gap giả" sau khi crop sạch nền — xác nhận cơ chế đúng. 1/5 ảnh (kệ chụp nghiêng phối cảnh, viền kệ là hình thang không phải chữ nhật) cần theo dõi thêm: nếu crop hình chữ nhật đơn giản không đủ (cắt sâu vẫn để lọt nền hoặc cắt hụt sản phẩm thật), cần polygon mask theo đúng contour thay vì bounding-box crop — quyết định cụ thể chờ thêm 1 vòng test. Ngưỡng/tham số segmentation cần benchmark riêng trước khi chốt, không đoán số. Nếu mask không chắc chắn (rỗng/quá nhỏ/không có connected component hợp lý) → fallback dùng ảnh gốc, không chặn luồng scan (tránh single point of failure lên toàn bộ Path 1).

**Detection & Classification Processing:** YOLO detect → danh sách box; mỗi box chạy SigLIP2 embedding + retrieval so với catalog hiện tại → SKU + confidence; nếu confidence cao nhất của 1 box dưới ngưỡng riêng cho từng box (per-detection threshold, tách biệt với ngưỡng low-confidence trung bình khu vực) → gán `unknown` thay vì SKU sai, không tính vào aggregate quantities/value; tính confidence trung bình theo khu vực để xác định flag low-confidence.

**Confirmation Handling:** nhận input xác nhận/sửa từ frontend (gồm depth nhập tay); chỉ ghi vào bảng tồn kho chính thức sau khi xác nhận; số lượng thực tế = facing × depth.

**Threshold & Flagging Handling:** so sánh số lượng đã xác nhận với ngưỡng đầy kệ của từng SKU → gán cờ Đủ/Sắp hết/Hết hàng; cập nhật giá trị tồn kho = số lượng × giá.

**Catalog Management (Path 3):** endpoint thêm SKU mới — nhận ảnh mẫu + metadata → tính embedding bằng đúng pipeline SigLIP2 benchmark (`embed_siglip2`) → lưu vào catalog store; catalog store đọc mới nhất mỗi lần scan, không cache cứng.

**Gap Detection Processing:** sau detect, gom box theo hàng kệ (cluster theo y-center); trong mỗi hàng, so khoảng cách giữa 2 box liền kề với chiều rộng trung bình sản phẩm của hàng (fallback
median toàn ảnh nếu hàng có 0-1 box) → nếu vượt ngưỡng tỉ lệ → flag vùng đó là gap. Không flag khoảng trống ở đầu/cuối hàng (trước box đầu, sau box cuối) — không đủ căn cứ phân biệt rìa kệ với hết hàng thật.

**Edge-Crop Warning Processing (2026-07-28):** sau detect, kiểm tra từng box sản phẩm — nếu cạnh box nằm trong ngưỡng N pixel (giá trị cụ thể cần benchmark, đề xuất bắt đầu ~2-3% chiều rộng/cao ảnh) tính từ mép ảnh tương ứng (trái/phải/trên/dưới) → đánh dấu box đó là "edge-crop suspect". Nếu 1 khu vực có ≥1 box edge-crop suspect → trigger cùng banner cảnh báo với low-confidence (mục 5, Path 2). Đây là kiểm tra hình học đơn giản trên bounding box đã có sẵn sau detect, không cần model/heuristic mới — tái dùng toàn bộ pipeline detect hiện tại. Quyết định 2026-07-28: chọn hướng post-capture (kiểm tra sau khi chụp) thay vì khung overlay hiển thị lúc đang chụp (live camera guide-frame), vì Streamlit không có sẵn cơ chế overlay lên camera preview, chi phí xây dựng component riêng không tương xứng lợi ích trong timeline 6 tuần.

**Logging & Observability:** log mỗi lần scan (ảnh gốc, kết quả detect/classify, xác nhận cuối, timestamp); log riêng các trường hợp low-confidence và thêm SKU mới.

**Lưu trữ:** SQLite (file `.db` local) — không dùng Supabase/cloud DB vì app chạy local, không cần multi-user/auth/network. Gồm 3 bảng chính:
- `catalog` — sku_id, tên, giá, ngưỡng đầy kệ, đường dẫn ảnh mẫu, embedding
- `inventory` — bản ghi tồn kho đã xác nhận (sku_id, số lượng, giá trị, thời điểm scan)
- `scan_history` — log từng lần scan (ảnh gốc, kết quả thô, xác nhận cuối, timestamp)

Kiến trúc bảng SQL này cho phép migrate sang Postgres/Supabase sau này nếu cần multi-tenant thật (ghi vào Future Work).

## 8. Catalog — hướng dẫn thu thập ảnh mẫu

- Nguồn: ảnh thật crawl từ web (Shopee/Tiki/trang thương hiệu) — **không tự chụp**, **không dùng ảnh AI generate** (rủi ro sai lệch bao bì làm giảm độ chính xác retrieval)
- Số lượng: 2-3 ảnh/SKU, theo đúng tỷ lệ đã dùng ở benchmark Phase 2 (RPC: 48 ảnh/16 category ≈ 3 ảnh/category)
- Tiêu chuẩn ảnh: 1 sản phẩm/ảnh, nền đơn giản, đủ sáng, thẳng mặt trước, nhãn đọc rõ — giống ảnh sản phẩm e-commerce, khác với ảnh chụp cả mảng kệ dùng lúc scan thật
- Thông tin cần thu thập mỗi SKU: tên nội bộ (tự đặt, không cần khớp cách hiển thị của bất kỳ siêu thị thật nào), giá tham khảo, ngưỡng đầy kệ (số lượng tự định nghĩa), 2-3 ảnh mẫu


> Lưu ý 2026-07-29: catalog hiện đã lên ~140 SKU (con số "~100 SKU" ở mục 2 chưa được cập nhật lại — cần thống nhất số thật trước khi sửa, chưa sửa trong lần cập nhật này).

## 9. Evaluation — Classification Phase (Định nghĩa Done)

Phạm vi: đánh giá riêng phase classify (SigLIP2 zero-shot retrieval trên catalog + Gemini escalation cho case `unknown`). Detection (SKU-110k model) đã frozen, không nằm trong phạm vi đánh giá này — quy trình chi tiết xem plan riêng `docs/superpowers/plans/2026-07-29-classification-eval.md`.

**Test set:**
- ~45-50 ảnh mảng kệ thật, đa dạng ánh sáng/góc/loại kệ
- ~80-85% ảnh chứa sản phẩm nằm trong catalog hiện có; ~15-20% ảnh cố ý chứa sản phẩm KHÔNG có trong catalog (test khả năng nhận biết "unknown" thay vì match nhầm)
- Từ crop sinh ra bởi detection, random subsample ~7-8 crop/ảnh → tổng ~300-400 crop label tay (không label hết mọi crop trong ảnh — không cần thiết cho độ chính xác thống kê ở quy mô MVP)
- Label qua Roboflow, project loại Single-Label Classification (không phải Object Detection)

**Metrics (tách riêng theo lớp, không gộp thành 1 con số accuracy tổng):**
- SigLIP2 top-1 accuracy trên crop hợp lệ, sản phẩm có trong catalog
- Escalation rate (% crop bị đẩy lên Gemini)
- Gemini accuracy trên phần đã escalate
- End-to-end classification accuracy (SigLIP2 đúng trực tiếp + Gemini đúng khi escalate)
- **Silent wrong-match rate** trên nhóm sản phẩm ngoài catalog — % bị gán nhầm thành 1 SKU có sẵn thay vì đúng ra phải trả `unknown`/escalate. Đây là failure mode nguy hiểm nhất (báo sai out-of-stock một cách "tự tin"), phải theo dõi riêng, không được pha vào accuracy chung.
- Crop lỗi do detection (merge nhiều SKU trong 1 box, hoặc detect nhầm vùng ngoài kệ) — loại khỏi mẫu số accuracy classification, chỉ report riêng tần suất xuất hiện (đây là lỗi của phase detection đã frozen, không phải lỗi classification)
- Latency: trung bình + **p95** toàn pipeline (detect → SigLIP2 match → Gemini escalation nếu có) mỗi lần scan

**Definition of Done (MVP) — TBD, cần em set số cụ thể trước khi chạy eval:**
- [ ] End-to-end classification accuracy ≥ ___%
- [ ] Silent wrong-match rate ≤ ___%
- [ ] p95 latency ≤ 1 phút (ngân sách đã thống nhất 2026-07-29)
- [ ] Escalation rate nằm trong ngân sách cost chấp nhận được (cost/lần gọi Gemini 3.5 Flash-Lite hiện đã xác nhận rẻ, chưa phải ràng buộc chặt)

Đạt đủ các ngưỡng trên → dừng tune, coi classification phase production-ready cho MVP, chuyển sang thu thập feedback thật từ production thay vì tiếp tục tối ưu trên test set nội bộ.
