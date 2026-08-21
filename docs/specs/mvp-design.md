# ShelfSense MVP: Design Spec

## 1. Persona

**Nhân viên cửa hàng/siêu thị mini**: được giao nhiệm vụ kiểm kê kệ hàng định kỳ, dùng điện thoại công ty, không rành công nghệ. Không phải PM/data scientist.

## 2. Scope

### Trong scope (MVP bắt buộc)
- 1 ảnh chụp toàn bộ 1 mảng kệ (nhiều hàng, nhiều SKU sát nhau, giống ảnh SKU-110K/ảnh thực tế, không phải 1 ngăn đơn lẻ)
- Giới hạn nhóm hàng: FMCG có bao bì (nước giải khát, mì gói, bánh kẹo...), không mở rộng sang quần áo, đồ gia dụng không bao bì
- Catalog 144 SKU thật của 1 kệ cụ thể tại 1 siêu thị tiện lợi, dùng làm demo target (không phải SKU tự chọn ngẫu nhiên). Nguồn ảnh vẫn crawl từ web (thương mại điện tử/trang thương hiệu) cho từng SKU đã ghi nhận tại kệ, không tự chụp, không dùng ảnh AI generate
- Quantity: nhân viên tự nhập tay số lượng sản phẩm
- Gap detection: khoanh vùng khoảng trống giữa các sản phẩm đã detect trong cùng 1 hàng kệ bằng heuristic hình học (so khoảng cách giữa 2 box liền kề với chiều rộng trung bình sản phẩm trong hàng), không train model riêng cho "khoảng trống". Quyết định 2026-07-21: nâng từ nice-to-have lên core, đánh đổi risk timeline có ý thức (xem docs/reports/week-01/2026-07-21.md)
- Kiến trúc 3 tầng, đổi từ Streamlit/Gradio ban đầu. Xem quyết định đầy đủ + rationale + rollback/checkpoint ở `docs/adr/0001-migrate-node-api-frontend.md`: `ml-service` (Python, Flask/FastAPI, `POST /predict`, chứa toàn bộ pipeline CV: YOLO, SigLIP2, LLM verify, gap detection, không đổi logic hiện có); `api` (Node.js/Express, `POST /analyze`, giữ MỎNG, chỉ proxy + validate + format JSON, không lặp business logic, có test Jest/supertest); `web` (HTML/CSS/JS thuần, gọi `api` qua `fetch`).
- Không deploy public (giữ nguyên quyết định gốc, ADR-001 chỉ đổi số lượng process nội bộ, không mở rộng scope deploy)
- Lưu trữ bằng SQLite (file local)

### Ngoài scope (Future Work)
- Continual learning từ feedback người dùng
- OCR trên bao bì để phân biệt flavor/biến thể cùng brand
- VLM và OCR làm fallback nhận diện cho SKU chưa có trong catalog, đã cân nhắc 2026-07-21, quyết định gác lại: VLM tốn cost/latency và chưa giải quyết được phần giá/ngưỡng đầy kệ (SKU chưa có trong catalog vẫn thiếu metadata này dù nhận diện đúng tên); OCR có tiềm năng nhưng rủi ro accuracy trên ảnh kệ thật khác điều kiện ảnh catalog sạch. Để dành làm nếu dư thời gian ở tuần 5, không phải cam kết bắt buộc
- Chuẩn hóa tên SKU liên siêu thị / xử lý biến thể tên gọi giữa các nhà bán lẻ
- Depth-multiplier tự động (suy luận độ sâu từ ảnh)
- Multi-tenant, deploy cloud, migrate sang Postgres/Supabase khi cần multi-store thật
- Lịch sử nhiều lần chụp theo thời gian + biểu đồ xu hướng, **nice-to-have**, chỉ làm nếu dư thời gian ở tuần 5, không phải cam kết bắt buộc
- Multi-segment capture chính thức (kệ quá to phải chụp thành nhiều ảnh nối tiếp, hệ thống tự cộng dồn/khai báo các ảnh thuộc cùng 1 kệ). Quyết định 2026-07-28: MVP giữ nguyên giả định "1 ảnh = 1 đơn vị kệ trọn vẹn" ở trên, KHÔNG build luồng khai báo/gộp nhiều ảnh thành 1 kệ. Nếu kệ quá to, nhân viên tự chụp nhiều ảnh và xác nhận riêng như các lần scan độc lập, chấp nhận rủi ro double-count nếu 2 ảnh chồng lấn vùng chụp, giảm thiểu bằng hướng dẫn "chụp nối tiếp, không chồng lấn" (không phải cơ chế tự động). Ghép ảnh thật (panorama/stitching) trước khi detect cũng bị loại, thêm hẳn 1 pipeline con (feature matching, warping, blending), rủi ro cao nhất cho timeline 6 tuần, không cân xứng với lợi ích.
- Path 2 (banner cảnh báo low-confidence/edge-crop + chụp lại 1 vòng) và Path 3 (màn Admin "Quản lý catalog" để thêm SKU mới) đã bị cắt khỏi MVP. Quyết định 2026-08-19: giới hạn thời gian 6 tuần solo không đủ để làm cả 2 path này cho chắc tay, ưu tiên độ chính xác của pipeline lõi (detection, classification, gap detection) hơn. Đúng theo thứ tự cắt đã tính trước ở roadmap tuần 1 (docs/reports/week-01), không phải phát sinh ngoài kế hoạch.

