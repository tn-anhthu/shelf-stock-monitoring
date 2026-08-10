# Literature Review: Shelf Monitoring & Product Recognition


### 1. Shelf Management: A deep learning-based system for shelf visual monitoring

- Tác giả: Pietrini, Paolanti, Mancini, Frontoni, Zingaretti (2024)
- Tạp chí: *Expert Systems with Applications*, vol 255, 124635. Nhà xuất bản: Elsevier
- DOI: [10.1016/j.eswa.2024.124635](https://doi.org/10.1016/j.eswa.2024.124635)
- Code + dataset: [github.com/rokopi-byte/shelf_management](https://github.com/rokopi-byte/shelf_management)

**Vì sao liên quan:** pipeline gần nhất với ShelfSense: detect sản phẩm (RetinaNet) → detect hàng kệ (Deep Hough Transform) → nhận diện SKU (MobileNetV3 + triplet loss + FAISS). 

---

### 2. LSR-YOLO: A lightweight and fast model for retail products detection

- Tác giả: Zhao, Solihin, Yang, Cai, Chow, Handayani, Prabuwono (2025)
- Tạp chí: *PLOS ONE*, 20(10): e0334216
- DOI: [10.1371/journal.pone.0334216](https://doi.org/10.1371/journal.pone.0334216)

**Lưu ý đã thống nhất trước đó:** không có source code public cho chính kiến trúc LSR-YOLO, chỉ có Data Availability (Locount + COCO), không có Code Availability. Không khuyến nghị implement lại kiến trúc custom (DWConv+CSPHet-CBAM+ADown+pruning) cho MVP 5 tuần.

---

### 3. Real-time retail planogram compliance application using computer vision and virtual shelves

- Tạp chí: *Scientific Reports* (Nature Portfolio), 2025
- Link: [nature.com/articles/s41598-025-27773-5](https://www.nature.com/articles/s41598-025-27773-5)

**Vì sao liên quan:** deploy thật ở quy mô 7,000+ cửa hàng 7-Eleven Taiwan, số liệu định lượng rõ ràng (shelf detect mAP50 99.41%, product detect mAP50 95.7%), có kỹ thuật few-shot learning (5 ảnh/class vẫn đạt top-1 98.39%), liên quan trực tiếp tới bài toán "thêm SKU mới không cần train lại" mà ShelfSense đang làm.

---

### 4. Enhanced Out-of-Stock Detection in Retail Shelf Images Based on Deep Learning

- Tạp chí: *Sensors* (MDPI), 24(2):693, 2024
- DOI: [10.3390/s24020693](https://doi.org/10.3390/s24020693)


**Vì sao liên quan:** bài toán out-of-stock detection, có AP cụ thể (86.3% kệ trống hoàn toàn, 83.7% trống mặt trước).

---

### 5. Precise Detection in Densely Packed Scenes (SKU-110K)

- Tác giả: Goldman, Herzig, Eisenschtat, Goldberger, Hassner (CVPR 2019)
- arXiv: [1904.00853](https://arxiv.org/abs/1904.00853)
- Code: [github.com/eg4000/SKU110K_CVPR19](https://github.com/eg4000/SKU110K_CVPR19)

**Vì sao liên quan:** đây chính là dataset mà pj đang fine-tune YOLO nano lên (spec dòng 186, recall 0.782), bài gốc tạo ra benchmark này, đáng đọc kỹ methodology gốc.

---

### 6. Object detection in smart indoor shopping using an enhanced YOLOv8n algorithm

- Tác giả: Zhao, Yang, Cao, Cai, Maryamah, Solihin (2024)
- Tạp chí: *IET Image Processing*, 18(14):4745-4759
- DOI: [10.1049/ipr2.13284](https://doi.org/10.1049/ipr2.13284)

**Vì sao liên quan:** đây là bài "tiền thân" của nhóm tác giả LSR-YOLO (cùng Solihin, Zhao), có thể có chi tiết implementation dễ tiếp cận hơn bản LSR-YOLO sau này.

