# G108 bước 3: plan học cuốn chiếu (kNN, LightGBM) và đối chứng

Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g108-m30-path-plans.md; bước 1–2: reports/2026-10-13-g108-patterns.md. Mỗi tháng từ 12/2024, mô hình học từ các plan đã **thoát lệnh trước ngày đầu tháng** (có assert trong code) rồi dự báo plan của tháng đó. **Kỳ test 2026 vẫn niêm phong.** Script: research/long/g108_features.py, g108_models.py.

Plan đã gộp (một plan một lần): 23583; có dự báo ngoài mẫu: 15898. p = xác suất chạm mục tiêu trước mức sai; EV = p × RR − (1 − p). Nhãn: mục tiêu cố định 2R.

## Mô hình có xếp hạng được plan không (AUC, ngoài mẫu)

| Mô hình | Kỳ | MUA | BÁN |
|---|---|---|---|
| lgbm | OOS 12/2024–03/2025 (cuối train) | 0.562 | 0.524 |
| lgbm | Validate 04–12/2025 | 0.538 | 0.521 |
| knn | OOS 12/2024–03/2025 (cuối train) | 0.525 | 0.504 |
| knn | Validate 04–12/2025 | 0.525 | 0.512 |
| C2 time | OOS 12/2024–03/2025 (cuối train) | 0.558 | 0.517 |
| C2 time | Validate 04–12/2025 | 0.545 | 0.534 |
| C3 no path | OOS 12/2024–03/2025 (cuối train) | 0.568 | 0.536 |
| C3 no path | Validate 04–12/2025 | 0.537 | 0.523 |
| C4 shuffled | OOS 12/2024–03/2025 (cuối train) | 0.560 | 0.522 |
| C4 shuffled | Validate 04–12/2025 | 0.536 | 0.516 |

AUC 0,5 = không hơn đoán mò. Lưu ý: RR là một đặc trưng, nên mô hình nào cũng học được "mục tiêu gần thì dễ chạm"; điều cần xem là lợi nhuận (bảng dưới), không phải AUC.

## Validate: R thực tế theo nhóm 10% EV dự báo (lgbm)

| Chiều | Nhóm EV (thấp → cao) | Plan | p dự báo | Thắng thực tế | R/plan |
|---|---|---|---|---|---|
| MUA | 1 | 517 | 0.14 | 21% | -0.335 |
| MUA | 2 | 517 | 0.20 | 22% | -0.322 |
| MUA | 3 | 516 | 0.23 | 28% | -0.163 |
| MUA | 4 | 517 | 0.25 | 27% | -0.170 |
| MUA | 5 | 517 | 0.27 | 28% | -0.159 |
| MUA | 6 | 516 | 0.28 | 28% | -0.143 |
| MUA | 7 | 517 | 0.30 | 30% | -0.085 |
| MUA | 8 | 516 | 0.32 | 29% | -0.130 |
| MUA | 9 | 517 | 0.35 | 28% | -0.144 |
| MUA | 10 | 517 | 0.42 | 32% | -0.052 |
| BÁN | 1 | 463 | 0.15 | 21% | -0.352 |
| BÁN | 2 | 462 | 0.20 | 22% | -0.343 |
| BÁN | 3 | 462 | 0.22 | 24% | -0.268 |
| BÁN | 4 | 462 | 0.23 | 24% | -0.266 |
| BÁN | 5 | 463 | 0.25 | 29% | -0.134 |
| BÁN | 6 | 462 | 0.26 | 29% | -0.136 |
| BÁN | 7 | 462 | 0.27 | 26% | -0.221 |
| BÁN | 8 | 462 | 0.29 | 27% | -0.182 |
| BÁN | 9 | 462 | 0.31 | 24% | -0.260 |
| BÁN | 10 | 463 | 0.35 | 26% | -0.221 |

## Lệnh không chồng (mỗi chiều một lệnh mỗi lúc)