## 3. User Stories

- Là nhân viên cửa hàng, tôi chụp 1 ảnh mảng kệ hàng bằng điện thoại → hệ thống tự khoanh vùng từng sản phẩm.
- Là nhân viên cửa hàng, tôi thấy sản phẩm nào bị đánh dấu "sắp hết/hết hàng" trên dashboard → tôi biết ngay cần bổ sung sản phẩm gì.

## 4. Feature Spec

| Feature | Mô tả | Input | Output |
|---|---|---|---|
| Manual crop (UI) | Nhân viên tự chỉnh vùng crop (loại bỏ nền/kệ hàng xóm) trước khi phân tích | Ảnh gốc + vùng crop tay chọn | Ảnh đã crop theo vùng nhân viên chọn |
| Upload & Detect | Nhân viên upload 1 ảnh mảng kệ | Ảnh JPG/PNG (đã crop tay qua UI) | Danh sách box tọa độ (YOLO) |
| Classify | Mỗi box được match với catalog | Box crop + catalog embeddings | Tên SKU + confidence, hoặc `unknown` nếu confidence của box đó dưới ngưỡng riêng (không ép match SKU sai) |
| Aggregate & Price | Cộng dồn theo SKU, nhân giá | SKU đã đếm + catalog giá | Bảng SKU/số lượng/thành tiền/tổng |
| Low-stock flag | So với ngưỡng "đầy kệ" mỗi SKU | Số lượng vs ngưỡng | Cờ: Đủ / Sắp hết / Hết hàng (áp dụng cho MỌI SKU trong catalog, kể cả SKU 0 lần detect, xem docs/reports/week-01/2026-07-21.md) |
| Gap detection | Khoanh vùng trống giữa 2 sản phẩm liền kề cùng hàng kệ | Danh sách box đã detect | Danh sách box "khoảng trống" (tọa độ), tách biệt với box sản phẩm |
| Dashboard | Hiển thị ảnh có box + bảng kết quả | - | Giao diện `web` (HTML/React), dữ liệu lấy từ `api` |

## 5. Acceptance Criteria

### Path 1: Scan kệ hàng (happy path)
- Nhân viên chọn "Chụp/Upload ảnh" và chọn 1 ảnh mảng kệ
- Sau upload, hiển thị ảnh gốc + loading state trong lúc detect + classify
- Kết quả trả về: ảnh có box khoanh, danh sách SKU nhận diện kèm confidence
- Nhân viên sửa số lượng (facing_count) từng vị trí nếu cần, trước khi xác nhận
- Sau khi bấm "Xác nhận", hệ thống lưu kết quả vào bảng tồn kho hiện tại và cập nhật dashboard ngay

### General A/C (All Paths)
- Mỗi lần scan lưu kèm timestamp và ảnh gốc để truy vết
- Kết quả chỉ tính là "tồn kho chính thức" sau khi nhân viên xác nhận. Số liệu AI đề xuất trước đó chỉ là draft, không tự ghi đè
- Catalog dùng để classify là bản mới nhất tại thời điểm scan
- Mọi lần scan (thành công/cảnh báo/lỗi) đều được log ở backend

