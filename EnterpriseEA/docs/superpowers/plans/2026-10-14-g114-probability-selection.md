# G114: chọn lọc setup theo xác suất và kỳ vọng (EV) — kế hoạch đăng ký trước

Ngày 14/10/2026. Theo người dùng: không cần chính xác hoàn toàn, nhưng việc phân phối và chọn lọc setup phải dựa vào **xác suất xảy ra và xác suất thành công** của các yếu tố, không chỉ dựa vào việc yếu tố có xuất hiện hay không. Chạy sau G113. Kỳ như cũ: train 07/2024–03/2025, validate 04–12/2025 (FX tới 10/2025). **Test 2026 niêm phong.**

## 1. Đầu vào

Các sự kiện và lệnh đã có, kèm kết quả R:
- G109 S1/S2;
- G110 theo/ngược;
- G111 test vùng;
- G112 đuổi;
- các bản M15/M30 và spread = 0 của G113;
- kiểu ngày dự báo của G113.

## 2. Ba tầng xác suất (mọi ước lượng chỉ dùng dữ liệu trước tháng đang xét, cuốn chiếu)

1. **Tần suất xuất hiện (phân phối):** mỗi yếu tố (phân kỳ, phá cấu trúc H1, cạn volume, kiểu ngày, phiên, chế độ D1, FVG/vùng phía trước…) xuất hiện bao nhiêu lần mỗi ngày hoặc mỗi tuần, theo từng mã. Yếu tố quá hiếm (ít hơn 30 lần trong dữ liệu học) không được dùng để ra quyết định, chỉ để mô tả.
2. **Xác suất thắng có điều kiện** P(thắng | yếu tố), có co về mức chung khi mẫu nhỏ (thêm 30 lệnh giả ở mức chung). **Tỉ số hợp lý** LR = P(yếu tố | thắng) / P(yếu tố | thua) cho biết yếu tố đẩy xác suất lên hay xuống bao nhiêu.
3. **Xác suất tổng hợp:** ghép các yếu tố theo ba cách:
   - (a) cộng log-LR kiểu Bayes ngây thơ (đọc được, mỗi yếu tố một con số);
   - (b) hồi quy logistic có điều chuẩn;
   - (c) LightGBM.

   Cả ba được **hiệu chỉnh** bằng hồi quy isotonic, học trên các tháng trước.

## 3. Quyết định

- **EV** = p × (R trung bình khi thắng) − (1 − p) × (R trung bình khi thua). Tính theo kết quả thật của từng loại lệnh, đã gồm chi phí ở bản có spread.
- **Vào lệnh khi cận dưới của EV > 0.** Cận dưới tính từ khoảng tin cậy của p với cỡ mẫu tương ứng (Wilson 90%), không dùng con số trung bình.
- **Khi nhiều setup cùng lúc:** chọn setup có cận dưới EV cao nhất, mỗi mã một lệnh mỗi lúc.
- **Khối lượng:** một phần tư Kelly theo EV và phương sai R, có trần 1R mỗi lệnh. Báo cả bản khối lượng cố định để so sánh.

## 4. Đánh giá

- **Độ khớp xác suất:** đường cong khớp theo 10 nhóm, điểm Brier, log loss. So với mức chung và giữa train với validate. Xác suất không khớp thì không dùng để ra quyết định.
- **Lợi nhuận:** R/lệnh, tổng, DD, cận dưới 90%. So với:
  - chọn theo luật yếu tố (có/không);
  - chọn theo mô hình không hiệu chỉnh (top 10–20% như G110–G112);
  - chọn ngẫu nhiên cùng số lệnh (ngày khác, như đối chứng công bằng của G112).
- **Bảng LR** của từng yếu tố trên train và validate: yếu tố nào **ổn định** (LR cùng phía 1 ở cả hai kỳ, khoảng tin cậy không chứa 1).
- **Tiêu chí:** cận dưới EV > 0 thực hiện được ở cả hai kỳ, ít nhất 100 lệnh, hơn các đối chứng, xác suất khớp ở cả hai kỳ. Báo riêng từng mã và từng chiều.

## 5. Kiểm tra

- **Test:**
  - ước lượng xác suất chỉ dùng dữ liệu trước tháng;
  - co về mức chung khi mẫu nhỏ;
  - LR và cộng log-LR;
  - hiệu chỉnh isotonic;
  - cận dưới Wilson;
  - quyết định vào lệnh và khối lượng Kelly có trần;
  - mỗi mã một lệnh mỗi lúc.
- **Audit độc lập:** tính lại xác suất, LR, EV và quyết định cho các tháng và lệnh ngẫu nhiên bằng đếm thô.
