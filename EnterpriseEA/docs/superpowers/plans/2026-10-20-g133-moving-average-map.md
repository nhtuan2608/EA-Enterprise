# G133: "bảng tra MA" (EMA 5/10/20, SMA 50/100/200, golden cross) trên vàng, khung nhỏ và khung lớn — kế hoạch đăng ký trước (20/10/2026)

## Vì sao

Người dùng gửi bảng tra MA phổ biến (Steve Burns): EMA5 động lượng, EMA10 xu hướng ngắn, EMA20 giá hay quay về, SMA50 hỗ trợ trong xu hướng tăng, SMA100 canh mua khi điều chỉnh, SMA200 đổi xu hướng, golden cross SMA50/200.

Phần lớn các ý này đã được kiểm dưới dạng tương đương (xem trả lời 20/10). G133 kiểm **ba phần còn chưa kiểm**, trên **khung nhỏ và khung lớn**.

## Dữ liệu, chi phí, kỳ

- **Dữ liệu**: XAUUSD M15 (từ 08/2021). M30, H1, H4, D1 dựng từ M30 (từ 03/2018) theo giờ server.
- **MA**: EMA5/10/20, SMA50/100/200 tính trên chính khung. ATR14.
- **Chi phí khắt khe**: spread nến vào/ra + trượt 0,5 × spread trung vị mỗi chiều + $6/lot.

**Kỳ:**

| Khung | Train | Validate | Test |
|---|---|---|---|
| M15 | 08/2021–2023 | 2024–2025 | **2026, mở một lần** cho ô được chọn |
| Khung khác | 03/2018–2021 | 2022–2025 | **2026, mở một lần** cho ô được chọn |

- 2026 chưa dùng cho các ý trong G133.
- Mỗi chiều một lệnh mỗi lúc. Báo cáo **mua và bán riêng**.

## Phần 1 — "mua khi điều chỉnh về SMA50 / SMA100" (bán đối xứng)

**Khung**: M15, M30, H1, H4, D1.

**Trạng thái** (ở nến tín hiệu):
- Mua: golden (SMA50 > SMA200) và giá đóng > SMA200.
- Bán: death (SMA50 < SMA200) và giá đóng < SMA200.

**Tín hiệu mua** ở nến i:
- nến trước đóng trên MA;
- đáy nến i chạm MA (đáy ≤ MA);
- nến i đóng lại trên MA.

**Lệnh:**
- Vào ở giá mở nến i+1.
- SL = đáy nến i − 0,1 ATR; khoảng SL tối thiểu 0,5 ATR.

**Biến thể** (4 mỗi khung):

| Thành phần | Lựa chọn |
|---|---|
| MA | SMA50 / SMA100 |
| Thoát X1 | TP 2R |
| Thoát X2 | giữ tới khi nến đóng dưới EMA20 (đóng ở giá mở nến kế) |

- Mọi lệnh tối đa 100 nến.

## Phần 2 — golden / death cross làm bộ lọc cho S07

- **Lệnh**: chân lệnh S07 (sổ G89/G107, giờ UTC đổi sang giờ server).
- **Nhãn**: tại lúc vào, trạng thái SMA50 / SMA200 của nến đã đóng gần nhất **cùng chiều lệnh** (mua khi golden, bán khi death).
- **Khung của nhãn**: H1 / H4 / D1, tức 3 bộ lọc.
- **Giữ bộ lọc** (như G79): nhóm giữ có R/lệnh cao hơn nhóm bỏ ở cả train (03/2018–2021) và validate (2022–2025), và còn ≥ 40% số lệnh.
- **Test 2026**: bộ lọc được giữ chỉ đạt khi nhóm giữ > nhóm bỏ trên 2026.
- VHedge là lệnh hedge hai chiều nên không gắn chiều được. Không xét.

## Phần 3 — scalp "chuỗi EMA ngắn" (bán đối xứng)

**Khung**: M15, M30, H1.

**Bối cảnh khung lớn**: giá đóng của nến đã đóng gần nhất của khung lớn nằm trên SMA200 của nó (bán: dưới).

| Khung vào lệnh | Khung lớn |
|---|---|
| M15, M30 | H4 |
| H1 | D1 |

**Tín hiệu mua** ở nến i:
- EMA5 > EMA10 > EMA20 ở nến i−1;
- đáy nến i chạm EMA20;
- nến i đóng trên EMA20;
- vẫn EMA10 > EMA20.

**Lệnh:**
- Vào ở giá mở nến i+1.
- SL = đáy nến i − 0,1 ATR; khoảng SL tối thiểu 0,5 ATR.

**Biến thể** (2 mỗi khung):

| Mã | Thoát |
|---|---|
| Y1 | TP 1,5R |
| Y2 | đóng khi nến đóng dưới EMA10 |

- Mọi lệnh tối đa 48 nến.

## Đối chứng (phần 1 và 3)

**Vào ngẫu nhiên công bằng**: mỗi lệnh thật được thay bằng một lệnh cùng chiều, cùng giờ trong ngày, ở một ngày khác cùng kỳ.
- Cùng khoảng SL tính theo ATR.
- Cùng cách thoát.
- Lặp 100 lần. p = tỷ lệ lần ngẫu nhiên ≥ thật.

## Chọn (phần 1 và 3, từng ô = biến thể × khung, mua + bán gộp)

Một ô được chọn khi đủ cả ba:
1. R/lệnh > 0 ở cả train và validate;
2. ≥ 20 lệnh mỗi kỳ;
3. p validate < 0,10.

**Test 2026**: mỗi ô được chọn chạy một lần; **đạt** khi R/lệnh > 0, cận dưới bootstrap 90% > 0, và p test < 0,10.

## Đầu ra

`research/long/g133_ma_map.py`, báo cáo `reports/2026-10-20-g133-moving-average-map.md`.
