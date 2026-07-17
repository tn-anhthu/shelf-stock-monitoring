# Inventory-based Lending Signal for Merchants

## Concept
Shop owner chụp ảnh kệ hàng → hệ thống detect + đếm sản phẩm → ước tính giá trị tồn kho
→ giá trị này được dùng làm ví dụ minh hoạ cho "alternative data" trong quyết định cho vay
working-capital cho nhà bán lẻ nhỏ / informal retailer.

> ⚠️ **Lưu ý quan trọng:** phần "signal cho vay vốn" trong repo này CHỈ là minh hoạ concept,
> KHÔNG phải một model chấm điểm tín dụng (credit scoring) thật. Không nên hiểu đây là hệ thống
> đánh giá rủi ro tín dụng hoàn chỉnh.

## Pipeline
1. **Detection (localization)** — fine-tune YOLO (nano, transfer learning) trên tập SKU-110K
   (dense/overlapping shelf objects), chạy local trên M4 (`device='mps'`) hoặc Colab.
   Auto-labeling hỗ trợ bằng Autodistill (Grounding DINO + SAM).
2. **Classification** — crop từng box, dùng VLM embedding zero-shot (CLIP/SigLIP2) để match
   với catalog sản phẩm (retrieval-based, không cần train riêng cho từng SKU mới).
3. **Depth multiplier (human-in-the-loop)** — sau detect, người dùng xác nhận + nhập số lớp
   sản phẩm xếp sâu phía sau mỗi vị trí (giải quyết giới hạn 2D chỉ thấy mặt trước).
4. **Pricing** — map class → giá theo catalog → tổng giá trị tồn kho ước tính.
5. **(Optional demo only)** rule đơn giản: giá trị + biến động theo thời gian → "signal" minh hoạ.

## Human-in-the-loop flow (lean MVP)
- Detect xong → nếu confidence thấp ở ngăn/vị trí nào → 1 message tổng hợp theo ngăn kệ,
  gợi ý chụp lại rõ hơn (tối đa 1 vòng xác nhận, không multi-turn phức tạp).
- "Học từ feedback" liên tục / continual learning → để ở mục Future Work, không phải core MVP.

## Status
- [ ] Detection: fine-tune trên subset SKU-110K (streaming qua Hugging Face `datasets`)
- [ ] Classification: CLIP/SigLIP2 embedding matching + catalog ban đầu
- [ ] Depth multiplier UI
- [ ] Pricing aggregation
- [ ] Human-in-the-loop confirmation message

## Setup
- MacBook Pro M4, 16GB RAM — dùng `device='mps'` cho PyTorch/YOLO khi train local.
- Dataset nặng (SKU-110K) nên stream/subset thay vì tải full 13.6GB về máy.

## Future Work
- Mở rộng catalog vượt ngoài scope ban đầu qua crawl/tự chụp thêm reference images.
- Continual learning thật từ feedback user (không chỉ là UX loop).
- OCR trên bao bì để hỗ trợ phân biệt flavor/biến thể trong cùng brand.
