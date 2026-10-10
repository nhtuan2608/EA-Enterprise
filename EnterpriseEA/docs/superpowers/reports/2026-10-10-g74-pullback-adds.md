# G74: Bồi lệnh S07 khi giá hồi về EMA / vùng — kết quả

Kế hoạch: `plans/2026-10-10-g74-pullback-adds.md`. XAUUSD, dữ liệu MT5, chi phí khắt khe G68 cho mọi lệnh, rủi ro 1,5% mỗi lệnh, tối đa 2 lệnh bồi và 3 lệnh mở. Ô kỳ: số lệnh gốc / tổng R mỗi lệnh gốc (gồm bồi) / số lệnh bồi.

## Sổ Mua (lệnh gốc M30)

### Phần 1 — giá hồi về đâu trong lúc lệnh gốc chạy (mô tả)

Lệnh gốc 2018–06/2026: 528.

| Vùng chạm | % lệnh gốc có chạm | Trung vị: chạm sau (nến) | Lệnh gốc đã lời lúc chạm (R, trung vị) | Giá đi tiếp sau chạm (ATR, trung vị) | R lệnh gốc khi có chạm | R lệnh gốc khi không chạm |
|---|---|---|---|---|---|---|
| EMA21 | 100% | 5 | +0.32 | 2.4 | +0.36 | — (2 lệnh) |
| EMA55 | 97% | 10 | +0.46 | 2.2 | +0.31 | +2.53 (15) |
| EMA100 | 73% | 10 | +0.45 | 2.0 | +0.08 | +1.15 (143) |
| Vùng | 100% | 1 | +0.14 | 2.5 | +0.37 | — (0 lệnh) |

### Phần 2 — các cách bồi

| Bản | 09/2018–07/2021 | Train 2021–2023 | Validate 2024–06/2025 | Test 07/2025–06/2026 | 07/2026–nay | Lệnh bồi: R/lệnh train / validate / test | DD (R) | %/năm | DD p90 1 năm | Chạm 20% | Chạm 30% | Ngẫu nhiên (TB / p) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A0 không bồi | 196 / +0.16 / 0 | 136 / +0.29 / 0 | 130 / +0.56 / 0 | 66 / +0.79 / 0 | 10 / -0.06 / 0 | +0.00 / +0.00 / +0.00 | 16.2 | +41% | 16% | 1% | 0% | — |
| A1 hiện tại (S07 khung khác) | 196 / +0.24 / 121 | 136 / +0.25 / 122 | 130 / +1.14 / 101 | 66 / +1.31 / 61 | 10 / +0.33 / 8 | -0.04 / +0.74 / +0.56 | 35.5 | +75% | 30% | 30% | 13% | -0.09 / 0.000 |
| P1C0 hồi EMA21 (khung gốc) | 196 / +0.26 / 165 | 136 / +0.38 / 113 | 130 / +1.15 / 108 | 66 / +1.50 / 62 | 10 / +0.59 / 8 | +0.11 / +0.71 / +0.76 | 55.7 | +83% | 46% | 71% | 28% | -0.31 / 0.000 |
| P1C1 hồi EMA21 (khung gốc) | 196 / +0.33 / 106 | 136 / +0.21 / 86 | 130 / +0.81 / 84 | 66 / +1.41 / 35 | 10 / +0.66 / 7 | -0.12 / +0.38 / +1.18 | 42.0 | +66% | 37% | 58% | 22% | -0.30 / 0.000 |
| P2C0 hồi EMA55 (khung gốc) | 196 / +0.14 / 80 | 136 / +0.30 / 71 | 130 / +0.81 / 47 | 66 / +1.40 / 39 | 10 / -0.19 / 2 | +0.03 / +0.70 / +1.04 | 35.0 | +59% | 33% | 48% | 13% | -0.30 / 0.000 |
| P2C1 hồi EMA55 (khung gốc) | 196 / +0.18 / 22 | 136 / +0.27 / 36 | 130 / +0.63 / 16 | 66 / +0.82 / 10 | 10 / -0.16 / 1 | -0.06 / +0.53 / +0.23 | 20.7 | +44% | 20% | 10% | 0% | -0.34 / 0.020 |
| P3C0 hồi mép vùng nén | 196 / +0.24 / 174 | 136 / +0.15 / 129 | 130 / +1.29 / 124 | 66 / +1.54 / 55 | 10 / +1.31 / 8 | -0.14 / +0.77 / +0.90 | 57.7 | +78% | 46% | 74% | 37% | -0.32 / 0.000 |
| P3C1 hồi mép vùng nén | 196 / +0.27 / 106 | 136 / +0.14 / 77 | 130 / +0.85 / 75 | 66 / +1.47 / 34 | 10 / +0.59 / 6 | -0.27 / +0.49 / +1.32 | 38.7 | +62% | 34% | 56% | 16% | -0.29 / 0.000 |
| P4C0 hồi EMA21 trên M15 | 196 / +0.16 / 0 | 136 / +0.06 / 137 | 130 / +1.35 / 133 | 66 / +1.39 / 75 | 10 / -0.19 / 10 | -0.23 / +0.77 / +0.53 | 25.5 | +70% | 28% | 64% | 3% | -0.31 / 0.000 |
| P4C1 hồi EMA21 trên M15 | 196 / +0.16 / 0 | 136 / +0.26 / 113 | 130 / +1.05 / 115 | 66 / +1.42 / 51 | 10 / +0.32 / 9 | -0.04 / +0.55 / +0.82 | 18.1 | +68% | 22% | 11% | 0% | -0.31 / 0.000 |

