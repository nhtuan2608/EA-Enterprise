# G73: Vào lệnh sớm cho S07 — kết quả

Kế hoạch: `plans/2026-10-10-g73-early-entry.md`. Số liệu: chi phí khắt khe G68, R/lệnh; "Gộp" = train + validate + test. DD p90 ở rủi ro 1,5%/lệnh, cửa sổ 1 năm.

## Khung M30, nến nhỏ M15

Nến nhỏ có từ 20/07/2021; nến nhỏ khớp nến chính (giá đóng): 100.0%. V1: 363 lệnh vào giữa nến, 264 lúc đóng nến, 35 tín hiệu giữa nến mất khi nến đóng, 209 lần bỏ vì SL > 4 ATR. V2: 7237 lần đặt lệnh chờ, 755 lần khớp, 11 lần chạm SL ngay nến khớp.

| Chiều | Cách | Train | Validate | Test | 07/2026– | Gộp n | Gộp R/lệnh | Tổng R | R/lệnh chi phí thường | DD p90 | SL (ATR) | Ngẫu nhiên (TB / p) | Sớm hơn B0 (phút, R giá vào, cặp) | Đạt |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Mua | B0 | 135 / +0.293 | 130 / +0.562 | 66 / +0.789 | 10 / -0.062 | 331 | +0.498 | +164.7 | +0.535 | 11% | 2.64 | +0.032 / 0.000 |  |  |
| Mua | V1 | 145 / +0.419 | 136 / +0.508 | 68 / +0.776 | 10 / -0.063 | 349 | +0.523 | +182.7 | +0.560 | 13% | 2.63 | +0.024 / 0.000 | 15 / +0.00 / 323 | không (4) |
| Mua | V2 | 176 / +0.231 | 169 / +0.374 | 97 / +0.553 | 14 / -0.179 | 442 | +0.356 | +157.4 | +0.394 | 19% | 2.58 | +0.031 / 0.000 | 30 / +0.15 / 242 | không (1, 2, 4) |
| Bán | B0 | 156 / -0.182 | 35 / -0.365 | 49 / +0.132 | 18 / +0.250 | 240 | -0.144 | -34.7 | -0.097 | 35% | 2.43 | -0.105 / 0.685 |  |  |
| Bán | V1 | 160 / -0.214 | 35 / -0.364 | 52 / +0.368 | 21 / +0.135 | 247 | -0.113 | -27.9 | -0.065 | 34% | 2.45 | -0.101 / 0.555 | 15 / +0.00 / 233 | không (3, 5) |
| Bán | V2 | 177 / -0.270 | 41 / -0.266 | 53 / +0.288 | 28 / -0.034 | 271 | -0.160 | -43.4 | -0.113 | 35% | 2.48 | -0.100 / 0.800 | 30 / +0.07 / 176 | không (1, 2, 3, 5) |

- Ví dụ B0: Bán 23/9: vào 23/09 13:00 VN, +2.95R; Bán 25–28/9: vào 28/09 05:30 VN, +7.97R; Mua 05/8: không vào; Mua 19/8: không vào
- Ví dụ V1: Bán 23/9: vào 23/09 12:45 VN, +1.85R; Bán 25–28/9: vào 28/09 05:15 VN, +7.97R; Mua 05/8: không vào; Mua 19/8: không vào
- Ví dụ V2: Bán 23/9: vào 23/09 12:30 VN, +1.38R; Bán 25–28/9: vào 28/09 05:00 VN, +3.63R; Mua 05/8: không vào; Mua 19/8: không vào

## Khung H1, nến nhỏ M15

Nến nhỏ có từ 20/07/2021; nến nhỏ khớp nến chính (giá đóng): 100.0%. V1: 298 lệnh vào giữa nến, 67 lúc đóng nến, 28 tín hiệu giữa nến mất khi nến đóng, 40 lần bỏ vì SL > 4 ATR. V2: 3189 lần đặt lệnh chờ, 498 lần khớp, 8 lần chạm SL ngay nến khớp.

