# G131c: đỉnh/đáy cạn đà sau nhiều lần RSI quá mua/quá bán — kết quả

Kế hoạch: `plans/2026-10-20-g131-rsi-exhaustion-top.md`. XAUUSD H4 (từ M30, 03/2018+). Train 03/2018–2021, validate 2022–2025. 2026 không phải test sạch (ví dụ thiết kế nằm trong 01–03/2026). Chi phí khắt khe. Ô: số lệnh / R mỗi lệnh (SL trên đỉnh test lại, thoát ở EMA200 H4 hoặc RSI cực trị bên kia).

## 18 biến thể

| Bối cảnh | Đỉnh | Vào | Train | Validate | Bán (train · val) | Mua (train · val) | Ngẫu nhiên validate | p | Chọn? |
|---|---|---|---|---|---|---|---|---|---|
| X1 | T1 | E1 | 18 / +0.34 | 23 / -0.32 | 12 / +0.84 · 18 / -0.65 | 6 / -0.68 · 5 / +0.86 | +nan | nan |  |
| X1 | T1 | E2 | 22 / +0.29 | 24 / -0.28 | 13 / +0.54 · 19 / -0.38 | 9 / -0.08 · 5 / +0.08 | +nan | nan |  |
| X1 | T1 | E3 | 25 / +0.34 | 33 / -0.31 | 16 / +0.57 · 26 / -0.53 | 9 / -0.08 · 7 / +0.49 | +nan | nan |  |
| X1 | T2 | E1 | 13 / +0.31 | 21 / -0.43 | 7 / +1.16 · 17 / -0.68 | 6 / -0.68 · 4 / +0.67 | +nan | nan |  |
| X1 | T2 | E2 | 17 / +0.51 | 21 / -0.17 | 8 / +1.18 · 17 / -0.29 | 9 / -0.08 · 4 / +0.35 | +nan | nan |  |
| X1 | T2 | E3 | 20 / +0.31 | 30 / -0.26 | 11 / +0.63 · 25 / -0.42 | 9 / -0.08 · 5 / +0.56 | +nan | nan |  |
| X2 | T1 | E1 | 10 / +0.66 | 16 / -0.49 | 5 / +1.93 · 13 / -0.71 | 5 / -0.61 · 3 / +0.48 | +nan | nan |  |
| X2 | T1 | E2 | 12 / +0.32 | 17 / -0.35 | 6 / +1.16 · 13 / -0.30 | 6 / -0.53 · 4 / -0.50 | +nan | nan |  |
| X2 | T1 | E3 | 14 / +0.29 | 22 / -0.48 | 8 / +0.90 · 17 / -0.58 | 6 / -0.53 · 5 / -0.12 | +nan | nan |  |
| X2 | T2 | E1 | 9 / +0.59 | 16 / -0.54 | 4 / +2.09 · 13 / -0.77 | 5 / -0.61 · 3 / +0.48 | +nan | nan |  |
| X2 | T2 | E2 | 10 / +0.58 | 13 / -0.12 | 4 / +2.24 · 10 / -0.05 | 6 / -0.53 · 3 / -0.33 | +nan | nan |  |
| X2 | T2 | E3 | 12 / +0.31 | 20 / -0.31 | 6 / +1.15 · 16 / -0.41 | 6 / -0.53 · 4 / +0.10 | +nan | nan |  |
| X3 | T1 | E1 | 11 / +0.74 | 19 / -0.50 | 8 / +1.14 · 15 / -0.66 | 3 / -0.33 · 4 / +0.10 | +nan | nan |  |
| X3 | T1 | E2 | 12 / +0.52 | 20 / -0.43 | 8 / +0.92 · 15 / -0.37 | 4 / -0.27 · 5 / -0.60 | +nan | nan |  |
| X3 | T1 | E3 | 15 / +0.37 | 26 / -0.34 | 11 / +0.60 · 20 / -0.36 | 4 / -0.27 · 6 / -0.27 | +nan | nan |  |
| X3 | T2 | E1 | 9 / +0.59 | 18 / -0.47 | 6 / +1.06 · 14 / -0.63 | 3 / -0.33 · 4 / +0.10 | +nan | nan |  |
| X3 | T2 | E2 | 8 / +0.95 | 17 / -0.44 | 5 / +1.54 · 12 / -0.37 | 3 / -0.02 · 5 / -0.60 | +nan | nan |  |
| X3 | T2 | E3 | 12 / +0.30 | 25 / -0.31 | 8 / +0.58 · 19 / -0.33 | 4 / -0.27 · 6 / -0.27 | +nan | nan |  |

Ngẫu nhiên / p chỉ tính cho biến thể dương ở cả hai kỳ với ≥ 10 lệnh mỗi kỳ.

## 2026 (không phải test sạch) — biến thể mặc định ('X1', 'T1', 'E3')

| Vào lệnh (server) | Chiều | R |
|---|---|---|
| 2026-01-02 16:00 | BÁN | -1.00 |
| 2026-01-19 16:00 | BÁN | -1.01 |
| 2026-01-30 04:00 | BÁN | +2.38 |
| 2026-05-05 04:00 | MUA | +5.44 |
| 2026-06-01 04:00 | MUA | -1.01 |

2026: 5 / +0.96 (bán 3 / +0.12, mua 2 / +2.22).

## Tất cả lệnh của biến thể đó (train + validate)

