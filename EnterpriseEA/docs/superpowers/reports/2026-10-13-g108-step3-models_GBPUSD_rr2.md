# G108 bước 3: plan học cuốn chiếu (kNN, LightGBM) và đối chứng

Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g108-m30-path-plans.md; bước 1–2: reports/2026-10-13-g108-patterns.md. Mỗi tháng từ 12/2024, mô hình học từ các plan đã **thoát lệnh trước ngày đầu tháng** (có assert trong code) rồi dự báo plan của tháng đó. **Kỳ test 2026 vẫn niêm phong.** Script: research/long/g108_features.py, g108_models.py.

Plan đã gộp (một plan một lần): 23951; có dự báo ngoài mẫu: 16159. p = xác suất chạm mục tiêu trước mức sai; EV = p × RR − (1 − p). Nhãn: mục tiêu cố định 2R.

## Mô hình có xếp hạng được plan không (AUC, ngoài mẫu)

| Mô hình | Kỳ | MUA | BÁN |
|---|---|---|---|
| lgbm | OOS 12/2024–03/2025 (cuối train) | 0.562 | 0.525 |
| lgbm | Validate 04–12/2025 | 0.530 | 0.530 |
| knn | OOS 12/2024–03/2025 (cuối train) | 0.534 | 0.505 |
| knn | Validate 04–12/2025 | 0.521 | 0.525 |
| C2 time | OOS 12/2024–03/2025 (cuối train) | 0.535 | 0.510 |
| C2 time | Validate 04–12/2025 | 0.532 | 0.534 |
| C3 no path | OOS 12/2024–03/2025 (cuối train) | 0.564 | 0.532 |
| C3 no path | Validate 04–12/2025 | 0.532 | 0.534 |
| C4 shuffled | OOS 12/2024–03/2025 (cuối train) | 0.562 | 0.530 |
| C4 shuffled | Validate 04–12/2025 | 0.517 | 0.520 |

AUC 0,5 = không hơn đoán mò. Lưu ý: RR là một đặc trưng, nên mô hình nào cũng học được "mục tiêu gần thì dễ chạm"; điều cần xem là lợi nhuận (bảng dưới), không phải AUC.

## Validate: R thực tế theo nhóm 10% EV dự báo (lgbm)

| Chiều | Nhóm EV (thấp → cao) | Plan | p dự báo | Thắng thực tế | R/plan |
|---|---|---|---|---|---|
| MUA | 1 | 526 | 0.16 | 23% | -0.283 |
| MUA | 2 | 525 | 0.20 | 24% | -0.274 |
| MUA | 3 | 525 | 0.23 | 26% | -0.215 |
| MUA | 4 | 525 | 0.25 | 27% | -0.177 |
| MUA | 5 | 525 | 0.27 | 31% | -0.054 |
| MUA | 6 | 525 | 0.28 | 29% | -0.138 |
| MUA | 7 | 525 | 0.30 | 29% | -0.132 |
| MUA | 8 | 525 | 0.32 | 26% | -0.217 |
| MUA | 9 | 525 | 0.35 | 30% | -0.098 |
| MUA | 10 | 525 | 0.42 | 32% | -0.051 |
| BÁN | 1 | 469 | 0.15 | 21% | -0.366 |
| BÁN | 2 | 469 | 0.19 | 21% | -0.358 |
| BÁN | 3 | 469 | 0.21 | 26% | -0.209 |
| BÁN | 4 | 468 | 0.23 | 28% | -0.167 |
| BÁN | 5 | 469 | 0.24 | 25% | -0.235 |
| BÁN | 6 | 469 | 0.25 | 22% | -0.341 |
| BÁN | 7 | 468 | 0.27 | 27% | -0.183 |
| BÁN | 8 | 469 | 0.28 | 27% | -0.196 |
| BÁN | 9 | 469 | 0.30 | 30% | -0.107 |
| BÁN | 10 | 469 | 0.34 | 27% | -0.185 |

## Lệnh không chồng (mỗi chiều một lệnh mỗi lúc)