Ứng viên (tổng R/lệnh gốc > A1 ở cả train và validate): P1C0 hồi EMA21 (khung gốc).
Chọn: **P1C0 hồi EMA21 (khung gốc)**. test ≥ A1: đạt; pre ≥ A1: đạt; lệnh bồi dương train/validate/test: đạt; DD p90 ≤ A1 + 2 điểm: KHÔNG; thắng ngẫu nhiên: đạt.
**Kết luận theo luật: giữ A1 (bồi bằng tín hiệu S07 khung khác).**

## Sổ Bán (lệnh gốc H1)

### Phần 1 — giá hồi về đâu trong lúc lệnh gốc chạy (mô tả)

Lệnh gốc 2018–06/2026: 210.

| Vùng chạm | % lệnh gốc có chạm | Trung vị: chạm sau (nến) | Lệnh gốc đã lời lúc chạm (R, trung vị) | Giá đi tiếp sau chạm (ATR, trung vị) | R lệnh gốc khi có chạm | R lệnh gốc khi không chạm |
|---|---|---|---|---|---|---|
| EMA21 | 99% | 3 | +0.45 | 2.0 | -0.09 | — (2 lệnh) |
| EMA55 | 93% | 6 | +0.51 | 1.8 | -0.17 | +1.50 (14) |
| EMA100 | 68% | 5 | +0.51 | 1.7 | -0.40 | +0.67 (68) |
| Vùng | 100% | 1 | +0.21 | 2.0 | -0.06 | — (0 lệnh) |

### Phần 2 — các cách bồi

| Bản | 09/2018–07/2021 | Train 2021–2023 | Validate 2024–06/2025 | Test 07/2025–06/2026 | 07/2026–nay | Lệnh bồi: R/lệnh train / validate / test | DD (R) | %/năm | DD p90 1 năm | Chạm 20% | Chạm 30% | Ngẫu nhiên (TB / p) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A0 không bồi | 76 / -0.16 / 0 | 87 / -0.07 / 0 | 25 / +0.05 / 0 | 22 / +0.22 / 0 | 20 / -0.31 / 0 | +0.00 / +0.00 / +0.00 | 29.3 | -3% | 20% | 10% | 0% | — |
| A1 hiện tại (S07 khung khác) | 76 / -0.37 / 56 | 87 / +0.03 / 81 | 25 / -0.39 / 22 | 22 / +0.50 / 20 | 20 / -0.65 / 20 | +0.11 / -0.50 / +0.31 | 52.9 | -6% | 34% | 47% | 23% | — |
| P1C0 hồi EMA21 (khung gốc) | 76 / -0.30 / 48 | 87 / -0.33 / 66 | 25 / -0.27 / 10 | 22 / +0.08 / 22 | 20 / -1.12 / 18 | -0.35 / -0.81 / -0.14 | 69.5 | -12% | 33% | 54% | 13% | — |
| P1C1 hồi EMA21 (khung gốc) | 76 / -0.40 / 32 | 87 / -0.17 / 42 | 25 / -0.10 / 5 | 22 / -0.02 / 21 | 20 / -0.87 / 12 | -0.21 / -0.77 / -0.25 | 60.5 | -10% | 28% | 45% | 9% | — |
| P2C0 hồi EMA55 (khung gốc) | 76 / -0.17 / 20 | 87 / -0.22 / 29 | 25 / -0.13 / 5 | 22 / +0.19 / 7 | 20 / -0.46 / 3 | -0.45 / -0.94 / -0.10 | 44.2 | -7% | 26% | 36% | 1% | — |
| P2C1 hồi EMA55 (khung gốc) | 76 / -0.19 / 13 | 87 / -0.12 / 14 | 25 / +0.02 / 1 | 22 / +0.21 / 7 | 20 / -0.36 / 1 | -0.32 / -0.94 / -0.03 | 34.5 | -5% | 22% | 20% | 0% | — |
| P3C0 hồi mép vùng nén | 76 / -0.32 / 58 | 87 / -0.42 / 92 | 25 / +0.19 / 19 | 22 / +1.24 / 27 | 20 / -0.89 / 19 | -0.34 / +0.18 / +0.83 | 79.6 | -7% | 39% | 86% | 38% | — |
| P3C1 hồi mép vùng nén | 76 / -0.48 / 35 | 87 / -0.17 / 47 | 25 / +0.44 / 9 | 22 / +0.73 / 18 | 20 / -0.74 / 11 | -0.19 / +1.07 / +0.62 | 63.8 | -6% | 31% | 45% | 11% | — |
| P4C0 hồi EMA21 trên M15 | 76 / -0.16 / 0 | 87 / -0.26 / 97 | 25 / +0.12 / 19 | 22 / +0.37 / 27 | 20 / -0.84 / 23 | -0.18 / +0.09 / +0.12 | 63.1 | -6% | 37% | 64% | 29% | — |
| P4C1 hồi EMA21 trên M15 | 76 / -0.16 / 0 | 87 / -0.24 / 85 | 25 / -0.10 / 14 | 22 / +0.29 / 27 | 20 / -0.80 / 22 | -0.18 / -0.27 / +0.05 | 63.0 | -7% | 33% | 53% | 20% | — |