## 6. Frontend Requirements

**Kiến trúc:** `web` gọi `api` (Node/Express, `POST /analyze`) qua HTTP, `api` gọi `ml-service`
(Python, `POST /predict`). Xem đầy đủ quyết định, rationale, và mốc rollback/checkpoint ở
`docs/adr/0001-migrate-node-api-frontend.md`. Trình tự triển khai: contract-first (chốt JSON
schema trước, `ml-service` trả mock data ban đầu để `web` không bị chặn bởi backlog CV chưa
đóng), nối `ml-service` thật vào sau.

- **Entry point Path 1:** trang chính "Scan kệ hàng", nút Upload, kết quả annotate hiển thị ngay trên cùng màn hình

**Confirmation Acceptance** *(bước người dùng xác nhận kết quả AI trước khi ghi nhận chính thức)*:
- Hiển thị rõ kết quả là "đề xuất, chưa lưu" cho đến khi xác nhận
- Bắt buộc xác nhận/sửa số liệu trước khi lưu vào tồn kho

**Post UI** *(trạng thái sau khi xác nhận xong)*:
- Dashboard cập nhật ngay: bảng số lượng theo SKU, tổng giá trị tồn kho, cờ Sắp hết/Hết hàng
- Ảnh annotate + thời điểm scan lưu vào lịch sử (nếu làm phần nice-to-have)

## 7. Backend Requirements

**Eligibility & Validation:** validate ảnh upload hợp lệ; validate catalog không rỗng trước khi cho phép scan.

**Manual Crop Decision (2026-08-04):** đã thử ROI-crop tự động bằng CLIPSeg zero-shot segmentation (chi tiết benchmark: `docs/log-figures/2026-07-28-roi-crop-component-selection.md`, `docs/log-figures/2026-07-28-roi-crop-threshold-benchmark.md`). Validated tay lúc 2026-07-28 là "4/5 ảnh tốt", nhưng test lại sau đó phát hiện segmentation lẹm vào sản phẩm quá nhiều, không đạt yêu cầu thực tế. Quyết định 2026-08-04: bỏ hẳn hướng auto-crop, dùng crop tay trong UI (`web/src/features/scan-wizard/CropStep.jsx`, bước "2. Chỉnh vùng kệ hàng" của scan wizard) làm cơ chế loại bỏ nền/kệ hàng xóm duy nhất. Nhân viên chủ động kiểm soát vùng crop ngay lúc chụp, không cần model segmentation riêng.

**Detection & Classification Processing:** YOLO detect → danh sách box; mỗi box chạy SigLIP2 embedding + retrieval so với catalog hiện tại → SKU + confidence; nếu confidence cao nhất của 1 box dưới ngưỡng riêng cho từng box → gán `unknown` thay vì SKU sai, không tính vào aggregate quantities/value.

**Confirmation Handling:** nhận input xác nhận/sửa số lượng (facing_count) từ frontend; chỉ ghi vào bảng tồn kho chính thức sau khi xác nhận. Depth cố định = 1, pipeline chưa tự suy luận độ sâu từ ảnh (xem ADR-002, mục "Depth-multiplier tự động" ở Future Work).

**Threshold & Flagging Handling:** so sánh số lượng đã xác nhận với ngưỡng đầy kệ của từng SKU → gán cờ Đủ/Sắp hết/Hết hàng; cập nhật giá trị tồn kho = số lượng × giá.

**Gap Detection Processing:** sau detect, gom box theo hàng kệ (cluster theo y-center); trong mỗi hàng, so khoảng cách giữa 2 box liền kề với chiều rộng trung bình sản phẩm của hàng (fallback median toàn ảnh nếu hàng có 0-1 box) → nếu vượt ngưỡng tỉ lệ → flag vùng đó là gap. Không flag khoảng trống ở đầu/cuối hàng (trước box đầu, sau box cuối), không đủ căn cứ phân biệt rìa kệ với hết hàng thật.

**Logging & Observability:** log mỗi lần scan (ảnh gốc, kết quả detect/classify, xác nhận cuối, timestamp).

