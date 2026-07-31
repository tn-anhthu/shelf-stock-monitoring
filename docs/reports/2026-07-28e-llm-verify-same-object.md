# Việc 1 — LLM escalation cho case IoU-duplicate (đã implement + chạy thật) — 2026-07-28e

## Implement

`src/pipeline/llm_escalation.py::verify_same_object` (+ `verify_same_object_gemini`
cho Gemini) — theo đúng convention của `escalate_to_llm` đã có (cùng schema
`{reasoning, answer}`, cùng retry-on-malformed-JSON, cùng cách build content
Anthropic/Gemini). Câu hỏi: gửi 2 crop, hỏi model đây là 1 vật lý (`same_object`)
hay 2 vật lý khác nhau (`different_objects`, có thể cùng SKU). Prompt nêu rõ bẫy
đã phát hiện hôm 2026-07-28d: 2 sản phẩm cùng SKU xếp chồng/sát nhau KHÔNG được
tự động coi là 1 vật chỉ vì giống hệt nhau — model phải nhìn nội dung ảnh (2 nắp,
2 đường viền sản phẩm, đường nối/khe hở) chứ không suy luận từ độ giống bao bì.

TDD: 15 test mới (`tests/pipeline/test_llm_escalation.py`, cả 2 provider) —
schema enum đúng, gửi đúng 2 ảnh crop, retry-on-malformed-JSON. 30/30 test
llm_escalation pass.

## Chạy thật trên đúng 42 cặp

Dùng lại `data/scan_viz/input/test{1-5}.HEIC` gốc + tọa độ 42 cặp đã đo hôm
2026-07-28d (không mở rộng danh sách). Provider = Gemini (mặc định `.env`,
khớp cách chạy thật của dự án).

### Kết quả tổng

| | |
|---|---|
| Tổng số cặp gọi LLM | 42 |
| `same_object` (đề xuất merge) | 34 |
| `different_objects` (giữ nguyên) | 8 |

### Đối chiếu với 3 ground truth đã xác nhận bằng mắt (test3, session 2026-07-28d)

| cặp | ground truth | LLM trả lời | đúng? |
|---|---|---|---|
| box38/box40 (2 lốc Yakult xếp chồng) | different_objects | different_objects | ✅ |
| box40/box42 (2 lốc Yakult xếp chồng, góc khác) | different_objects | different_objects | ✅ |
| box20/box44 (1 chai Betagen, box44 chỉ chụp nắp) | different_objects | **same_object** | ❌ |

**2/3 đúng.** Case sai (box20/box44) là case khó nhất trong 3 case — box44 chỉ
chụp phần nắp/cổ chai (không có logo/text phân biệt), nên hợp lý là model không
đủ tín hiệu thị giác để nhận ra đây là crop của 1 vùng rất nhỏ, không đại diện
đủ để so sánh — vẫn là lỗi thật, không phải điểm cộng.

### Hiệu ứng merge tổng thể theo từng ảnh (union-find trên các cặp `same_object`)

| ảnh | box liên quan tới ≥1 cặp trùng lặp | số vật lý còn lại sau merge theo LLM |
|---|---|---|
| test1 | 6 | 5 |
| test2 | 19 | 8 |
| test3 | 30 | 16 |
| test4 | 5 | 2 |
| test5 | 8 | 4 |

*Lưu ý phạm vi:* con số "số vật lý sau merge" ở bảng này dựa hoàn toàn vào
quyết định pairwise của LLM, CHƯA đối chiếu đếm tay cho toàn bộ — chỉ 3 cặp
ở test3 có ground truth đếm tay xác nhận (bảng trên). Đếm tay đầy đủ cho tất cả
42 cặp/19+ box liên quan nằm ngoài phạm vi thời gian hợp lý của việc đo này;
báo cáo trung thực đúng những gì đã đo được, không suy rộng.

### Cost/latency thực tế (đo trực tiếp, không ước lượng)

| | |
|---|---|
| Input tokens | 102,280 |
| Output tokens | 3,052 |
| **Chi phí thực** (Gemini 3.5 flash-lite, $0.25/$1.50 per Mtok) | **$0.0301** cho 42 lần gọi — **$0.00072/cặp** |
| **Latency thực** (tuần tự, không parallel) | 134.5s tổng — **3.20s/cặp trung bình** (nhanh nhất 1.26s, chậm nhất 15.40s — 1 outlier) |

So sánh quy mô: nếu áp dụng cho toàn bộ 5 ảnh demo mỗi lần scan (42 cặp/297 box
≈ 14% box cần thêm bước này), chi phí thêm ~$0.03/lần scan 5 ảnh — không đáng kể
so với chi phí LLM verify SKU đã có (~$0.54/5 ảnh, xem báo cáo catalog trước).
Latency nếu chạy song song (giống `classify_crops_parallel` đã làm cho verify
SKU) sẽ giảm đáng kể so với 134.5s tuần tự — chưa đo thực tế phần này vì nằm
ngoài yêu cầu (đo cost/latency của chính lệnh gọi LLM mới, chưa phải đo latency
sau khi nối vào pipeline song song).

## Kết luận Việc 1

Đủ điều kiện để tiếp tục (đúng như bạn đánh giá ban đầu): cost/latency thấp
($0.00072/cặp, 3.2s/cặp), cơ chế chạy ổn định (0 lỗi JSON/retry trên cả 42 lần
gọi thật). Nhưng **độ chính xác trên đúng 3 case có ground truth mới đạt 2/3
(66.7%)** — case sai (box20/box44, chai Betagen) nằm ở crop quá nhỏ/thiếu thông
tin phân biệt (chỉ chụp nắp chai), không phải lỗi suy luận rõ ràng. 39/42 cặp
còn lại chưa có ground truth đếm tay để tính accuracy thật, chỉ có thể báo cáo
phân bố câu trả lời (34 same_object / 8 different_objects), không suy ra %
đúng cho toàn bộ. Điểm 2/3 này nên cân nhắc khi quyết định bước tiếp theo (vd:
gửi kèm ảnh ngữ cảnh rộng hơn thay vì chỉ 2 crop tách biệt, tương tự cách
`escalate_to_llm` gửi kèm reference image) — **không tự ý mở rộng làm trong
việc này**, để lại cho quyết định tiếp theo.
