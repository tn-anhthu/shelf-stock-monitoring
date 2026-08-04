# Việc 2 — Trigger cho case đa-SKU trong 1 box (Binggrae) — CHỈ ĐO, chưa implement — 2026-07-28

## Case đã biết

Tìm lại từ `scripts/debug_duplicate_boxes.py` (KNOWN_CASES) + `src/pipeline/box_filter.py`
comment: **test1, box38** — box oversized (610,2478,821,2809), swallow box37
(702.7,2476.3,819.0,2772.5, chỉ chứa vị Melon), nhưng phần "leftover" (vị
Strawberry) KHÔNG có box nào khác độc lập che phủ (containment=0.0 với mọi box
khác) → `filter_contained_boxes` giữ lại box38 và gắn cờ NEEDS REVIEW tĩnh
(quyết định cũ, không train, vẫn giữ nguyên — khảo sát này không đảo ngược).
Ảnh gốc `data/scan_viz/input/test1.HEIC` còn nguyên, không cần dựng ảnh giả.

Đối chiếu case Haohao (crop_45, cùng file debug script) để chắc chắn không
nhầm 2 case: Haohao's leftover (cup thứ 2) CÓ box48 độc lập che phủ
(containment≥leftover_coverage_threshold) → bị `filter_contained_boxes` drop
thẳng, không phải "case ẩn" như Binggrae — không tính vào n cho khảo sát này.

**Xác nhận thống kê "0.34%"**: dữ liệu lấy lại từ log full-pipeline 5 ảnh demo
(đã chạy trước, 297 box tổng — khớp đúng con số đã dùng nhiều lần trong các báo
cáo trước) → 1/297 = 0.337% ≈ 0.34%. Không tìm thấy văn bản gốc ghi đúng số này
trong `docs/` hiện tại (spec cũ đã bị xoá/tái cấu trúc, xem báo cáo 2026-07-28),
nhưng con số khớp chính xác với dữ liệu đang có — coi là xác nhận được, không
phải bịa số.

## Đo 3 giả thuyết: box38 (n=1, case đã biết) vs toàn bộ 297 box của 5 ảnh demo

### (a) Kích thước tuyệt đối so với kích thước tham chiếu SKU — **CÓ TÁCH BIỆT RÕ**, nhưng phải chuẩn hoá đúng cách

Thử đầu tiên (so `box38` với các box khác **cùng sku_id** `binggrae_dua_200`
trên TOÀN BỘ 5 ảnh, không phân biệt ảnh nào) → **KHÔNG tách biệt** (box38 area
= 0.93x median tham chiếu, rank 153/251, giữa phân bố) — lý do: khoảng cách
camera/zoom khác nhau giữa 5 ảnh làm kích thước tuyệt đối theo pixel không so
được trực tiếp giữa các ảnh khác nhau, kể cả cùng SKU (bài học tương tự đã gặp
với `iou`/`width_multiplier` — 1 con số thô không đủ, cần chuẩn hoá theo bối
cảnh cục bộ).

Đo lại đúng cách: **width của box / width trung bình cùng HÀNG cùng ẢNH**
(chuẩn hoá theo scale cục bộ, dùng lại `cluster_rows` đã có sẵn trong pipeline)
→ **tách biệt rõ ràng**:

| | |
|---|---|
| box38 (Binggrae) | ratio = **1.43** |
| Runner-up thứ 2 toàn bộ 245 box hợp lệ | 1.23 |
| p95 toàn phân bố | 1.13 |
| median toàn phân bố | 1.00 |
| **Rank box38** | **1/245 (widest tương đối)** |

box38 là box "rộng hơn hàng của nó" nhiều nhất trong toàn bộ 5 ảnh demo,
cách biệt rõ với runner-up thứ 2 (1.43 vs 1.23) và với p95 (1.13).

### (b) Tỉ lệ khung hình (aspect ratio, w/h) — KHÔNG tách biệt

| | |
|---|---|
| box38 aspect ratio | 0.637 |
| Percentile trong 297 box | 57.6th (giữa phân bố) |
| Z-score | -0.12 |

Không có gì bất thường — box38 nằm giữa phân bố w/h chung, không dùng được
làm trigger riêng.

### (c) Confidence classification — KHÔNG tách biệt

| | |
|---|---|
| box38 score | 0.739 |
| Percentile trong 297 box | 35.0th |
| Z-score | -0.25 |
| So với avg ảnh test1 (0.735) | gần như bằng, không thấp bất thường |

Không tách biệt — model vẫn tự tin gán SKU dù box chứa 2 sản phẩm (dễ hiểu:
"binggrae_dua_200" vẫn đúng MỘT PHẦN, phần Melon chiếm phần lớn box nên
SigLIP2/LLM vẫn match tự tin).

## Kết luận Việc 2 (đúng nhánh "CÓ tín hiệu tách biệt" theo tiêu chí đã thống nhất)

1/3 giả thuyết tách biệt rõ: **box width / row-average width cùng ảnh (đã
chuẩn hoá scale cục bộ)** — box38 rank 1/245, cách biệt rõ runner-up và p95.
**Đề xuất dùng tín hiệu này làm trigger** gửi LLM hỏi "box này có chứa nhiều
hơn 1 sản phẩm không?" — ví dụ ngưỡng ~1.2–1.3x row-average (giữa runner-up
1.23 và box38 1.43), cần benchmark thêm nếu quyết định implement.

**Giới hạn quan trọng cần nêu rõ trước khi quyết định implement:** n=1 case
dương tính đã biết (đúng bản chất hiếm 0.34% của vấn đề) — 1 điểm dữ liệu
không đủ để khẳng định ngưỡng chính xác, chỉ đủ để nói "có tín hiệu đáng để
thử", không phải "đã validate ngưỡng". Rủi ro false positive trên box thật sự
rộng hợp lệ (packaging lớn, combo pack chính hãng) chưa được đo — cần ít nhất
vài case dương tính thật nữa (hoặc case âm tính khó — box rộng hợp lệ) trước
khi chốt ngưỡng, giống bài học `width_ratio_threshold` đã validate trên 4 ảnh
thật trước khi chốt, không phải áp dụng ngay từ 1 điểm dữ liệu.

**Chưa implement gì thêm** (không gọi LLM, không đổi `box_filter.py`, không
đổi quyết định NEEDS REVIEW tĩnh hiện tại) — đúng phạm vi yêu cầu, để lại
quyết định implement (hay không) cho bước sau.
