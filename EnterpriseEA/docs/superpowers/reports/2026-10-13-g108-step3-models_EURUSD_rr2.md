# G108 bước 3: plan học cuốn chiếu (kNN, LightGBM) và đối chứng

Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g108-m30-path-plans.md; bước 1–2: reports/2026-10-13-g108-patterns.md. Mỗi tháng từ 12/2024, mô hình học từ các plan đã **thoát lệnh trước ngày đầu tháng** (có assert trong code) rồi dự báo plan của tháng đó. **Kỳ test 2026 vẫn niêm phong.** Script: research/long/g108_features.py, g108_models.py.

Plan đã gộp (một plan một lần): 23229; có dự báo ngoài mẫu: 15806. p = xác suất chạm mục tiêu trước mức sai; EV = p × RR − (1 − p). Nhãn: mục tiêu cố định 2R.

## Mô hình có xếp hạng được plan không (AUC, ngoài mẫu)

| Mô hình | Kỳ | MUA | BÁN |
|---|---|---|---|
| lgbm | OOS 12/2024–03/2025 (cuối train) | 0.529 | 0.527 |
| lgbm | Validate 04–12/2025 | 0.524 | 0.563 |
| knn | OOS 12/2024–03/2025 (cuối train) | 0.525 | 0.498 |
| knn | Validate 04–12/2025 | 0.516 | 0.542 |
| C2 time | OOS 12/2024–03/2025 (cuối train) | 0.530 | 0.538 |
| C2 time | Validate 04–12/2025 | 0.503 | 0.557 |
| C3 no path | OOS 12/2024–03/2025 (cuối train) | 0.527 | 0.534 |
| C3 no path | Validate 04–12/2025 | 0.521 | 0.552 |
| C4 shuffled | OOS 12/2024–03/2025 (cuối train) | 0.515 | 0.531 |
| C4 shuffled | Validate 04–12/2025 | 0.503 | 0.546 |

AUC 0,5 = không hơn đoán mò. Lưu ý: RR là một đặc trưng, nên mô hình nào cũng học được "mục tiêu gần thì dễ chạm"; điều cần xem là lợi nhuận (bảng dưới), không phải AUC.

## Validate: R thực tế theo nhóm 10% EV dự báo (lgbm)

| Chiều | Nhóm EV (thấp → cao) | Plan | p dự báo | Thắng thực tế | R/plan |
|---|---|---|---|---|---|
| MUA | 1 | 509 | 0.16 | 32% | -0.045 |
| MUA | 2 | 509 | 0.21 | 24% | -0.271 |
| MUA | 3 | 508 | 0.24 | 22% | -0.320 |
| MUA | 4 | 509 | 0.25 | 28% | -0.157 |
| MUA | 5 | 509 | 0.27 | 26% | -0.222 |
| MUA | 6 | 508 | 0.28 | 27% | -0.194 |
| MUA | 7 | 509 | 0.30 | 29% | -0.112 |
| MUA | 8 | 508 | 0.32 | 29% | -0.112 |
| MUA | 9 | 509 | 0.35 | 32% | -0.044 |
| MUA | 10 | 509 | 0.42 | 33% | -0.004 |
| BÁN | 1 | 455 | 0.15 | 16% | -0.502 |
| BÁN | 2 | 455 | 0.19 | 23% | -0.312 |
| BÁN | 3 | 454 | 0.21 | 23% | -0.308 |
| BÁN | 4 | 455 | 0.23 | 23% | -0.304 |
| BÁN | 5 | 455 | 0.24 | 28% | -0.149 |
| BÁN | 6 | 454 | 0.25 | 27% | -0.179 |
| BÁN | 7 | 455 | 0.27 | 33% | +0.005 |
| BÁN | 8 | 454 | 0.29 | 31% | -0.070 |
| BÁN | 9 | 455 | 0.31 | 33% | -0.016 |
| BÁN | 10 | 455 | 0.37 | 28% | -0.160 |

## Lệnh không chồng (mỗi chiều một lệnh mỗi lúc)

