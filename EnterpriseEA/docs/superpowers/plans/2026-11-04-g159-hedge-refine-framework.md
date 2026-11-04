# G159: tinh chỉnh hedge — điểm hedge, cắt lãi / lỗ theo cặp, TP và gồng, input / output — khung kế hoạch (04/11/2026)

Viết **trước khi có kết quả G158** ([kế hoạch G158](2026-11-04-g158-hedge-recovery.md)).

Người dùng (04/11) muốn tiếp tục:
- tìm điểm hedge;
- tinh chỉnh cách cắt lãi / lỗ, TP và gồng;
- bổ sung input / output để hệ thống làm tốt hơn.

Mọi module dưới đây được định nghĩa ngay bây giờ. Sau G158 chỉ được làm hai việc: **chọn thứ tự chạy** và **chọn cấu hình nền** (cấu hình tốt
nhất của G158 trên kỳ chọn). Không được đổi định nghĩa module theo kết quả G158.

## 1. Vì sao cần các module này

Từ lần chạy thử G158 (chưa phải kết luận), hệ thống bồi lệnh không SL chết ở bốn chỗ:

1. **Bồi lệnh ngược một xu hướng mạnh**: lot tăng đúng lúc giá chạy một chiều.
2. **Swap**: rổ giữ lâu trả 5.000–10.000 USD swap. Hedge thì cả hai chân cùng trả.
3. **Thả nổi sâu** (có lúc −55.000 USD trên vốn 10.000) trước khi kịp về mục tiêu.
4. **Chỉ chốt khi cả rổ đạt mục tiêu**: không có cơ chế giảm tải dần.

Mỗi module dưới đây nhắm vào một trong bốn chỗ đó.

## 2. Module điểm hedge (H) — lúc nào mở lệnh ngược

Thay cho "mở ngược ở mép vùng cố định" (R2 của G158):

| Mã | Điểm hedge | Ý tưởng |
|---|---|---|
| H1 | **Chế độ D1 đổi chiều** ngược rổ (R1 của XauRegime) | chỉ hedge khi xu hướng lớn thật sự quay đầu |
| H2 | **Phá cấu trúc H4 ngược chiều** (đóng qua swing H4 gần nhất) | price action: cấu trúc gãy mới hedge |
| H3 | **Chạm OB H4 ngược chiều** (định nghĩa OB của G158) | hedge tại vùng cung / cầu của bên kia |
| H4 | Giá đã đi ngược **≥ k × ADR20** từ lúc mở rổ (k ∈ {1; 1,5}) | cạn đà không xảy ra thì khóa lại |
| H5 | **Cú bung quanh tin USD HIGH** ngược rổ (nến H1 ≥ 2 ATR trong ± 1 giờ quanh tin) | khóa trước cú tin |

**Khóa / mở khóa (lock / unlock):**
- Khi H1–H5 xảy ra, mở lệnh ngược **cùng tổng lot** với phía đang lỗ (khóa: thả nổi không tăng thêm).
- Mở khóa (đóng lệnh hedge) khi:
  - (U1) giá về OB H4 / đáy cấu trúc **cùng chiều rổ gốc**;
  - hoặc (U2) chế độ D1 quay lại chiều rổ gốc;
  - hoặc (U3) lệnh hedge đạt +1 × bước S.
- Không có SL nào. Nhưng thả nổi bị đóng băng trong lúc khóa; chỉ còn swap chạy.

## 3. Module cắt lãi / lỗ theo cặp (P) — giảm tải dần

| Mã | Quy tắc |
|---|---|
| P0 | như G158: chỉ cắt khi cả rổ đạt mục tiêu |
| P1 | **Cặp liên tục**: mỗi khi (lệnh lời nhất + lệnh lỗ nhất) có tổng ≥ 0, đóng cả cặp |
| P2 | **Cặp có phần dư**: như P1, nhưng chỉ cần tổng ≥ −0,1 × S × lot gốc × 100 (chấp nhận lỗ nhỏ để giảm lot nhanh) |
| P3 | **Thang chốt một phần**: lời ròng đạt +0,5 / +1 / +1,5 mục tiêu thì đóng 1/3 lot ròng mỗi nấc, từ lệnh lỗ nhất trở đi |

## 4. Module TP và gồng (X) — mở rộng X0–X4 của G158