| Chiều | Cách | Train | Validate | Test | 07/2026– | Gộp n | Gộp R/lệnh | Tổng R | R/lệnh chi phí thường | DD p90 | SL (ATR) | Ngẫu nhiên (TB / p) | Sớm hơn B0 (phút, R giá vào, cặp) | Đạt |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Mua | B0 | 80 / +0.183 | 70 / +0.552 | 34 / +1.259 | 3 / -0.808 | 184 | +0.522 | +96.0 | +0.551 | 21% | 2.27 | +0.103 / 0.000 |  |  |
| Mua | V1 | 86 / +0.312 | 79 / +0.407 | 35 / +1.503 | 3 / -0.768 | 200 | +0.558 | +111.6 | +0.588 | 20% | 2.14 | +0.099 / 0.005 | 30 / +0.01 / 183 | không (5) |
| Mua | V2 | 118 / +0.083 | 115 / +0.310 | 48 / +1.384 | 6 / -0.894 | 281 | +0.398 | +111.9 | +0.431 | 19% | 1.93 | +0.110 / 0.005 | 60 / +0.25 / 145 | không (1, 5) |
| Bán | B0 | 85 / -0.076 | 25 / +0.049 | 22 / -0.010 | 20 / -0.039 | 132 | -0.041 | -5.5 | -0.005 | 19% | 1.99 | -0.109 / 0.255 |  |  |
| Bán | V1 | 91 / -0.126 | 27 / -0.032 | 22 / +0.521 | 22 / -0.127 | 140 | -0.006 | -0.8 | +0.031 | 21% | 2.02 | -0.114 / 0.140 | 30 / +0.00 / 129 | không (3, 4, 5) |
| Bán | V2 | 119 / -0.154 | 38 / -0.454 | 32 / +0.212 | 22 / -0.138 | 189 | -0.152 | -28.8 | -0.114 | 30% | 1.88 | -0.106 / 0.690 | 60 / +0.14 / 103 | không (1, 2, 3, 4, 5) |

- Ví dụ B0: Bán 23/9: vào 23/09 13:00 VN, +0.88R; Bán 25–28/9: vào 28/09 06:00 VN, +7.98R; Mua 05/8: không vào; Mua 19/8: không vào
- Ví dụ V1: Bán 23/9: vào 23/09 12:45 VN, +1.12R; Bán 25–28/9: vào 28/09 05:15 VN, +7.98R; Mua 05/8: không vào; Mua 19/8: không vào
- Ví dụ V2: Bán 23/9: vào 23/09 08:15 VN, +1.09R; Bán 25–28/9: vào 28/09 05:00 VN, +2.13R; Mua 05/8: không vào; Mua 19/8: không vào

## Khung M15, nến nhỏ M5

Nến nhỏ có từ 14/05/2024; nến nhỏ khớp nến chính (giá đóng): 100.0%. V1: 359 lệnh vào giữa nến, 149 lúc đóng nến, 38 tín hiệu giữa nến mất khi nến đóng, 826 lần bỏ vì SL > 4 ATR. V2: 5464 lần đặt lệnh chờ, 491 lần khớp, 2 lần chạm SL ngay nến khớp.

| Chiều | Cách | Train | Validate | Test | 07/2026– | Gộp n | Gộp R/lệnh | Tổng R | R/lệnh chi phí thường | DD p90 | SL (ATR) | Ngẫu nhiên (TB / p) | Sớm hơn B0 (phút, R giá vào, cặp) | Đạt |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Mua | B0 | — | 163 / +0.344 | 135 / +0.307 | 14 / +0.005 | 298 | +0.327 | +97.5 | +0.359 | 15% | 3.04 | +0.034 / 0.000 |  |  |
| Mua | V1 | — | 171 / +0.373 | 150 / +0.256 | 14 / +0.089 | 321 | +0.319 | +102.3 | +0.350 | 20% | 3.08 | +0.041 / 0.000 | 5 / +0.00 / 294 | không (1, 3, 4) |
| Mua | V2 | — | 179 / +0.435 | 156 / +0.321 | 15 / -0.100 | 335 | +0.382 | +127.9 | +0.412 | 16% | 3.24 | +0.039 / 0.000 | 15 / +0.05 / 197 | không (3) |
| Bán | B0 | — | 45 / -0.443 | 76 / +0.100 | 39 / -0.050 | 121 | -0.102 | -12.3 | -0.073 | 28% | 2.97 | -0.055 / 0.680 |  |  |
| Bán | V1 | — | 50 / -0.479 | 84 / +0.061 | 39 / -0.049 | 134 | -0.141 | -18.9 | -0.112 | 32% | 2.92 | -0.056 / 0.850 | 5 / +0.00 / 121 | không (1, 2, 3, 4, 5) |
| Bán | V2 | — | 43 / -0.141 | 71 / +0.276 | 27 / +0.015 | 114 | +0.119 | +13.6 | +0.143 | 15% | 3.16 | -0.050 / 0.035 | 15 / +0.04 / 77 | không (3, 5) |

