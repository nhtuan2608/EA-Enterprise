# FX02: sức mạnh tiền tệ khung D1 — kết quả

Kế hoạch: `plans/2026-10-11-fx02-currency-strength.md`. USD, EUR, GBP, JPY; 3 cặp chính thật + 3 cặp chéo tổng hợp. R = lời/lỗ sau chi phí ÷ (2 × biến động ngày 20 ngày). Ô: số lệnh / R mỗi lệnh. Chọn và chấm không swap.

## Kiểm tra cặp chéo tổng hợp (D1, 2024–2025)

| Cặp | Ngày | Tương quan lợi nhuận ngày | Lệch giá trung vị |
|---|---|---|---|
| EURJPY | 425 | 0.999 | 0.007% |
| GBPJPY | 425 | 1.000 | 0.006% |
| EURGBP | 425 | 0.998 | 0.013% |

## CSM — biến thể (L ngày, giữ H ngày)

| L / H | Train 2010–16 | Validate 2017–20 | Đạt? | Test 2021–25 |
|---|---|---|---|---|
| 20 / 5 | 314 / -0.105 | 207 / -0.278 |  | 247 / -0.197 |
| 20 / 20 | 79 / +0.095 | 52 / -0.807 |  | 61 / +0.061 |
| 60 / 5 | 314 / +0.164 | 207 / -0.057 |  | 247 / +0.069 |
| 60 / 20 | 79 / +0.669 | 52 / -0.402 |  | 61 / +0.539 |
| 120 / 5 | 314 / +0.074 | 207 / -0.065 |  | 247 / -0.031 |
| 120 / 20 | 79 / +0.658 | 52 / -0.259 |  | 61 / +0.186 |

**CSM: không biến thể nào đạt → dừng.**

## CSR — biến thể (L ngày, giữ H ngày)

| L / H | Train 2010–16 | Validate 2017–20 | Đạt? | Test 2021–25 |
|---|---|---|---|---|
| 3 / 1 | 1568 / -0.069 | 1036 / -0.030 |  | 1238 / -0.013 |
| 3 / 3 | 523 / -0.065 | 345 / -0.077 |  | 412 / -0.072 |
| 5 / 1 | 1568 / -0.055 | 1036 / -0.012 |  | 1238 / -0.030 |
| 5 / 3 | 523 / -0.087 | 345 / +0.049 |  | 412 / -0.074 |

**CSR: không biến thể nào đạt → dừng.**

## TSM — biến thể (L ngày, giữ H ngày)

| L / H | Train 2010–16 | Validate 2017–20 | Đạt? | Test 2021–25 |
|---|---|---|---|---|
| 20 / 5 | 1883 / -0.063 | 1242 / -0.127 |  | 1482 / -0.092 |
| 20 / 20 | 474 / +0.002 | 312 / -0.414 |  | 366 / -0.055 |
| 60 / 5 | 1884 / +0.067 | 1242 / -0.040 |  | 1482 / -0.016 |
| 60 / 20 | 474 / +0.332 | 312 / -0.276 |  | 366 / +0.187 |
| 120 / 5 | 1884 / +0.029 | 1242 / -0.068 |  | 1482 / -0.022 |
| 120 / 20 | 474 / +0.413 | 312 / -0.130 |  | 366 / +0.082 |

**TSM: không biến thể nào đạt → dừng.**

## Kiểm tra cuối (2021–10/2025)

| Họ | Biến thể + lọc | Lệnh | R/lệnh | Cận dưới 90% | Cận dưới 96,7% | Sau trừ 0,10R | Có swap (mức hiện tại) | %/năm @0,5% | DD @0,5% | Đạt? |
|---|---|---|---|---|---|---|---|---|---|---|

Không họ nào qua bước chọn, nên bảng trên trống.

## Kết luận

**FX02 không đạt.**

- **Cặp chéo tổng hợp khớp cặp thật** (tương quan ≥ 0,998), nên dùng được cho nghiên cứu.
- **Động lượng chậm (L 60–120 ngày, giữ 20 ngày), cả CSM lẫn TSM**, có dạng quen thuộc của xu hướng FX: dương ở 2010–2016 và 2021–2025 (CSM L60/H20: +0,67 / −0,40 / +0,54), nhưng **âm toàn bộ 2017–2020**, giai đoạn FX đi ngang, biến động thấp.
  - Theo luật đã đăng ký thì không được chọn.
  - Kỳ test đã bị nhìn thấy, nên không thể lấy kết quả 2021–2025 làm bằng chứng.
- **Lợi thế này phụ thuộc chế độ thị trường** và rất ít lệnh: khoảng 12 lệnh/năm, mỗi lệnh biến động ±2R. Nó không ổn định đủ để làm chiến lược đứng riêng.
- **Đảo chiều ngắn (CSR)** âm nhẹ ở mọi biến thể (−0,01 đến −0,09).
