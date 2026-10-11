# G98: mở rộng bối cảnh vào lệnh + giữ lệnh theo phản ứng (không TP cố định) — train và validate

Ngày 11/10/2026. Ý của người dùng (chart 12–20/03/2026): không cắt lệnh bằng TP/SL sớm, quản lý theo phản ứng và bối cảnh của mô hình, giữ để ăn mở biên; không bó vào điều kiện S07 hiện có.

Script: `research/long/g98_context.py`. XAUUSD M15 và H1 (H1 dựng từ M15), cả hai chiều. Kỳ test 07/2025–06/2026 **chưa mở**: không lệnh nào được bắt đầu trong kỳ đó, kể cả ví dụ 12/03/2026.

## Thiết kế

**Điểm vào:** bản "sớm" của G97, xét ở nến M15 đóng, không chờ H1 đóng.
- Giá đóng vượt cả 4 EMA (không cần xếp thứ tự).
- DI tách ≥ 10 theo chiều lệnh, ADX đang tăng.
- Giá ở nửa theo chiều lệnh của nến M30 đang chạy.

**Bối cảnh (mỗi lần dùng một):**

| Mã | Bối cảnh |
|---|---|
| X0 | không lọc |
| X1 | nến H1 trước đóng đúng phía EMA200 H1 |
| X2 | nến H1 trước đóng đúng phía EMA55 H1 |
| X3 | có nén trước đó (ADX M15 thấp nhất trong 16 nến ≤ 25) |
| X4 | chế độ D1 (EMA50 có độ dốc, theo G96) |
| X5 | cấu trúc H1: đáy sau cao hơn đáy trước (mua) / đỉnh sau thấp hơn đỉnh trước (bán) |

**Mốc hủy cấu trúc (cũng là 1R):** cực trị M15 của 16 nến phía ngược chiều ± 0,1 ATR.

**Cách giữ lệnh (không TP, tối đa 10 ngày):**

| Mã | Cách giữ |
|---|---|
| S07 | đóng ngược EMA55 M15; sau 3R dùng EMA100 (luật S07 hiện tại, để tham chiếu) |
| H1E | trước +1R: đóng ngược EMA100 M15; sau +1R: chỉ thoát khi **H1 đóng ngược EMA55 H1** |
| SWG | dời stop theo từng đỉnh/đáy swing H1 đã xác nhận |
| FIB | sau +1R: H1 đóng hồi quá 61,8% nhịp hiện tại |
| CHD | trail chandelier 3 ATR H1 |
| ADX | sau +1R: ADX H1 ≥ 45 quay đầu, DI H1 cắt ngược, hoặc EMA55 H1 |

**Bồi lệnh (A1):** lệnh gốc ≥ +1R; giá nghỉ (ADX M15 ≤ 25) rồi có tín hiệu mới cùng chiều → thêm một lệnh, tối đa 2 lệnh bồi, thoát cùng lệnh gốc.

**Chi phí:** spread theo từng nến.

## Kết quả toàn lưới (72 ô mỗi chiều)

| Chiều | Ô dương ở train | Ô dương ở validate | Ô dương cả hai |
|---|---|---|---|
| Mua | 60/72 | 72/72 | 60 |
| Bán | 25/72 | **0/72** | 0 |

- Cách giữ lệnh tốt nhất trung bình là CHD: +0,09R ở train, +0,12R ở validate; có bồi lệnh thì +0,05 / +0,36.
- Bán dương ở train (2021–23 có đợt giảm 2022) nhưng âm toàn bộ ở validate.

## Đối chứng công bằng

Vào lệnh ở thời điểm ngẫu nhiên, nhưng giá cũng đã vượt cả 4 EMA và trong cùng bối cảnh, cùng cách giữ lệnh, 40 lần. Đo cả R/lệnh và lãi/lỗ theo ATR (không phụ thuộc vị trí stop).

| Ô | Train R (ngẫu nhiên, p) | Train ATR (ngẫu nhiên, p) | Validate R (ngẫu nhiên, p) | Validate ATR (ngẫu nhiên, p) |
|---|---|---|---|---|
| **Mua X5 H1E** | **+0,10** (+0,03, **0,03**) | **+0,26** (+0,03, **0,00**) | **+0,49** (+0,30, **0,00**) | **+1,72** (+1,11, **0,00**) |
| Mua X1 H1E | +0,11 (+0,08, 0,23) | +0,38 (+0,21, 0,03) | +0,39 (+0,33, 0,12) | +1,32 (+0,92, 0,00) |
| Mua X1 CHD | +0,20 (+0,21, 0,68) | +0,71 (+0,80, 0,82) | +0,40 (+0,37, 0,45) | +1,54 (+1,22, 0,00) |
| Mua X4 CHD | +0,21 (+0,25, 0,82) | +0,91 (+1,09, 0,90) | +0,44 (+0,38, 0,23) | +1,80 (+1,42, 0,00) |
| Mua X5 CHD + bồi | +0,19 (+0,15, 0,45) | +0,46 (+0,38, 0,38) | +1,02 (+0,98, 0,25) | +3,63 (+3,48, 0,40) |
| Bán X5 SWG + bồi | +0,24 (+0,16, 0,15) | +0,77 (+0,29, 0,03) | −0,09 (−0,25, 0,03) | −0,47 (−0,85, 0,10) |
| Bán X1 H1E | −0,01 | −0,11 | −0,14 | −0,59 |

## Đọc kết quả

1. Các ô mua với CHD lãi cao nhưng **vào ngẫu nhiên trong cùng bối cảnh cũng lãi như vậy**. Lãi đến từ bối cảnh (vàng tăng) và cách giữ lệnh, không đến từ điểm vào.
2. **Mua X5 H1E** là ô duy nhất mà điểm vào thắng vào ngẫu nhiên ở **cả train lẫn validate, theo cả hai thước đo** (p ≤ 0,03). Mô tả: cấu trúc H1 đang tạo đáy cao dần; vào sớm ở M15 khi giá vượt các EMA, DI tách, ADX tăng; trước +1R thoát nếu M15 đóng dưới EMA100; sau +1R chỉ thoát khi H1 đóng dưới EMA55 H1. Giữ trung vị khoảng 7 giờ, lệnh tốt nhất đạt +18R (train) và +22R (validate).
3. **Bán:** không ô nào dương ở validate. Khớp với G69–G96.
4. Lưu ý: X5 H1E được nhận ra **sau khi đã xem validate**, không phải ô đứng đầu theo train. Vì vậy nó phải được xác nhận trên kỳ test kín bằng kế hoạch đăng ký trước.