| Vào lệnh | Chiều | R | Kỳ |
|---|---|---|---|
| 2018-10-26 04:00 | BÁN | -1.02 | train |
| 2018-12-12 00:00 | BÁN | +1.55 | train |
| 2019-01-08 04:00 | BÁN | -1.02 | train |
| 2019-02-21 20:00 | BÁN | +1.30 | train |
| 2019-06-17 04:00 | BÁN | -1.02 | train |
| 2019-08-14 08:00 | BÁN | -1.01 | train |
| 2020-02-26 16:00 | BÁN | -1.01 | train |
| 2020-03-09 20:00 | BÁN | +1.79 | train |
| 2020-04-17 08:00 | BÁN | -1.01 | train |
| 2020-05-19 08:00 | BÁN | -1.01 | train |
| 2020-07-10 08:00 | BÁN | -1.01 | train |
| 2020-08-11 04:00 | BÁN | +1.27 | train |
| 2020-12-22 08:00 | BÁN | +1.27 | train |
| 2021-01-07 04:00 | BÁN | +1.68 | train |
| 2021-05-31 16:00 | BÁN | -1.03 | train |
| 2021-11-18 08:00 | BÁN | +9.46 | train |
| 2022-02-28 08:00 | BÁN | -1.01 | validate |
| 2022-03-10 04:00 | BÁN | +1.34 | validate |
| 2023-01-09 12:00 | BÁN | -1.02 | validate |
| 2023-01-18 20:00 | BÁN | -1.01 | validate |
| 2023-07-19 04:00 | BÁN | -1.03 | validate |
| 2023-07-24 00:00 | BÁN | -1.02 | validate |
| 2023-10-25 00:00 | BÁN | -1.03 | validate |
| 2023-11-21 12:00 | BÁN | -1.02 | validate |
| 2023-12-05 08:00 | BÁN | +1.38 | validate |
| 2024-01-03 00:00 | BÁN | +1.62 | validate |
| 2024-04-11 12:00 | BÁN | -1.01 | validate |
| 2024-04-16 12:00 | BÁN | -1.01 | validate |
| 2024-07-11 00:00 | BÁN | -1.01 | validate |
| 2024-07-24 04:00 | BÁN | -1.04 | validate |
| 2024-08-15 16:00 | BÁN | -1.01 | validate |
| 2024-08-26 08:00 | BÁN | -1.02 | validate |
| 2024-10-01 00:00 | BÁN | -1.00 | validate |
| 2024-10-24 20:00 | BÁN | -1.02 | validate |
| 2024-11-04 20:00 | BÁN | +1.51 | validate |
| 2025-01-15 04:00 | BÁN | -1.01 | validate |
| 2025-01-27 00:00 | BÁN | -1.01 | validate |
| 2025-03-24 04:00 | BÁN | -1.01 | validate |
| 2025-06-17 00:00 | BÁN | +1.76 | validate |
| 2025-09-18 08:00 | BÁN | -1.00 | validate |
| 2025-09-26 08:00 | BÁN | -1.01 | validate |
| 2025-10-06 16:00 | BÁN | -1.01 | validate |
| 2018-05-04 04:00 | MUA | -1.06 | train |
| 2018-07-03 04:00 | MUA | -1.07 | train |
| 2018-07-04 04:00 | MUA | -1.02 | train |
| 2018-07-20 12:00 | MUA | -1.02 | train |
| 2019-11-15 16:00 | MUA | -1.03 | train |
| 2020-06-08 04:00 | MUA | +1.84 | train |
| 2020-11-02 04:00 | MUA | +1.63 | train |
| 2020-12-02 00:00 | MUA | +2.00 | train |
| 2021-09-21 00:00 | MUA | -1.02 | train |
| 2022-05-13 04:00 | MUA | -1.01 | validate |
| 2022-07-26 00:00 | MUA | -1.03 | validate |
| 2022-09-05 08:00 | MUA | -1.02 | validate |
| 2023-03-10 12:00 | MUA | +1.64 | validate |
| 2023-08-22 00:00 | MUA | +2.40 | validate |
| 2023-10-10 20:00 | MUA | +0.89 | validate |
| 2024-11-18 12:00 | MUA | +1.56 | validate |

## Kết luận G131 (ba bản a / b / c)

**Không đạt.** Ở cả ba bản, không biến thể nào dương ở cả train và validate.

- **Bản a** (theo kế hoạch gốc) quá chặt: 0–7 lệnh mỗi kỳ, không bắt được ví dụ nào của người dùng.
- **Bản b và c** nới cho đúng mô tả:
  - nến đảo chiều được phép khi RSI vẫn còn ≥ 70;
  - nhấn chìm tính theo thân;
  - RSI chỉ cần nằm dưới RSI-MA;
  - test lại 38,2%;
  - chờ 12 nến;
  - (c) nến biên độ lớn không xét tỷ lệ thân.
- **Bản c bắt được ví dụ 29/01/2026**: vào bán 30/01 04:00, **+2,38R**. Ví dụ 03/2026 vẫn không vào lệnh.
- **Nhưng trên lịch sử thì không đứng được:**
  - Train 2018–2021 dương ở mọi biến thể: +0,29 đến +0,95R, tức có những đỉnh đẹp như ví dụ.
  - **Validate 2022–2025 âm ở cả 18 biến thể**: −0,12 đến −0,54R.
  - Riêng **lệnh bán đỉnh** giai đoạn 2022–2025: −0,05 đến −0,77R. Phần lớn lệnh dính −1R vì trong thị trường vàng tăng mạnh, "đỉnh cạn đà" thường chỉ là một nhịp nghỉ rồi đi tiếp.
- **Chiều mua** (đáy sau nhiều lần quá bán): quá ít lệnh (3–9 mỗi kỳ) và đổi dấu, chưa nói được gì.
- **Lưu ý về độ tin cậy:** luật đã được chỉnh hai lần sau khi nhìn ví dụ 2026 và kết quả bản trước. Kể cả vậy validate vẫn âm, nên kết luận "không đạt" là chắc chắn.
