# Literature Review — Shelf Monitoring & Product Recognition


### 1. Shelf Management: A deep learning-based system for shelf visual monitoring

- Tác giả: Pietrini, Paolanti, Mancini, Frontoni, Zingaretti (2024)
- Tạp chí: *Expert Systems with Applications*, vol 255, 124635. Nhà xuất bản: Elsevier
- DOI: [10.1016/j.eswa.2024.124635](https://doi.org/10.1016/j.eswa.2024.124635)
- Code + dataset: [github.com/rokopi-byte/shelf_management](https://github.com/rokopi-byte/shelf_management)

**Xếp hạng tạp chí:** SCImago **Q1** (2024), SJR **1.854**, CiteScore **12.2**, Impact Factor
**10.48** (tăng 12.81% so với 2023), h-index **290**. Đây là tạp chí uy tín cao trong nhóm
Computer Science / AI Applications, thuộc Elsevier.

**Vì sao liên quan:** pipeline gần nhất với ShelfSense — detect sản phẩm (RetinaNet) → detect
hàng kệ (Deep Hough Transform) → nhận diện SKU (MobileNetV3 + triplet loss + FAISS). 

---

### 2. LSR-YOLO: A lightweight and fast model for retail products detection

- Tác giả: Zhao, Solihin, Yang, Cai, Chow, Handayani, Prabuwono (2025)
- Tạp chí: *PLOS ONE*, 20(10): e0334216
- DOI: [10.1371/journal.pone.0334216](https://doi.org/10.1371/journal.pone.0334216)

**Xếp hạng tạp chí:** SCImago **Q1** (multidisciplinary, 2024), SJR **0.803**. Peer-reviewed,
có "Peer Review History" công khai (đặc trưng PLOS) — minh bạch hơn phần lớn journal khác dù
SJR thấp hơn ESWA.

**Lưu ý đã thống nhất trước đó:** không có source code public cho chính kiến trúc LSR-YOLO —
chỉ có Data Availability (Locount + COCO), không có Code Availability. Không khuyến nghị
implement lại kiến trúc custom (DWConv+CSPHet-CBAM+ADown+pruning) cho MVP 5 tuần.

---

### 3. Real-time retail planogram compliance application using computer vision and virtual shelves

- Tạp chí: *Scientific Reports* (Nature Portfolio), 2025
- Link: [nature.com/articles/s41598-025-27773-5](https://www.nature.com/articles/s41598-025-27773-5)

**Xếp hạng tạp chí:** SCImago **Q1** (2024), SJR **0.874**, Impact Factor **4.08**. Thuộc
Nature Portfolio, multidisciplinary, peer-reviewed.

**Vì sao liên quan:** deploy thật ở quy mô 7,000+ cửa hàng 7-Eleven Taiwan — số liệu định
lượng rõ ràng (shelf detect mAP50 99.41%, product detect mAP50 95.7%), có kỹ thuật few-shot
learning (5 ảnh/class vẫn đạt top-1 98.39%) — liên quan trực tiếp tới bài toán "thêm SKU mới
không cần train lại" mà ShelfSense đang làm.

---

### 4. Enhanced Out-of-Stock Detection in Retail Shelf Images Based on Deep Learning

- Tạp chí: *Sensors* (MDPI), 24(2):693, 2024
- DOI: [10.3390/s24020693](https://doi.org/10.3390/s24020693)

**Xếp hạng tạp chí:** SCImago liệt kê best quartile **Q1**, SJR **0.764**, nhưng theo Journal
Citation Reports (Clarivate) 2024 thì *Sensors* rơi vào **Q2** ở cả 3 category chính
(Instruments and Instrumentation; Chemistry, Analytical; Engineering, Electrical and
Electronic). Chị lưu ý thêm: MDPI là nhà xuất bản có volume bài rất lớn và từng bị giới học
thuật đặt câu hỏi về tốc độ review nhanh bất thường ở một số journal — bản thân *Sensors* nói
riêng vẫn được xem là hợp lệ/không nằm trong danh sách predatory, nhưng nên đọc kỹ methodology
thay vì chỉ tin vào quartile.

**Vì sao liên quan:** đúng bài toán out-of-stock detection, có AP cụ thể (86.3% kệ trống hoàn
toàn, 83.7% trống mặt trước).

---

### 5. Precise Detection in Densely Packed Scenes (SKU-110K)

- Tác giả: Goldman, Herzig, Eisenschtat, Goldberger, Hassner — CVPR 2019
- arXiv: [1904.00853](https://arxiv.org/abs/1904.00853)
- Code: [github.com/eg4000/SKU110K_CVPR19](https://github.com/eg4000/SKU110K_CVPR19)

**Xếp hạng venue:** đây là **conference paper**, không phải journal nên không có SJR/quartile.
CVPR (Conference on Computer Vision and Pattern Recognition) là 1 trong 3 hội nghị hàng đầu thế
giới về computer vision (cùng ICCV, ECCV), tỉ lệ chấp nhận bài thường dưới 25-30%, được xem
tương đương venue hạng cao nhất trong ngành CV theo bảng xếp hạng CORE (CORE A*). Độ uy tín
thực tế cao hơn phần lớn journal Q1 trong domain thị giác máy tính.

**Vì sao liên quan:** đây chính là dataset em đang fine-tune YOLO nano lên (spec dòng 186,
recall 0.782) — bài gốc tạo ra benchmark này, đáng đọc kỹ methodology gốc.

---

### 6. Object detection in smart indoor shopping using an enhanced YOLOv8n algorithm

- Tác giả: Zhao, Yang, Cao, Cai, Maryamah, Solihin (2024)
- Tạp chí: *IET Image Processing*, 18(14):4745-4759
- DOI: [10.1049/ipr2.13284](https://doi.org/10.1049/ipr2.13284)

**Xếp hạng tạp chí:** SCImago **Q2** (2024), SJR **0.496**. Peer-reviewed, thuộc Institution of
Engineering and Technology (IET) — uy tín vừa phải, thấp hơn nhóm Q1 ở trên nhưng vẫn là venue
hợp lệ, không nằm trong nhóm đáng ngờ.

**Vì sao liên quan:** đây là bài "tiền thân" của nhóm tác giả LSR-YOLO (cùng Solihin, Zhao) —
có thể có chi tiết implementation dễ tiếp cận hơn bản LSR-YOLO sau này.