| Mã | Cách thoát lệnh chạy | Nguồn |
|---|---|---|
| X5 | **Trail theo swing H4** (dời mức thoát dưới đáy swing H4 gần nhất) | G103 (giữ theo cấu trúc) |
| X6 | **Giữ theo hộp nghỉ H1** (chỉ dời khi giá phá khỏi vùng nghỉ) | G103 BOX |
| X7 | **TP ở gốc nhịp trước** (ORG, 7–12R) | G104 |
| X8 | **Thoát theo thời gian và swap**: mục tiêu giảm dần khi swap tích lũy, đủ trả swap thì đóng | mới |
| X9 | **Chốt một nửa ở +1S, phần còn lại trail 3 ATR H1** | kết hợp X1 / X2 |

## 5. Bộ lọc thêm vào (F) — input mới cho quyết định bồi lệnh

| Mã | Input | Dùng thế nào |
|---|---|---|
| F1 | **Chế độ D1** (R1) | chỉ bồi cùng chiều xu hướng D1; ngược D1 thì chuyển sang hedge (H) thay vì bồi |
| F2 | **Phân vị ATR D1** (biến động) | biến động > p90 thì dừng bồi, giãn bước S × 1,5 |
| F3 | **Lịch tin** | không bồi trong ± 30 phút quanh tin USD HIGH |
| F4 | **Bước theo cấu trúc** | đặt lệnh bồi ở swing H4 / OB / số tròn gần nhất thay vì bước ATR cố định |
| F5 | **Mức ký quỹ tối thiểu để bồi** | mức ký quỹ < 300 % thì không bồi nữa (đây không phải SL: không đóng lệnh) |
| F6 | **Trần lot** | tổng lot mở ≤ L_max (ví dụ 1,0 với vốn 10.000) |

## 6. Output — để đánh giá và để chạy trong EA

**Đo trong nghiên cứu (mỗi rổ):**
- số lệnh, lot tối đa;
- thả nổi sâu nhất, thời gian giữ;
- swap đã trả;
- mức ký quỹ thấp nhất;
- lý do kết thúc (mục tiêu / cặp / lệnh chạy thoát / cháy);
- số lần khóa / mở khóa.

**Đo cho cả tài khoản:**
- số lần cháy, xác suất cháy trong 12 tháng (mở tài khoản mới mỗi tháng);
- lãi ròng, sụt vốn theo giá bất lợi trong nến;
- **expected shortfall** (TB 5 % rổ tệ nhất);
- thời gian nằm dưới đỉnh vốn;
- phần lãi đến từ lệnh đầu / lệnh bồi / lệnh chạy.

**Nếu sau này đưa vào EA (chỉ sau khi đạt):**
- **Input:** lot gốc, cách tính bước (ATR / cấu trúc), hệ số nhân, số lệnh tối đa, trần lot, kiểu điểm hedge, ngưỡng cặp, kiểu lệnh chạy, lọc
  tin, ký quỹ tối thiểu để bồi.
- **Output:**
  - nhật ký bot (mở / bồi / hedge / cặp / thoát, kèm thả nổi và mức ký quỹ);
  - `bots_status.json`: thả nổi rổ, mức ký quỹ, giá bồi kế tiếp, trạng thái khóa;
  - Telegram cảnh báo khi mức ký quỹ < 500 % / 300 % / 150 %.

## 7. Cách test (như G158)

- **Dữ liệu và mô hình tài khoản:** H1 thật 2018–10/2026, chọn trên 2018–2022, kiểm trên 2023–2026; cùng mô hình tài khoản (ký quỹ, stop-out,
  swap).
- **Đối chứng:** entry ngẫu nhiên chạy cùng module.
- **Kiểm thêm:**
  - xác suất cháy 12 tháng;
  - swap −60 và chi phí × 1,5;
  - đòn bẩy 1:100;
  - stress D1 2010–2018 (bi quan);
  - láng giềng tham số.
- **Mỗi module so với cấu hình nền G158**, thêm từng module một rồi mới tổ hợp. Tối đa 3 module trong một tổ hợp, để tránh dò quá nhiều.
- **Đạt** như (B) của G158. Thêm hai điều kiện:
  - expected shortfall không tệ hơn cấu hình nền;
  - swap trả không quá 30 % tổng lãi gộp.

## 8. Thứ tự đề xuất (chốt sau G158)

1. **F1 + H1 / H2** (không bồi ngược xu hướng D1, hedge khi cấu trúc gãy): nhắm vào nguyên nhân cháy số 1.
2. **P1 / P2** (cắt cặp liên tục): nhắm vào thả nổi sâu.
3. **X8** (thoát theo swap) và **F5 / F6** (ký quỹ tối thiểu, trần lot).
4. Cuối cùng: X5–X7, X9 cho phần gồng.

Kế hoạch chi tiết từng vòng (G159a, G159b...) viết riêng trước mỗi lần chạy. Không chạy module nào khi chưa có kế hoạch vòng đó.
