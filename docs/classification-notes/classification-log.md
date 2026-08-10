# Nhật ký Classification (Phase 2)

**Trạng thái hiện tại:** dùng **SigLIP2** (`google/siglip2-base-patch16-224`) làm model
embedding cho zero-shot retrieval, chưa có gì thay đổi từ quyết định ban đầu.

## 18/7/2026: So sánh CLIP vs SigLIP2

**Dataset:** RPC (`benjamintli/retail-product-checkout`), catalog lấy từ `train` split (ảnh 1 sản phẩm/tấm), test crop lấy từ `test` split (ảnh cảnh tính tiền nhiều sản phẩm, có ground-truth bbox + category). 

Tập con: 105 crop, 16 category, 48 ảnh catalog.

| Model | Top-1 accuracy | Top-5 accuracy | Thời gian suy luận/crop |
|---|---|---|---|
| CLIP (`openai/clip-vit-base-patch32`) | 0.295 | 0.743 | 0.012s |
| SigLIP2 (`google/siglip2-base-patch16-224`) | **0.676** | **0.952** | 0.025s |

**Quyết định: chọn SigLIP2.** 
Chênh lệch quá lớn để cân nhắc yếu tố phụ (thời gian suy luận CLIP nhanh hơn nhưng không đáng kể so với khoảng cách accuracy 38 điểm %). Đã kiểm tra trực quan 5 crop mẫu xác nhận không có lỗi pipeline (crop đúng là sản phẩm thật, category dự đoán hợp lý).

**Lưu ý về con số:** đo trên tập con 16/200 category của RPC, không suy ra được accuracy tuyệt đối ở quy mô đầy đủ 200 category (khả năng thấp hơn khi catalog lớn hơn). Kết luận đây là **thứ hạng tương đối** CLIP vs SigLIP2, không phải con số tuyệt đối.

## Bước tiếp theo (đã thực hiện ở Phase 3: ShelfSense MVP)

Tích hợp SigLIP2 embedding retrieval với catalog nhỏ tự tạo (không dùng RPC làm catalog chính thức nữa, xem `docs/specs/mvp-design.md` phần Catalog). RPC chỉ còn dùng làm bộ benchmark tham khảo cho quyết định chọn model ở trên.
