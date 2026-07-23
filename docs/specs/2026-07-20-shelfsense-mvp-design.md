# ShelfSense MVP — Design Spec

**Ngày:** 2026-07-20

> Vấn đề, câu hỏi nghiên cứu, roadmap, và trạng thái hiện tại xem ở
> [README.md](../../README.md). Spec này tập trung chi tiết kỹ thuật: persona, scope, user
> stories, feature spec, acceptance criteria, backend/frontend requirements.

## 1. Persona

**Nhân viên cửa hàng/siêu thị mini** — được giao nhiệm vụ kiểm kê kệ hàng định kỳ, dùng điện thoại công ty, không rành công nghệ. Không phải PM/data scientist.

Vai phụ: **Admin/quản lý cửa hàng** — người thêm sản phẩm mới vào catalog khi nhập hàng.

## 2. Scope

### Trong scope (MVP bắt buộc)
- 1 ảnh chụp toàn bộ 1 mảng kệ (nhiều hàng, nhiều SKU sát nhau — giống ảnh SKU-110K/ảnh thực tế, không phải 1 ngăn đơn lẻ)
- Giới hạn nhóm hàng: FMCG có bao bì (nước giải khát, mì gói, bánh kẹo...) — không mở rộng sang quần áo, đồ gia dụng không bao bì
- Catalog ~100 SKU thật (2026-07-21: mở rộng từ ~15-30, xem mục 9) — là danh sách SKU
  tổng của "khách hàng" (giống client cung cấp master SKU list trong production thật), KHÔNG
  gắn cố định với 1 kệ/vị trí cụ thể. Lý do: planogram thay đổi theo campaign marketing của
  từng brand, nhân viên xoay vị trí sản phẩm liên tục — hệ thống chỉ cần nhận ra đúng SKU khi
  nó xuất hiện trong khung hình, bất kể đang ở kệ nào. Nguồn gốc thực tế của danh sách 100 SKU
  này: ghi nhận từ 2 ảnh kệ thật chụp để demo (không phải chọn ngẫu nhiên) — nguồn ảnh catalog
  vẫn crawl từ web (Shopee/Tiki/trang thương hiệu) cho từng SKU, không tự chụp, không dùng ảnh
  AI generate
- Depth-multiplier: nhân viên tự nhập tay số lớp phía sau (không tự động suy luận)
- HITL: 1 banner cảnh báo tĩnh khi confidence thấp, tối đa 1 vòng chụp lại — không có luồng xác nhận đa bước
- Gap detection: khoanh vùng khoảng trống giữa các sản phẩm đã detect trong cùng 1 hàng kệ
  bằng heuristic hình học (so khoảng cách giữa 2 box liền kề với chiều rộng trung bình sản
  phẩm trong hàng) — không train model riêng cho "khoảng trống". Quyết định 2026-07-21: nâng
  từ nice-to-have lên core, đánh đổi risk timeline có ý thức (xem mục 9)
- Chạy local qua Streamlit/Gradio, không deploy public
- Lưu trữ bằng SQLite (file local), không dùng Supabase/cloud DB

### Ngoài scope (Future Work)
- Lending/credit signal (đã cắt — dùng mock data sẽ không dùng được thực tế)
- Continual learning từ feedback người dùng
- OCR trên bao bì để phân biệt flavor/biến thể cùng brand
- VLM và OCR làm fallback nhận diện cho SKU chưa có trong catalog — đã cân nhắc
  2026-07-21, quyết định gác lại: VLM tốn cost/latency và không giải quyết được phần
  giá/ngưỡng đầy kệ (SKU chưa có trong catalog vẫn thiếu metadata này dù nhận diện
  đúng tên); OCR có tiềm năng nhưng rủi ro accuracy trên ảnh kệ thật khác điều kiện
  ảnh catalog sạch — để dành làm nếu dư thời gian ở tuần 5, không phải cam kết bắt buộc