- Ví dụ B0: Bán 23/9: không vào; Bán 25–28/9: vào 28/09 05:15 VN, +7.96R; Mua 05/8: không vào; Mua 19/8: không vào
- Ví dụ V1: Bán 23/9: không vào; Bán 25–28/9: vào 28/09 05:05 VN, +7.95R; Mua 05/8: không vào; Mua 19/8: không vào
- Ví dụ V2: Bán 23/9: không vào; Bán 25–28/9: vào 28/09 05:00 VN, +4.70R; Mua 05/8: không vào; Mua 19/8: không vào

## Khung M30, nến nhỏ M5 (kiểm tra M5, chỉ báo cáo)

Nến nhỏ có từ 14/05/2024; nến nhỏ khớp nến chính (giá đóng): 100.0%. V1: 240 lệnh vào giữa nến, 39 lúc đóng nến, 30 tín hiệu giữa nến mất khi nến đóng, 163 lần bỏ vì SL > 4 ATR. V2: 3160 lần đặt lệnh chờ, 349 lần khớp, 1 lần chạm SL ngay nến khớp.

| Chiều | Cách | Train | Validate | Test | 07/2026– | Gộp n | Gộp R/lệnh | Tổng R | R/lệnh chi phí thường | DD p90 | SL (ATR) | Ngẫu nhiên (TB / p) | Sớm hơn B0 (phút, R giá vào, cặp) | Đạt |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Mua | B0 | — | 95 / +0.659 | 66 / +0.789 | 10 / -0.062 | 161 | +0.712 | +114.7 | +0.735 | 9% | 2.73 | — |  |  |
| Mua | V1 | — | 98 / +0.675 | 69 / +0.902 | 10 / -0.055 | 167 | +0.769 | +128.4 | +0.794 | 13% | 2.68 | — | 15 / +0.00 / 153 | — |
| Mua | V2 | — | 125 / +0.522 | 97 / +0.558 | 14 / -0.140 | 222 | +0.538 | +119.4 | +0.562 | 11% | 2.61 | — | 38 / +0.15 / 114 | — |
| Bán | B0 | — | 28 / -0.213 | 49 / +0.132 | 18 / +0.250 | 77 | +0.007 | +0.5 | +0.029 | 13% | 2.46 | — |  |  |
| Bán | V1 | — | 29 / -0.187 | 51 / +0.405 | 22 / +0.076 | 80 | +0.190 | +15.2 | +0.214 | 14% | 2.34 | — | 15 / +0.00 / 72 | — |
| Bán | V2 | — | 32 / -0.097 | 53 / +0.288 | 28 / -0.034 | 85 | +0.143 | +12.2 | +0.166 | 14% | 2.40 | — | 30 / +0.14 / 57 | — |

- Ví dụ B0: Bán 23/9: vào 23/09 13:00 VN, +2.95R; Bán 25–28/9: vào 28/09 05:30 VN, +7.97R; Mua 05/8: không vào; Mua 19/8: không vào
- Ví dụ V1: Bán 23/9: vào 23/09 12:45 VN, +1.85R; Bán 25–28/9: vào 28/09 05:05 VN, +7.97R; Mua 05/8: không vào; Mua 19/8: không vào
- Ví dụ V2: Bán 23/9: vào 23/09 12:40 VN, +1.38R; Bán 25–28/9: vào 28/09 05:00 VN, +3.63R; Mua 05/8: không vào; Mua 19/8: không vào