| Mô hình | Quy tắc | Kỳ | Chiều | Lệnh | Lệnh/tháng | Thắng | R/lệnh | Cận dưới 90% | Tổng / DD |
|---|---|---|---|---|---|---|---|---|---|
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | MUA | 808 | 202 | 28% | -0.175 | -0.237 | -141.6R / DD 140.6R |
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | BÁN | 955 | 239 | 29% | -0.148 | -0.197 | -141.7R / DD 168.2R |
| (vào mọi plan) | — | Validate 04–12/2025 | MUA | 1346 | 192 | 28% | -0.153 | -0.198 | -206.5R / DD 223.5R |
| (vào mọi plan) | — | Validate 04–12/2025 | BÁN | 1609 | 230 | 27% | -0.192 | -0.237 | -308.7R / DD 312.7R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 298 | 74 | 29% | -0.155 | -0.245 | -46.2R / DD 52.2R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 269 | 67 | 33% | +0.001 | -0.091 | +0.4R / DD 19.0R |
| lgbm | EV > 0 | Validate 04–12/2025 | MUA | 465 | 66 | 32% | -0.037 | -0.109 | -17.1R / DD 61.5R |
| lgbm | EV > 0 | Validate 04–12/2025 | BÁN | 257 | 37 | 28% | -0.170 | -0.252 | -43.7R / DD 49.7R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 111 | 28 | 27% | -0.198 | -0.335 | -22.0R / DD 29.0R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 82 | 20 | 26% | -0.239 | -0.413 | -19.6R / DD 26.0R |
| lgbm | top 10% | Validate 04–12/2025 | MUA | 312 | 45 | 31% | -0.077 | -0.171 | -23.9R / DD 36.9R |
| lgbm | top 10% | Validate 04–12/2025 | BÁN | 130 | 19 | 25% | -0.270 | -0.388 | -35.1R / DD 36.1R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 89 | 22 | 28% | -0.157 | -0.337 | -14.0R / DD 20.0R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 52 | 13 | 31% | -0.077 | -0.294 | -4.0R / DD 11.0R |
| knn | EV > 0 | Validate 04–12/2025 | MUA | 258 | 37 | 33% | -0.057 | -0.147 | -14.7R / DD 29.7R |
| knn | EV > 0 | Validate 04–12/2025 | BÁN | 78 | 11 | 29% | -0.115 | -0.321 | -9.0R / DD 18.0R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 173 | 43 | 28% | -0.168 | -0.282 | -29.1R / DD 30.1R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 101 | 25 | 31% | -0.088 | -0.236 | -8.9R / DD 19.9R |
| knn | top 10% | Validate 04–12/2025 | MUA | 480 | 69 | 32% | -0.062 | -0.134 | -29.7R / DD 50.7R |
| knn | top 10% | Validate 04–12/2025 | BÁN | 267 | 38 | 26% | -0.213 | -0.312 | -57.0R / DD 57.0R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 184 | 46 | 28% | -0.159 | -0.288 | -29.2R / DD 38.2R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 155 | 39 | 30% | -0.130 | -0.266 | -20.2R / DD 37.5R |
| C2 time | EV > 0 | Validate 04–12/2025 | MUA | 234 | 33 | 33% | -0.020 | -0.149 | -4.7R / DD 30.6R |
| C2 time | EV > 0 | Validate 04–12/2025 | BÁN | 168 | 24 | 28% | -0.170 | -0.302 | -28.6R / DD 34.6R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 119 | 30 | 32% | -0.052 | -0.216 | -6.2R / DD 15.0R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 110 | 28 | 26% | -0.238 | -0.424 | -26.2R / DD 32.5R |
| C2 time | top 10% | Validate 04–12/2025 | MUA | 260 | 37 | 32% | -0.049 | -0.173 | -12.7R / DD 32.6R |
| C2 time | top 10% | Validate 04–12/2025 | BÁN | 199 | 28 | 29% | -0.153 | -0.272 | -30.4R / DD 37.6R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 292 | 73 | 29% | -0.146 | -0.237 | -42.5R / DD 51.5R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 250 | 62 | 31% | -0.075 | -0.182 | -18.7R / DD 35.7R |
| C3 no path | EV > 0 | Validate 04–12/2025 | MUA | 420 | 60 | 30% | -0.122 | -0.207 | -51.1R / DD 70.1R |
| C3 no path | EV > 0 | Validate 04–12/2025 | BÁN | 271 | 39 | 27% | -0.202 | -0.290 | -54.7R / DD 54.7R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 89 | 22 | 26% | -0.244 | -0.406 | -21.7R / DD 25.7R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 72 | 18 | 31% | -0.083 | -0.304 | -6.0R / DD 20.0R |
| C3 no path | top 10% | Validate 04–12/2025 | MUA | 250 | 36 | 28% | -0.179 | -0.274 | -44.9R / DD 56.9R |
| C3 no path | top 10% | Validate 04–12/2025 | BÁN | 124 | 18 | 25% | -0.243 | -0.392 | -30.2R / DD 35.2R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 295 | 74 | 31% | -0.097 | -0.196 | -28.5R / DD 41.5R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 279 | 70 | 31% | -0.071 | -0.162 | -19.7R / DD 37.7R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | MUA | 527 | 75 | 30% | -0.113 | -0.181 | -59.7R / DD 65.7R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | BÁN | 309 | 44 | 28% | -0.155 | -0.230 | -48.0R / DD 55.0R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 126 | 32 | 28% | -0.182 | -0.328 | -22.9R / DD 26.9R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 92 | 23 | 25% | -0.250 | -0.407 | -23.0R / DD 34.0R |
| C4 shuffled | top 10% | Validate 04–12/2025 | MUA | 322 | 46 | 31% | -0.081 | -0.179 | -25.9R / DD 44.9R |
| C4 shuffled | top 10% | Validate 04–12/2025 | BÁN | 145 | 21 | 26% | -0.214 | -0.336 | -31.0R / DD 32.0R |