- Chuẩn hóa tên SKU liên siêu thị / xử lý biến thể tên gọi giữa các nhà bán lẻ
- Depth-multiplier tự động (suy luận độ sâu từ ảnh)
- Multi-tenant, deploy cloud, migrate sang Postgres/Supabase khi cần multi-store thật
- Lịch sử nhiều lần chụp theo thời gian + biểu đồ xu hướng — **nice-to-have**, chỉ làm nếu dư thời gian ở tuần 5, không phải cam kết bắt buộc
- Nhận diện ranh giới giữa nhiều đơn vị kệ/tủ khác nhau trong cùng 1 ảnh (ví dụ 2 tủ lạnh đặt sát nhau, ảnh vô tình lấy lẫn sản phẩm của tủ bên cạnh) — phát hiện 2026-07-21 khi stress-test gap detection trên ảnh tủ lạnh nước ngọt (xem mục 9). Input giả định của toàn hệ thống là "1 ảnh = đúng 1 đơn vị kệ/tủ trọn vẹn" (mục 2, dòng đầu) — ảnh lấn sang đơn vị khác là ngoài giả định này, không phải bug cần vá bằng thêm heuristic. Xử lý bằng kỷ luật chụp ảnh (nhân viên chụp đúng khung 1 tủ).

## 3. User Stories

- Là nhân viên cửa hàng, tôi chụp 1 ảnh mảng kệ hàng bằng điện thoại → hệ thống tự khoanh vùng và đếm số lượng từng sản phẩm, để tôi không phải đếm tay.
- Là nhân viên cửa hàng, tôi thấy sản phẩm nào bị đánh dấu "sắp hết/hết hàng" trên dashboard → tôi biết ngay cần bổ sung sản phẩm gì.
- Là nhân viên cửa hàng, khi ảnh chụp không rõ → tôi nhận cảnh báo "nên chụp lại" thay vì hệ thống báo sai số liệu.
- Là admin, tôi thêm 1 sản phẩm mới (ảnh mẫu + tên + giá) vào catalog khi cửa hàng nhập hàng mới → hệ thống nhận diện được sản phẩm đó ở lần chụp tiếp theo, không cần train lại model.
- Là nhân viên cửa hàng, tôi nhập tay số lớp sản phẩm xếp phía sau mỗi vị trí → hệ thống tính đúng hơn tổng số lượng thực tế.

## 4. Feature Spec

| Feature | Mô tả | Input | Output |
|---|---|---|---|
| Upload & Detect | Nhân viên upload 1 ảnh mảng kệ | Ảnh JPG/PNG | Danh sách box tọa độ (YOLO) |
| Classify | Mỗi box được match với catalog | Box crop + catalog embeddings | Tên SKU + confidence, hoặc `unknown` nếu confidence của box đó dưới ngưỡng riêng (không ép match SKU sai) |
| Depth input | Nhân viên nhập số lớp sau mỗi vị trí | Số nguyên (mặc định = 1) | Số lượng thực tế = facing × depth |
| Aggregate & Price | Cộng dồn theo SKU, nhân giá | SKU đã đếm + catalog giá | Bảng SKU/số lượng/thành tiền/tổng |
| Low-stock flag | So với ngưỡng "đầy kệ" mỗi SKU | Số lượng vs ngưỡng | Cờ: Đủ / Sắp hết / Hết hàng (áp dụng cho MỌI SKU trong catalog, kể cả SKU 0 lần detect — xem bugfix mục 9) |
| Gap detection | Khoanh vùng trống giữa 2 sản phẩm liền kề cùng hàng kệ | Danh sách box đã detect | Danh sách box "khoảng trống" (tọa độ), tách biệt với box sản phẩm |
| Low-confidence warning | Confidence trung bình khu vực < ngưỡng | Confidence scores | Banner "nên chụp lại khu vực X" |
| Add new SKU | Admin thêm sản phẩm mới vào catalog | 1-2 ảnh mẫu + tên + giá | Catalog cập nhật (embedding mới) |
| Dashboard | Hiển thị ảnh có box + bảng kết quả | — | Giao diện Streamlit/Gradio |

