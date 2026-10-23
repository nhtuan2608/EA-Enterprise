# G154: máy dò ngẫu nhiên / tiến hóa tìm setup scalp vàng M15 — kế hoạch đăng ký trước (23/10/2026)

## Vì sao

Người dùng hỏi (23/10): đã có phương pháp ghép ngẫu nhiên nhiều khối luật để **sinh** ra setup scalp chưa? Chưa. Lệnh ngẫu nhiên mới chỉ được
dùng để **kiểm** setup. G154 làm máy dò, kèm đủ phép chống "tìm ra nhờ may":
- đối chứng chạy cùng máy dò trên dữ liệu đã cắt đứt quan hệ tín hiệu → kết quả;
- một kỳ máy dò không được nhìn;
- chuyển sang thị trường khác;
- chi phí harsh ngay từ lúc tìm.

Kết quả trước đó: G125 (scalp vàng) và G146–G149 (bản đồ, ô hành vi) đều không đạt. Khả năng đạt được đánh giá trước là thấp.

## Dữ liệu và kỳ

Nến M15 của MT5 (`data/m15v`), giờ server.

| Kỳ | Khoảng | Dùng cho |
|---|---|---|
| **tìm** | 20/07/2021 – 31/12/2023 | máy dò chỉ thấy kỳ này |
| **kiểm** | 01/01/2024 – 30/06/2026 | chấm top 20, quyết định |
| sau | 01/07/2026 – hết dữ liệu | chỉ báo cáo |
| BTC | 10/2022 – 06/2026 | chuyển thị trường |
| bạc | 02/2024 – 06/2026 | chuyển thị trường |

## Mô phỏng lệnh

- Tín hiệu ở giá đóng nến i, vào lệnh ở giá mở nến i+1 (mua theo ask = giá mở + spread).
- Khoảng SL = k × ATR14 (Wilder) của nến i.
- SL trước TP khi cả hai cùng chạm; nến mở vượt mức thì khớp ở giá mở; hết số nến tối đa thì thoát ở giá đóng. Lệnh bán thoát theo ask.
- Chi phí **harsh G68**: trượt giá 0,5 × spread trung vị mỗi chiều, commission × 2, spread × 3 quanh giờ rollover. Có báo thêm mức × 1,5.
- Một lệnh một lúc cho mỗi tổ hợp; lệnh mở chặn cả hai chiều.

## Không gian luật (cố định trước khi chạy)

Một tổ hợp gồm: **1 kích hoạt + tối đa 3 bộ lọc + 1 kiểu thoát**. Luật đối xứng: cùng một tổ hợp áp cho cả mua lẫn bán, máy dò không được chọn
chỉ một chiều.

**Kích hoạt (15)**:
- phá đỉnh/đáy 8 và 20 nến;
- quét thanh khoản 8 và 20 nến (xuyên qua rồi đóng lại vào trong);
- hồi về EMA20 khi EMA20/EMA50 cùng chiều;
- nến nhấn chìm; pin bar;
- đóng cắt qua VWAP ngày;
- phá biên Asia (sau 08:00);
- RSI14 thoát vùng 30/70;
- phá nến inside bar;
- 3 nến đà cùng chiều;
- phá đỉnh/đáy ngày trước;
- squeeze Bollinger rồi đóng ngoài dải;
- đóng quay lại vào trong dải Bollinger.

**Bộ lọc (12, mỗi bộ 2–4 lựa chọn)**:
- khung giờ (Asia 1–7, London 8–13, NY 14–18, muộn 19–22);
- chế độ D1 R1 (cùng / ngược / không ngược);
- phía EMA200 M15 (cùng / ngược);
- ATR14 / ATR100 (> 1,2 / < 0,8 / giữa);
- khoảng cách tới VWAP theo ATR (xa cùng chiều / xa ngược chiều / sát);
- ADX (> 25 / < 20);
- ngày trong tuần (bỏ thứ Sáu / bỏ thứ Hai);
- nến tín hiệu so với ATR (> 1,5 / < 0,7);
- RSI so với 50 (cùng / ngược);
- dốc EMA200 M15 trong 16 nến (cùng / ngược);
- vị trí so với biên Asia (ngoài cùng chiều / trong);
- spread / ATR < 0,03.

**Thoát (36)**: SL ∈ {0,5; 1; 1,5} ATR × TP ∈ {1; 1,5; 2; 3} R × tối đa {8; 16; 32} nến.

## Máy dò

- Thuật toán tiến hóa: quần thể 300, 40 thế hệ, chọn theo thi đấu (4), lai từng gen, đột biến 0,2 mỗi gen, giữ 20 tổ hợp tốt nhất mỗi thế hệ.
  Hạt giống cố định 154.
- **Điểm** trong kỳ tìm: t-stat của R harsh sau khi bỏ 5 lệnh lãi lớn nhất. Hợp lệ khi ≥ 150 lệnh, và mỗi chiều mua/bán có ≥ 30 lệnh.
- Kết quả máy dò: **top 20** tổ hợp khác nhau (không trùng kích hoạt + thoát + bộ lọc), theo điểm kỳ tìm.

## Đối chứng toàn máy dò (null)

- Chạy lại **y hệt** máy dò 50 lần. Mỗi lần, kết quả lệnh (R, thời gian giữ) bị **dịch vòng** đi 92 × m nến, với m ngẫu nhiên từ 20 tới số
  ngày − 20.
- Dịch theo bội của một ngày giao dịch vàng (92 nến M15), nên quan hệ giờ trong ngày gần như được giữ, còn quan hệ tín hiệu → kết quả bị cắt.
- Ghi lại điểm tốt nhất của mỗi lần.

## Đạt khi

**Điều kiện cả cuộc dò (G0)**: điểm tốt nhất thật > phân vị 95 % của 50 điểm tốt nhất null. Không qua G0 thì kết luận "máy dò không tìm được gì
hơn may", **dù** có tổ hợp qua các tiêu chí dưới.

**Từng tổ hợp trong top 20**, kỳ **kiểm**:
1. ≥ 100 lệnh, R/lệnh harsh > 0 và với chi phí × 1,5 > 0;
2. bỏ 5 lệnh lãi lớn nhất vẫn > 0;
3. hai chiều: mua và bán, chiều nào có ≥ 30 lệnh thì R/lệnh ≥ −0,05;
4. ≥ 55 % số quý dương (10 quý);
5. thắng lệnh vào ngẫu nhiên cùng chiều, cùng giờ server, cùng kiểu thoát, trong cùng kỳ. 1.000 lần, p ≤ 0,0025 (Bonferroni 0,05 / 20);
6. chuyển thị trường, cùng luật (mọi tham số tính theo ATR): BTC hoặc bạc có R/lệnh harsh > 0; thị trường còn lại không dưới −0,05. Chỉ tính
   thị trường có ≥ 50 lệnh.

Kỳ "sau" chỉ báo cáo.

## Nếu đạt

Đề xuất SHADOW forward như SQZ / W1. Người dùng đồng ý mới làm.

Script `research/long/g154_scalp_search.py`. Không chỉnh luật sau khi chạy.