**Lưu trữ:** SQLite (file `.db` local), không dùng Supabase/cloud DB vì app chạy local, không cần multi-user/auth/network. Gồm 3 bảng chính:
- `catalog`: sku_id, tên, giá, ngưỡng đầy kệ, đường dẫn ảnh mẫu, embedding
- `inventory`: bản ghi tồn kho đã xác nhận (sku_id, số lượng, giá trị, thời điểm scan)
- `scan_history`: log từng lần scan (ảnh gốc, kết quả thô, xác nhận cuối, timestamp)

Kiến trúc bảng SQL này cho phép migrate sang Postgres/Supabase sau này nếu cần multi-tenant thật (ghi vào Future Work).

## 8. Catalog: hướng dẫn thu thập ảnh mẫu

- Nguồn: ảnh thật crawl từ web (Shopee/Tiki/trang thương hiệu), **không tự chụp**, **không dùng ảnh AI generate** (rủi ro sai lệch bao bì làm giảm độ chính xác retrieval)
- Số lượng: 2-3 ảnh/SKU, theo đúng tỷ lệ đã dùng ở benchmark Phase 2 (RPC: 48 ảnh/16 category ≈ 3 ảnh/category)
- Tiêu chuẩn ảnh: 1 sản phẩm/ảnh, nền đơn giản, đủ sáng, thẳng mặt trước, nhãn đọc rõ, giống ảnh sản phẩm e-commerce, khác với ảnh chụp cả mảng kệ dùng lúc scan thật
- Thông tin cần thu thập mỗi SKU: tên nội bộ (tự đặt, không cần khớp cách hiển thị của bất kỳ siêu thị thật nào), giá tham khảo, ngưỡng đầy kệ (số lượng tự định nghĩa), 2-3 ảnh mẫu

## 9. Evaluation: Classification Phase (Định nghĩa Done)

Phạm vi: đánh giá riêng phase classify (SigLIP2 zero-shot retrieval trên catalog + Gemini escalation cho case `unknown`). Detection (SKU-110k model) đã frozen, không nằm trong phạm vi đánh giá này. Quy trình chi tiết xem plan riêng `docs/superpowers/plans/2026-07-29-classification-eval.md`.

**Test set:**
- ~20 ảnh mảng kệ thật, đa dạng ánh sáng/góc/loại kệ (thực tế: 21 ảnh, test1-5 + test7-22, đánh số test6 bị bỏ có chủ đích)
- 150 crop label tay, chia 3 batch (52 + 78 + 20), lấy mẫu từ crop do detection sinh ra trên các ảnh trên
- Tỷ lệ trong/ngoài catalog thực tế: 98/150 (65.3%) có SKU nằm trong catalog hiện có, 52/150 (34.7%) là sản phẩm ngoài catalog hoặc crop không xác định được (lệch so với dự kiến ban đầu 80-85%/15-20%, vì mẫu lấy ngẫu nhiên từ crop thật chứ không ép tỷ lệ cố định)

**Metrics (tách riêng theo lớp, không gộp thành 1 con số accuracy tổng):**
- SigLIP2 top-1 accuracy trên crop hợp lệ, sản phẩm có trong catalog
- Escalation rate (% crop bị đẩy lên Gemini)
- Gemini accuracy trên phần đã escalate
- End-to-end classification accuracy (SigLIP2 đúng trực tiếp + Gemini đúng khi escalate)
- **Silent wrong-match rate** trên nhóm sản phẩm ngoài catalog: % bị gán nhầm thành 1 SKU có sẵn thay vì đúng ra phải trả `unknown`/escalate. Đây là failure mode nguy hiểm nhất (báo sai out-of-stock một cách "tự tin"), phải theo dõi riêng, không được pha vào accuracy chung.
- Crop lỗi do detection (merge nhiều SKU trong 1 box, hoặc detect nhầm vùng ngoài kệ), loại khỏi mẫu số accuracy classification, chỉ report riêng tần suất xuất hiện (đây là lỗi của phase detection đã frozen, không phải lỗi classification)
- Latency: trung bình + **p95** toàn pipeline (detect → SigLIP2 match → Gemini escalation nếu có) mỗi lần scan

**Definition of Done (MVP):**
- [x] End-to-end classification accuracy ≥ 80% (đạt 80.7%, 121/150)

Đạt đủ các ngưỡng trên → dừng tune, coi classification phase production-ready cho MVP, chuyển sang thu thập feedback thật từ production thay vì tiếp tục tối ưu trên test set nội bộ.