## 5. Acceptance Criteria

### Path 1 — Scan kệ hàng (happy path)
- Nhân viên chọn "Chụp/Upload ảnh" và chọn 1 ảnh mảng kệ
- Sau upload, hiển thị ảnh gốc + loading state trong lúc detect + classify
- Kết quả trả về: ảnh có box khoanh, danh sách SKU nhận diện kèm confidence
- Nhân viên nhập depth (mặc định = 1) cho từng vị trí trước khi xác nhận
- Sau khi bấm "Xác nhận", hệ thống lưu kết quả vào bảng tồn kho hiện tại và cập nhật dashboard ngay

### Path 2 — Khu vực nhận diện kém (low-confidence)
- Nếu confidence trung bình 1 khu vực dưới ngưỡng, hệ thống không tự động lưu số liệu khu vực đó
- Hiển thị banner theo khu vực: "Khu vực X chưa rõ, nên chụp lại" kèm nút "Chụp lại khu vực này"
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

**Detection & Classification Processing:** YOLO detect → danh sách box; mỗi box chạy SigLIP2 embedding + retrieval so với catalog hiện tại → SKU + confidence; nếu confidence cao nhất của 1 box dưới ngưỡng riêng cho từng box (per-detection threshold, tách biệt với ngưỡng low-confidence trung bình khu vực) → gán `unknown` thay vì SKU sai, không tính vào aggregate quantities/value; tính confidence trung bình theo khu vực để xác định flag low-confidence.

**Confirmation Handling:** nhận input xác nhận/sửa từ frontend (gồm depth nhập tay); chỉ ghi vào bảng tồn kho chính thức sau khi xác nhận; số lượng thực tế = facing × depth.

**Threshold & Flagging Handling:** so sánh số lượng đã xác nhận với ngưỡng đầy kệ của từng SKU → gán cờ Đủ/Sắp hết/Hết hàng; cập nhật giá trị tồn kho = số lượng × giá.

**Catalog Management (Path 3):** endpoint thêm SKU mới — nhận ảnh mẫu + metadata → tính
embedding bằng đúng pipeline SigLIP2 đã benchmark (`embed_siglip2`) → lưu vào catalog store; catalog store đọc mới nhất mỗi lần scan, không cache cứng.

**Gap Detection Processing:** sau detect, gom box theo hàng kệ (cluster theo y-center); trong
mỗi hàng, so khoảng cách giữa 2 box liền kề với chiều rộng trung bình sản phẩm của hàng (fallback
median toàn ảnh nếu hàng có 0-1 box) → nếu vượt ngưỡng tỉ lệ → flag vùng đó là gap. Không flag
khoảng trống ở đầu/cuối hàng (trước box đầu, sau box cuối) — không đủ căn cứ phân biệt rìa kệ
với hết hàng thật.

**Logging & Observability:** log mỗi lần scan (ảnh gốc, kết quả detect/classify, xác nhận cuối, timestamp); log riêng các trường hợp low-confidence và thêm SKU mới.

**Lưu trữ:** SQLite (file `.db` local) — không dùng Supabase/cloud DB vì app chạy local,
không cần multi-user/auth/network. Gồm 3 bảng chính:
- `catalog` — sku_id, tên, giá, ngưỡng đầy kệ, đường dẫn ảnh mẫu, embedding
- `inventory` — bản ghi tồn kho đã xác nhận (sku_id, số lượng, giá trị, thời điểm scan)
- `scan_history` — log từng lần scan (ảnh gốc, kết quả thô, xác nhận cuối, timestamp)

Kiến trúc bảng SQL này cho phép migrate sang Postgres/Supabase sau này nếu cần multi-tenant thật (ghi vào Future Work).

## 8. Catalog — hướng dẫn thu thập ảnh mẫu