## Đối chứng C1: chọn ngẫu nhiên (theo plan, không chồng lệnh)

- MUA: lgbm top 10% trên validate R/plan -0.031; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.160, 95% ≤ -0.077; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.015**
- BÁN: lgbm top 10% trên validate R/plan -0.207; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.181, 95% ≤ -0.024; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.605**

## Học tiếp theo thời gian (lgbm, từng tháng ngoài mẫu)

| Tháng | Plan học | Plan dự báo | AUC | R/plan top 10% EV trong tháng |
|---|---|---|---|---|
| 2024-12 | 7419 | 1533 | 0.551 | -0.188 |
| 2025-01 | 8950 | 1637 | 0.509 | -0.207 |
| 2025-02 | 10588 | 1429 | 0.527 | -0.236 |
| 2025-03 | 12015 | 1573 | 0.535 | -0.126 |
| 2025-04 | 13586 | 1603 | 0.524 | +0.006 |
| 2025-05 | 15188 | 1678 | 0.558 | -0.043 |
| 2025-06 | 16870 | 1548 | 0.535 | -0.071 |
| 2025-07 | 18415 | 1616 | 0.580 | -0.056 |
| 2025-08 | 20031 | 1520 | 0.521 | -0.103 |
| 2025-09 | 21546 | 1543 | 0.533 | -0.254 |
| 2025-10 | 23096 | 126 | 0.547 | +0.385 |

## Kiểm tra cuốn chiếu

| Tháng dự báo | Plan học | Plan dự báo | Lệnh học thoát muộn nhất |
|---|---|---|---|
| 2024-12 | 7419 | 1533 | 2024-11-29 21:55:00 |
| 2025-01 | 8950 | 1637 | 2024-12-31 22:00:00 |
| 2025-02 | 10588 | 1429 | 2025-01-31 21:15:00 |
| 2025-03 | 12015 | 1573 | 2025-02-28 21:00:00 |
| 2025-04 | 13586 | 1603 | 2025-03-31 23:25:00 |
| 2025-05 | 15188 | 1678 | 2025-04-30 23:15:00 |
| 2025-06 | 16870 | 1548 | 2025-05-30 20:30:00 |
| 2025-07 | 18415 | 1616 | 2025-06-30 23:30:00 |
| 2025-08 | 20031 | 1520 | 2025-07-31 23:50:00 |
| 2025-09 | 21546 | 1543 | 2025-08-31 23:55:00 |
| 2025-10 | 23096 | 126 | 2025-09-30 23:15:00 |