Cột Đạt: số trong ngoặc là tiêu chí không đạt (1 R/lệnh ≥ B0, 2 tổng R ≥ B0, 3 dương cả train/validate/test, 4 DD p90 ≤ B0 + 2 điểm %, 5 thắng ngẫu nhiên p < 0,05/12).


## Phân tích thêm (không đăng ký trước, chỉ để hiểu)

Lệnh V1 vào **giữa nến** (không tính lệnh vào lúc đóng nến, vì những lệnh đó trùng bản gốc), chi phí khắt khe, gộp train + validate + test:

| Khung / chiều | Lệnh giữa nến | Trong đó mất tín hiệu khi nến đóng | Cặp với B0 cùng đợt: V1 vs B0 | Vào sớm (trung vị) | Giá vào tốt hơn (trung vị) |
|---|---|---|---|---|---|
| M30 mua | 203 / +0.604 | 20 / +0.198 | 174 lệnh: +0.688 vs +0.614 | 15 phút | +0.02R |
| M30 bán | 143 / +0.063 | 13 / +0.022 | 123 lệnh: +0.008 vs −0.082 | 15 phút | +0.01R |
| H1 mua | 162 / +0.529 | 16 / +0.283 | 141 lệnh: +0.585 vs +0.455 | 30 phút | +0.05R |
| H1 bán | 117 / +0.029 | 11 / −0.694 | 102 lệnh: +0.130 vs +0.006 | 30 phút | +0.00R |

## Kết luận

- **Theo tiêu chí đăng ký trước, không cách nào đạt. Giữ bản gốc S07 (vào sau khi nến M30 đóng).**
- **V1 (kích hoạt khi nến nhỏ đóng) gần đạt nhất ở M30 mua.**
  - Đạt: R/lệnh +0,523 so với +0,498; tổng R +182,7 so với +164,7; dương cả train, validate, test; thắng vào lệnh ngẫu nhiên (p < 0,001).
  - Trượt duy nhất tiêu chí 4: DD p90 13% so với 11% của B0, vượt ngưỡng +2 điểm % khoảng 0,4 điểm.
  - Kiểm tra bằng M5 từ 05/2024 cho cùng chiều: +0,769 so với +0,712.
  - Lệnh vào giữa nến chỉ sớm 15 phút và giá vào gần như không tốt hơn (+0,02R). Lợi ích chủ yếu đến từ việc **bắt thêm các đợt bung** mà nến đóng không còn đủ điều kiện, cộng vài lệnh vào trước khi SL bị nới quá 4 ATR. Không phải nhờ giá vào đẹp hơn.
- **V2 (lệnh chờ Stop) kém hơn ở M30 và H1 mua.**
  - R/lệnh M30 mua +0,356 so với +0,498; DD p90 19% so với 11%.
  - Lệnh chờ khớp sớm 30–60 phút và giá vào tốt hơn 0,15–0,25R, nhưng gặp nhiều cú bứt phá giả (khớp rồi quay đầu), vì không chờ DI tách và ADX quay lên.
  - Chỉ ở M15 mua V2 tốt hơn (+0,382 so với +0,327), nhưng M15 chỉ có dữ liệu từ 2024 (không có train) nên không đủ để quyết định.
- **Bên bán:** không cách nào tạo được lợi thế ổn định (âm ở train). S07S giữ SHADOW như D6.
- **Bốn ví dụ:**
  - Hai lệnh bán được cả ba cách bắt. V1/V2 vào sớm hơn 15–30 phút nhưng ra kém hơn ở ví dụ 23/9.
  - Hai lệnh mua 05/8 và 19/8 không cách nào vào (như G69: các lần đó không qua bộ lọc H4 hoặc điều kiện nén).

**Đề xuất:** giữ quy tắc vào lệnh S07 như hiện tại (đang SHADOW theo D5). Nếu muốn theo dõi V1, ghi V1 thành tín hiệu SHADOW song song (không vào lệnh) cho M30 mua, rồi xem lại sau ≥ 30 lệnh ảo. Không đổi tiêu chí sau khi đã thấy kết quả.