Sổ bán chỉ để mô tả (bên bán đang SHADOW, chưa có lợi thế đã kiểm chứng).

## Kết luận

**Theo tiêu chí đăng ký trước: giữ cách bồi hiện tại (A1, tín hiệu S07 ở M15/H1/H4).**

- **P1C0 (hồi EMA21 khung M30) là ứng viên duy nhất** (tổng R/lệnh gốc cao hơn A1 ở cả train và validate).
  - Đạt: test, pre, lệnh bồi dương ở cả 3 kỳ, thắng ngẫu nhiên.
  - **Trượt DD:** DD p90 1 năm 46% so với 30% của A1.
  - Lý do: nó bồi rất thường xuyên ở mép EMA21 (giá gần như lần nào cũng chạm lại, xem phần 1). Lệnh bồi dồn vào những đợt giá đi ngang rồi thua cùng lệnh gốc.
- **P4C1 (hồi EMA21 trên M15, có DMI xác nhận)** cho rủi ro thấp nhất trong các cách có bồi, nhưng **không phải ứng viên** vì validate thấp hơn A1 (+1,05 so với +1,14). Đây là quan sát, không dùng để chọn.
  - DD p90 22%, chạm 20% chỉ 11%, chạm 30% 0%.
  - Lãi gần A1: +68%/năm so với +75%.
  - Nếu muốn giảm rủi ro của sổ bồi, đây là hướng nên kiểm lại bằng một kế hoạch riêng.
- **Thêm xác nhận DMI (C1) giảm DD ở mọi cách nhưng cũng giảm lãi.** Không có cách nào vừa lãi hơn vừa ít rủi ro hơn A1 ở cả train lẫn validate.
- **Phần 1 (vùng):**
  - Gần như mọi lệnh gốc đều quay lại chạm EMA21 (trung vị sau 5 nến M30, lúc đó lệnh đã lời +0,32R); 97% chạm EMA55.
  - **Lệnh hồi sâu về EMA100 yếu hơn hẳn:** R lệnh gốc +0,08 khi có chạm, so với +1,15 khi không chạm.
  - Mép vùng nén luôn bị chạm ngay nến đầu (giá vào sát vùng), nên không phân biệt được gì.
- **Bên bán:** không cách bồi nào giúp được, sổ bán vẫn âm.

**Lưu ý rủi ro (phát hiện phụ):** với chi phí khắt khe, A1 (đang thiết kế cho EA) có DD p90 1 năm 30% và 13% số cửa sổ 1 năm chạm 30% — đúng bằng mức lỗ tổng 30%. G70 (chi phí thường) báo 24% và 6%. Nên cân nhắc trước khi bật S07A LIVE.