- Nguồn: ảnh thật crawl từ web (Shopee/Tiki/trang thương hiệu) — **không tự chụp**, **không dùng ảnh AI generate** (rủi ro sai lệch bao bì làm giảm độ chính xác retrieval)
- Số lượng: 2-3 ảnh/SKU, theo đúng tỷ lệ đã dùng ở benchmark Phase 2 (RPC: 48 ảnh/16 category ≈ 3 ảnh/category)
- Tiêu chuẩn ảnh: 1 sản phẩm/ảnh, nền đơn giản, đủ sáng, thẳng mặt trước, nhãn đọc rõ — giống ảnh sản phẩm e-commerce, khác với ảnh chụp cả mảng kệ dùng lúc scan thật
- Thông tin cần thu thập mỗi SKU: tên nội bộ (tự đặt, không cần khớp cách hiển thị của bất kỳ siêu thị thật nào), giá tham khảo, ngưỡng đầy kệ (số lượng tự định nghĩa), 2-3 ảnh mẫu

## 9. Revision Log

- **2026-07-21:** Thảo luận về rủi ro closed-set catalog khi test trên kệ hàng thật
  (crop không thuộc catalog vẫn bị ép match ra 1 SKU sai thay vì báo unknown). Quyết
  định: (1) catalog chuyển từ "15-30 SKU tự chọn" sang "SKU thật của 1 kệ cụ thể tại 1
  siêu thị gần nhà" để scope test luôn nằm trong thế giới đã catalog hóa (mục 2, 8);
  (2) thêm ngưỡng confidence riêng cho từng box detection để trả `unknown` thay vì ép
  match sai (mục 4, 7) — khác với `is_low_confidence` hiện có vốn chỉ tính trung bình
  cả khu vực, không chặn từng detection riêng lẻ; (3) cân nhắc VLM/OCR làm fallback
  nhận diện cho SKU ngoài catalog, quyết định gác lại tuần 5 (mục 2, Ngoài scope) vì cả
  hai đều không giải quyết được phần giá/ngưỡng đầy kệ cho SKU chưa từng thêm vào
  catalog — đây là giới hạn dữ liệu nghiệp vụ, không phải giới hạn model.
- **2026-07-21 (tiếp):** Phát hiện bug thật trong `scan.py`: `flags` hiện chỉ tính cho SKU đã
  xuất hiện ít nhất 1 lần trong `quantities` (tức đã detect được) — SKU hết sạch hoàn toàn (0
  detection) không bao giờ vào được `quantities` nên cũng không bao giờ có flag `"out"`, dù
  `flag_status(0, ...)` có logic trả `"out"` sẵn. Cần sửa: loop `flags` qua toàn bộ
  `catalog_items` thay vì chỉ qua `quantities.items()`, dùng `quantities.get(sku_id, 0)` làm
  mặc định. Đây là bug ảnh hưởng đúng user story quan trọng nhất (mục 3, dòng 2) — sửa bất kể
  quyết định gap detection bên dưới.
  Đồng thời quyết định: thêm Gap Detection (mục 2, 4, 7) làm core feature thay vì nice-to-have
  tuần 5 — dùng heuristic hình học (so khoảng cách giữa box liền kề trong cùng hàng kệ với
  chiều rộng trung bình), không train model riêng. Đây là quyết định có ý thức đánh đổi risk
  timeline (đi ngược nguyên tắc "thứ tự cắt nếu trễ" ở README) — việc cắt gì để bù nếu trễ sẽ
  quyết ở checkpoint buffer tuần 5, không chốt trước.