| Mô hình | Quy tắc | Kỳ | Chiều | Lệnh | Lệnh/tháng | Thắng | R/lệnh | Cận dưới 90% | Tổng / DD |
|---|---|---|---|---|---|---|---|---|---|
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | MUA | 759 | 190 | 29% | -0.156 | -0.212 | -118.1R / DD 121.1R |
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | BÁN | 970 | 242 | 28% | -0.176 | -0.232 | -170.9R / DD 188.5R |
| (vào mọi plan) | — | Validate 04–12/2025 | MUA | 1290 | 184 | 28% | -0.182 | -0.225 | -234.1R / DD 255.4R |
| (vào mọi plan) | — | Validate 04–12/2025 | BÁN | 1627 | 232 | 26% | -0.218 | -0.258 | -353.9R / DD 358.2R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 363 | 91 | 29% | -0.138 | -0.227 | -50.0R / DD 63.0R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 257 | 64 | 27% | -0.188 | -0.307 | -48.3R / DD 55.0R |
| lgbm | EV > 0 | Validate 04–12/2025 | MUA | 506 | 72 | 29% | -0.121 | -0.190 | -61.2R / DD 74.2R |
| lgbm | EV > 0 | Validate 04–12/2025 | BÁN | 183 | 26 | 23% | -0.302 | -0.426 | -55.3R / DD 56.3R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 124 | 31 | 30% | -0.121 | -0.265 | -15.0R / DD 15.0R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 67 | 17 | 27% | -0.214 | -0.458 | -14.3R / DD 31.0R |
| lgbm | top 10% | Validate 04–12/2025 | MUA | 306 | 44 | 30% | -0.084 | -0.182 | -25.6R / DD 38.6R |
| lgbm | top 10% | Validate 04–12/2025 | BÁN | 53 | 8 | 25% | -0.264 | -0.467 | -14.0R / DD 13.0R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 200 | 50 | 30% | -0.121 | -0.233 | -24.1R / DD 24.1R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 43 | 11 | 33% | -0.023 | -0.250 | -1.0R / DD 9.0R |
| knn | EV > 0 | Validate 04–12/2025 | MUA | 273 | 39 | 29% | -0.120 | -0.236 | -32.8R / DD 47.8R |
| knn | EV > 0 | Validate 04–12/2025 | BÁN | 68 | 10 | 21% | -0.382 | -0.566 | -26.0R / DD 30.0R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 182 | 46 | 30% | -0.133 | -0.256 | -24.1R / DD 29.6R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 41 | 10 | 27% | -0.195 | -0.415 | -8.0R / DD 17.0R |
| knn | top 10% | Validate 04–12/2025 | MUA | 376 | 54 | 30% | -0.095 | -0.176 | -35.7R / DD 58.8R |
| knn | top 10% | Validate 04–12/2025 | BÁN | 104 | 15 | 25% | -0.250 | -0.395 | -26.0R / DD 33.0R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 217 | 54 | 23% | -0.323 | -0.420 | -70.0R / DD 74.0R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 154 | 38 | 29% | -0.166 | -0.282 | -25.5R / DD 36.5R |
| C2 time | EV > 0 | Validate 04–12/2025 | MUA | 276 | 39 | 29% | -0.132 | -0.225 | -36.4R / DD 53.4R |
| C2 time | EV > 0 | Validate 04–12/2025 | BÁN | 81 | 12 | 32% | -0.037 | -0.207 | -3.0R / DD 15.0R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 101 | 25 | 21% | -0.390 | -0.545 | -39.4R / DD 42.4R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 95 | 24 | 23% | -0.323 | -0.458 | -30.7R / DD 34.7R |
| C2 time | top 10% | Validate 04–12/2025 | MUA | 297 | 42 | 30% | -0.102 | -0.200 | -30.4R / DD 46.4R |
| C2 time | top 10% | Validate 04–12/2025 | BÁN | 94 | 13 | 31% | -0.069 | -0.244 | -6.5R / DD 16.5R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 370 | 92 | 31% | -0.066 | -0.159 | -24.3R / DD 36.3R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 253 | 63 | 31% | -0.068 | -0.187 | -17.3R / DD 39.0R |
| C3 no path | EV > 0 | Validate 04–12/2025 | MUA | 537 | 77 | 32% | -0.053 | -0.133 | -28.7R / DD 47.9R |
| C3 no path | EV > 0 | Validate 04–12/2025 | BÁN | 184 | 26 | 26% | -0.227 | -0.344 | -41.8R / DD 40.8R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 108 | 27 | 26% | -0.243 | -0.394 | -26.3R / DD 29.3R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 64 | 16 | 30% | -0.109 | -0.364 | -7.0R / DD 25.0R |
| C3 no path | top 10% | Validate 04–12/2025 | MUA | 287 | 41 | 33% | -0.007 | -0.100 | -2.0R / DD 34.0R |
| C3 no path | top 10% | Validate 04–12/2025 | BÁN | 46 | 7 | 24% | -0.283 | -0.510 | -13.0R / DD 15.0R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 395 | 99 | 29% | -0.132 | -0.208 | -52.3R / DD 65.4R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 261 | 65 | 31% | -0.086 | -0.186 | -22.3R / DD 44.0R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | MUA | 539 | 77 | 29% | -0.129 | -0.204 | -69.5R / DD 90.5R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | BÁN | 189 | 27 | 25% | -0.254 | -0.372 | -48.0R / DD 52.0R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 120 | 30 | 28% | -0.169 | -0.305 | -20.3R / DD 23.4R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 61 | 15 | 30% | -0.137 | -0.361 | -8.3R / DD 22.0R |
| C4 shuffled | top 10% | Validate 04–12/2025 | MUA | 308 | 44 | 31% | -0.084 | -0.172 | -26.0R / DD 40.0R |
| C4 shuffled | top 10% | Validate 04–12/2025 | BÁN | 69 | 10 | 28% | -0.174 | -0.392 | -12.0R / DD 18.0R |