| Mô hình | Quy tắc | Kỳ | Chiều | Lệnh | Lệnh/tháng | Thắng | R/lệnh | Cận dưới 90% | Tổng / DD |
|---|---|---|---|---|---|---|---|---|---|
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | MUA | 755 | 189 | 29% | -0.151 | -0.208 | -114.1R / DD 118.1R |
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | BÁN | 971 | 243 | 28% | -0.180 | -0.237 | -174.9R / DD 190.5R |
| (vào mọi plan) | — | Validate 04–12/2025 | MUA | 1305 | 186 | 27% | -0.183 | -0.231 | -238.3R / DD 261.5R |
| (vào mọi plan) | — | Validate 04–12/2025 | BÁN | 1627 | 232 | 26% | -0.219 | -0.261 | -356.9R / DD 361.2R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 385 | 96 | 30% | -0.094 | -0.177 | -36.2R / DD 44.2R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 232 | 58 | 25% | -0.269 | -0.379 | -62.3R / DD 65.0R |
| lgbm | EV > 0 | Validate 04–12/2025 | MUA | 498 | 71 | 29% | -0.121 | -0.193 | -60.4R / DD 63.5R |
| lgbm | EV > 0 | Validate 04–12/2025 | BÁN | 219 | 31 | 25% | -0.262 | -0.374 | -57.3R / DD 58.3R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 136 | 34 | 27% | -0.194 | -0.323 | -26.4R / DD 31.0R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 51 | 13 | 24% | -0.320 | -0.525 | -16.3R / DD 25.0R |
| lgbm | top 10% | Validate 04–12/2025 | MUA | 278 | 40 | 31% | -0.069 | -0.164 | -19.1R / DD 37.1R |
| lgbm | top 10% | Validate 04–12/2025 | BÁN | 67 | 10 | 33% | -0.041 | -0.272 | -2.8R / DD 15.8R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 178 | 44 | 27% | -0.209 | -0.322 | -37.3R / DD 39.3R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 58 | 14 | 38% | +0.138 | -0.042 | +8.0R / DD 6.0R |
| knn | EV > 0 | Validate 04–12/2025 | MUA | 251 | 36 | 31% | -0.068 | -0.192 | -17.0R / DD 37.9R |
| knn | EV > 0 | Validate 04–12/2025 | BÁN | 61 | 9 | 23% | -0.311 | -0.508 | -19.0R / DD 21.0R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 181 | 45 | 30% | -0.107 | -0.219 | -19.3R / DD 23.3R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 51 | 13 | 35% | +0.059 | -0.121 | +3.0R / DD 11.0R |
| knn | top 10% | Validate 04–12/2025 | MUA | 368 | 53 | 31% | -0.075 | -0.172 | -27.4R / DD 49.4R |
| knn | top 10% | Validate 04–12/2025 | BÁN | 110 | 16 | 21% | -0.373 | -0.496 | -41.0R / DD 45.0R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 276 | 69 | 31% | -0.080 | -0.187 | -22.2R / DD 38.4R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 125 | 31 | 24% | -0.308 | -0.431 | -38.5R / DD 37.5R |
| C2 time | EV > 0 | Validate 04–12/2025 | MUA | 399 | 57 | 31% | -0.076 | -0.162 | -30.5R / DD 66.5R |
| C2 time | EV > 0 | Validate 04–12/2025 | BÁN | 50 | 7 | 24% | -0.280 | -0.509 | -14.0R / DD 22.0R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 148 | 37 | 30% | -0.116 | -0.258 | -17.2R / DD 22.4R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 46 | 12 | 26% | -0.294 | -0.505 | -13.5R / DD 13.8R |
| C2 time | top 10% | Validate 04–12/2025 | MUA | 359 | 51 | 31% | -0.074 | -0.164 | -26.5R / DD 59.5R |
| C2 time | top 10% | Validate 04–12/2025 | BÁN | 34 | 5 | 24% | -0.294 | -0.559 | -10.0R / DD 15.0R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 394 | 98 | 28% | -0.161 | -0.248 | -63.3R / DD 68.3R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 249 | 62 | 25% | -0.241 | -0.358 | -60.0R / DD 63.0R |
| C3 no path | EV > 0 | Validate 04–12/2025 | MUA | 533 | 76 | 31% | -0.064 | -0.137 | -34.1R / DD 65.0R |
| C3 no path | EV > 0 | Validate 04–12/2025 | BÁN | 207 | 30 | 21% | -0.385 | -0.488 | -79.8R / DD 78.8R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 127 | 32 | 27% | -0.208 | -0.348 | -26.4R / DD 30.4R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 47 | 12 | 23% | -0.298 | -0.556 | -14.0R / DD 21.0R |
| C3 no path | top 10% | Validate 04–12/2025 | MUA | 263 | 38 | 32% | -0.042 | -0.134 | -11.0R / DD 43.0R |
| C3 no path | top 10% | Validate 04–12/2025 | BÁN | 61 | 9 | 26% | -0.242 | -0.408 | -14.8R / DD 18.8R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 440 | 110 | 29% | -0.134 | -0.214 | -59.0R / DD 65.0R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 279 | 70 | 28% | -0.161 | -0.248 | -45.0R / DD 52.0R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | MUA | 542 | 77 | 32% | -0.037 | -0.118 | -20.0R / DD 47.0R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | BÁN | 241 | 34 | 24% | -0.297 | -0.403 | -71.6R / DD 70.6R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 128 | 32 | 27% | -0.203 | -0.349 | -26.0R / DD 31.0R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 63 | 16 | 33% | +0.000 | -0.231 | +0.0R / DD 17.0R |
| C4 shuffled | top 10% | Validate 04–12/2025 | MUA | 268 | 38 | 35% | +0.052 | -0.054 | +14.0R / DD 24.0R |
| C4 shuffled | top 10% | Validate 04–12/2025 | BÁN | 79 | 11 | 24% | -0.278 | -0.471 | -22.0R / DD 24.0R |