- **2026-07-21 (test thật trên ảnh kệ sữa + tủ lạnh nước ngọt):** Phát hiện thêm 1 lỗi thật
  qua debug có số liệu (không phải đoán): nhiều box sản phẩm bị YOLO detect chẻ đôi/ba (1 hộp
  vật lý → 2-3 box), làm sai số lượng đếm được. Đo IoU giữa các cặp box nghi ngờ trên 29
  candidate, 4 ảnh: IoU gần như 0 (0.000–0.03) xuyên suốt, x-overlap ≈1.00, y liền kề/chạm —
  xác nhận đây là hiện tượng "2 mảnh tách rời của cùng 1 vật" chứ không phải "model vẽ 2 box
  trùng nhau" (case đó IoU cao 0.5-0.7, đã gặp riêng và loại khỏi tập trên). Do đó hướng sửa là
  heuristic merge theo x-overlap + y-gap + aspect ratio bất thường (không phải chỉnh tham số
  `iou` của NMS khi gọi `model.predict()`, vì NMS không xử lý được case 2 box không chồng lấn).
  Giả thuyết chưa kiểm chứng đầy đủ: hộp có hoa văn/sọc ngang (SKU màu, có họa tiết bò đốm) bị
  chẻ nhiều hơn hộp vỏ trắng trơn — hợp lý về mặt kỹ thuật (pattern tần số cao dễ gây nhiễu
  feature của detector fine-tune trên ít data) nhưng chưa đo diện rộng để khẳng định; không
  chặn hướng sửa (merge heuristic không phụ thuộc nguyên nhân gây chẻ).
  Riêng ảnh tủ lạnh nước ngọt lộ ra giới hạn phạm vi input (ghi ở mục 2, Ngoài scope, dòng
  "Nhận diện ranh giới giữa nhiều đơn vị kệ/tủ") — không phải lỗi của gap detection logic.
- **2026-07-21 (Task G/E/H hoàn tất, 92/92 test):** `src/pipeline/box_merge.py::merge_adjacent_fragments`
  implement xong (quét toàn cặp box, không dùng row-clustering, xử lý được chuỗi 3+ mảnh).
  `width_ratio_threshold` (Task E) chốt 0.65, `width_multiplier` (Task H, gap) chốt 0.9 — cả
  2 số validate trên 4 ảnh thật (kệ sữa, tủ Pepsi, 2 ảnh Walmart), không over-filter/không phát
  sinh gap giả. `scan.py` nối đúng thứ tự `merge → filter → detect_gaps`, classify loop dùng
  boxes đã sạch. Xác nhận bằng ảnh render thật: kệ sữa gap khớp 100% ô trống thật (trước đó bỏ
  sót); tủ Pepsi loại đúng 1 gap giả do lon 7Up bị chẻ, giữ đúng 2 gap thật ở rìa kệ.
  Còn lại chưa làm: Task D (text-embedding SigLIP2 chống nhầm SKU hình dạng giống nhau, xem
  mục 9 lượt cân nhắc trước) — pipeline detect/gap giờ đã ổn định, đây là hạng mục tiếp theo
  hợp lý. `scripts/visualize_scan_e2e.py` (dùng cho slide) chưa được nối với merge/filter mới —
  cần cập nhật trước khi dùng lại cho demo, nếu không ảnh slide sẽ không phản ánh đúng pipeline
  đã cải thiện.
- **2026-07-21 (Task D thất bại, thay bằng LLM escalation):** Text-embedding fusion bị loại bỏ
  hoàn toàn sau 2 vòng test (tên tiếng Việt và tiếng Anh) — cosine similarity ở mức nhiễu
  (0.001-0.18), không tách được đúng/sai cho cả 2 nhóm khó. `embed_text_siglip2()` vẫn giữ
  trong code nhưng không dùng trong pipeline chính.
  Thay vào đó thử LLM escalation (chi phí không đáng kể ở quy mô demo)
  cho đúng 2 nhóm khó: 7Up thật vs Pepsi (case SigLIP2 sai) và Vinamilk có/không đường (case
  text-embedding cũng thua) — cả 2 được LLM phân loại đúng 100% khi có trong shortlist candidate
  thật. 2 case sai (ảnh tủ lạnh UAE dùng để stress-test, ngoài scope demo Việt Nam) là do sản
  phẩm thật (Mountain Dew) không có trong catalog — bộc lộ: điều kiện escalate chỉ dựa khoảng
  cách top1/top2 sát nhau là chưa đủ, cần kết hợp thêm ngưỡng điểm tuyệt đối của top-1 để phân
  biệt "2 SKU đã biết cạnh tranh nhau" khỏi "không SKU nào khớp tốt (sản phẩm ngoài catalog)".
  Quyết định: làm tiếp `escalate_to_llm` production + gắn vào `classify_crop`, có mitigation
  cho điểm yếu này.