## Đối chứng C1: chọn ngẫu nhiên (theo plan, không chồng lệnh)

- MUA: lgbm top 10% trên validate R/plan -0.083; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.173, 95% ≤ -0.090; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.040**
- BÁN: lgbm top 10% trên validate R/plan -0.194; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.224, 95% ≤ +0.030; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.475**

## Học tiếp theo thời gian (lgbm, từng tháng ngoài mẫu)

| Tháng | Plan học | Plan dự báo | AUC | R/plan top 10% EV trong tháng |
|---|---|---|---|---|
| 2024-12 | 7783 | 1512 | 0.557 | +0.097 |
| 2025-01 | 9297 | 1679 | 0.549 | -0.133 |
| 2025-02 | 10977 | 1435 | 0.560 | -0.177 |
| 2025-03 | 12411 | 1594 | 0.523 | -0.202 |
| 2025-04 | 14003 | 1607 | 0.497 | -0.124 |
| 2025-05 | 15606 | 1658 | 0.583 | +0.167 |
| 2025-06 | 17273 | 1584 | 0.542 | +0.057 |
| 2025-07 | 18851 | 1677 | 0.535 | -0.116 |
| 2025-08 | 20531 | 1494 | 0.576 | +0.023 |
| 2025-09 | 22022 | 1553 | 0.491 | -0.290 |
| 2025-10 | 23575 | 366 | 0.516 | -0.108 |

## Kiểm tra cuốn chiếu

| Tháng dự báo | Plan học | Plan dự báo | Lệnh học thoát muộn nhất |
|---|---|---|---|
| 2024-12 | 7783 | 1512 | 2024-11-29 19:45:00 |
| 2025-01 | 9297 | 1679 | 2024-12-31 21:50:00 |
| 2025-02 | 10977 | 1435 | 2025-01-31 22:00:00 |
| 2025-03 | 12411 | 1594 | 2025-02-28 21:00:00 |
| 2025-04 | 14003 | 1607 | 2025-03-31 23:25:00 |
| 2025-05 | 15606 | 1658 | 2025-04-30 23:20:00 |
| 2025-06 | 17273 | 1584 | 2025-05-30 20:30:00 |
| 2025-07 | 18851 | 1677 | 2025-06-30 23:30:00 |
| 2025-08 | 20531 | 1494 | 2025-07-31 23:45:00 |
| 2025-09 | 22022 | 1553 | 2025-08-31 23:55:00 |
| 2025-10 | 23575 | 366 | 2025-09-30 22:05:00 |
