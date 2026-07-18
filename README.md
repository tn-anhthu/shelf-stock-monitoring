# Inventory-based Lending Signal for Merchants

## Concept
Shop owner chụp ảnh kệ hàng → hệ thống detect + đếm sản phẩm → ước tính giá trị tồn kho
→ giá trị này được dùng làm ví dụ minh hoạ cho "alternative data" trong quyết định cho vay
working-capital cho nhà bán lẻ nhỏ / informal retailer.

> ⚠️ **Lưu ý quan trọng:** phần "signal cho vay vốn" trong repo này CHỈ là minh hoạ concept,
> KHÔNG phải một model chấm điểm tín dụng (credit scoring) thật. Không nên hiểu đây là hệ thống
> đánh giá rủi ro tín dụng hoàn chỉnh.

## Pipeline
1. **Detection (localization)** — trên tập SKU-110K (dense/overlapping shelf objects),
   chạy local trên M4 (`device='mps'`) hoặc Colab. SKU-110K đã có sẵn ground-truth
   bounding boxes nên không cần Autodistill để label chính dataset này — trước khi
   fine-tune riêng, benchmark xem checkpoint có sẵn (YOLOv8 community) hoặc detector
   zero-shot (Grounding DINO) có đủ dùng không (xem
   `docs/detection-notes/2026-07-17-detection-benchmark-results.md`). Autodistill
   (Grounding DINO + SAM) chỉ cần thiết sau này nếu tự chụp ảnh kệ hàng Việt Nam để
   fine-tune thêm (ảnh đó chưa có label sẵn).
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
- [x] Detection benchmark harness: `src/detection/benchmark/` — metrics module (IoU/precision/recall,
      unit-tested), SKU-110K subset loader, wrappers for checkpoint (1b) và zero-shot (1c) candidates,
      report + visualize scripts.
- [x] Detection benchmark run trên máy thật (M4 `mps`, 50 ảnh SKU-110K) → cả 1b (recall 0.17)
      và 1c (recall 0.09) đều dưới ngưỡng 0.45 → quyết định: fallback 1a (fine-tune YOLO). Xem
      `docs/detection-notes/2026-07-17-detection-benchmark-results.md`.
- [x] Detection: fine-tune YOLO nano trên SKU-110K (1a) — recall 0.782 trên 50 ảnh
      eval, đạt ngưỡng 0.6 (precision 0.745). Xem
      `docs/detection-notes/2026-07-17-yolo-finetune-results.md`. Phase 1 (Detection)
      hoàn tất.
- [x] Classification benchmark: CLIP vs SigLIP2 zero-shot retrieval trên subset RPC
      (Retail Product Checkout) — CLIP top-1 0.295, SigLIP2 top-1 0.676. Chọn SigLIP2.
      Xem `docs/classification-notes/2026-07-18-classification-benchmark-results.md`.
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