## Đối chứng C1: chọn ngẫu nhiên (theo plan, không chồng lệnh)

- MUA: lgbm top 10% trên validate R/plan -0.069; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.196, 95% ≤ -0.100; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.005**
- BÁN: lgbm top 10% trên validate R/plan -0.086; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.239, 95% ≤ +0.000; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.120**

## Học tiếp theo thời gian (lgbm, từng tháng ngoài mẫu)

| Tháng | Plan học | Plan dự báo | AUC | R/plan top 10% EV trong tháng |
|---|---|---|---|---|
| 2024-12 | 7676 | 1486 | 0.561 | +0.206 |
| 2025-01 | 9164 | 1654 | 0.554 | -0.177 |
| 2025-02 | 10818 | 1413 | 0.543 | -0.324 |
| 2025-03 | 12231 | 1555 | 0.530 | -0.355 |
| 2025-04 | 13786 | 1581 | 0.509 | -0.151 |
| 2025-05 | 15367 | 1646 | 0.565 | -0.091 |
| 2025-06 | 17016 | 1543 | 0.559 | +0.219 |
| 2025-07 | 18557 | 1647 | 0.522 | -0.218 |
| 2025-08 | 20207 | 1463 | 0.564 | -0.216 |
| 2025-09 | 21671 | 1545 | 0.500 | -0.336 |
| 2025-10 | 23209 | 365 | 0.539 | -0.103 |

## Kiểm tra cuốn chiếu

| Tháng dự báo | Plan học | Plan dự báo | Lệnh học thoát muộn nhất |
|---|---|---|---|
| 2024-12 | 7676 | 1486 | 2024-11-29 21:45:00 |
| 2025-01 | 9164 | 1654 | 2024-12-31 23:50:00 |
| 2025-02 | 10818 | 1413 | 2025-01-31 23:15:00 |
| 2025-03 | 12231 | 1555 | 2025-02-28 23:00:00 |
| 2025-04 | 13786 | 1581 | 2025-03-31 22:45:00 |
| 2025-05 | 15367 | 1646 | 2025-04-30 23:20:00 |
| 2025-06 | 17016 | 1543 | 2025-05-30 23:30:00 |
| 2025-07 | 18557 | 1647 | 2025-06-30 22:25:00 |
| 2025-08 | 20207 | 1463 | 2025-07-31 23:50:00 |
| 2025-09 | 21671 | 1545 | 2025-08-29 23:55:00 |
| 2025-10 | 23209 | 365 | 2025-09-30 23:05:00 |