- **2026-07-21 (catalog mở rộng 40 → ~100 SKU, đổi mô hình tư duy):** Catalog không còn gắn với
  "1 kệ cụ thể" (như mục 2 ghi ban đầu) — sửa thành danh sách SKU tổng kiểu client cung cấp
  trong production thật, độc lập với vị trí/kệ vật lý. Lý do: planogram đổi theo campaign
  marketing từng brand, nhân viên xoay vị trí sản phẩm liên tục — catalog theo 1 kệ cố định sẽ
  lỗi thời ngay khi planogram đổi. Danh sách 100 SKU hiện tại lấy từ 2 ảnh kệ thật chụp để demo
  (đã crawl ảnh + seed vào repo), dùng chung cho mọi case, không tách catalog riêng theo kệ.
  Ảnh hưởng tới các quyết định trước: catalog càng lớn, khả năng gặp SKU dễ nhầm (cùng hãng
  khác vị, hình dạng giống nhau) càng cao — củng cố lý do cần `unknown_threshold` +
  `escalate_to_llm` (mục 9, các mục trên), không phải chỉ để dự phòng mà là cơ chế cần thiết
  hơn khi scale catalog lên.
- **2026-07-21 (chốt kiến trúc: LLM verify mọi match, không chỉ escalation-only):** Test thật
  trên ảnh demo (không phải stress-test ngoài scope) cho thấy nhiều sản phẩm chưa seed vào
  catalog (Dutch Lady, Oatside, Green Farm...) vẫn bị gán 1 sku_id có sẵn với score 0.58-0.72 —
  cao hơn hẳn `unknown_threshold=0.5`. Đây là lần thứ 3 trong phiên (sau Pepsi/7up, Vinamilk
  vị) SigLIP2 score không tách được đúng/sai bằng bất kỳ ngưỡng cố định nào — kết luận: điểm số
  SigLIP2 không đáng tin để tự quyết định "khi nào cần hỏi LLM" (giả định nền của thiết kế
  escalation-only). Quyết định: **LLM verify MỌI match**, không chỉ escalate case mơ hồ.
  SigLIP2 vẫn giữ vai trò retrieval (rút gọn catalog xuống top-K candidate để giữ prompt nhỏ/rẻ
  dù catalog có 100 hay nhiều hơn), LLM luôn là bên quyết định cuối cùng (kể cả trả `unknown`).
  Đánh đổi: không phải chi phí (đã xác nhận rất thấp ở quy mô demo) mà là **thời gian** — mọi
  detection đều gọi API, cần cân nhắc gọi song song để không kéo dài thời gian scan.
  Cùng lúc phát hiện thêm 1 lỗi khác trên ảnh demo thật: nhiều box chồng lấn cao lên cùng 1 hộp
  Vinamilk, mỗi box gán sku khác nhau — nghi là case "duplicate detection, IoU cao 0.5-0.7" đã
  xác định từ Task F nhưng chưa từng fix (khác `merge_adjacent_fragments`, vốn chỉ xử lý IoU
  gần 0). Hướng sửa đúng: chỉnh tham số `iou` khi gọi `model.predict()` trong `detect_1a` — cần
  đo IoU thật trước khi chỉnh. 2 khung gap sai trên cùng ảnh nghi là hệ quả phụ của nhiễu này,
  nên sửa duplicate detection trước rồi mới debug lại gap.
