# G108 bước 3: plan học cuốn chiếu (kNN, LightGBM) và đối chứng

Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g108-m30-path-plans.md; bước 1–2: reports/2026-10-13-g108-patterns.md. Mỗi tháng từ 12/2024, mô hình học từ các plan đã **thoát lệnh trước ngày đầu tháng** (có assert trong code) rồi dự báo plan của tháng đó. **Kỳ test 2026 vẫn niêm phong.** Script: research/long/g108_features.py, g108_models.py.

Plan đã gộp (một plan một lần): 39233; có dự báo ngoài mẫu: 23310. p = xác suất chạm mục tiêu trước mức sai; EV = p × RR − (1 − p). Nhãn: mục tiêu cố định 3R.

## Mô hình có xếp hạng được plan không (AUC, ngoài mẫu)

| Mô hình | Kỳ | MUA | BÁN |
|---|---|---|---|
| lgbm | OOS 12/2024–03/2025 (cuối train) | 0.543 | 0.491 |
| lgbm | Validate 04–12/2025 | 0.530 | 0.535 |
| knn | OOS 12/2024–03/2025 (cuối train) | 0.558 | 0.485 |
| knn | Validate 04–12/2025 | 0.511 | 0.525 |
| C2 time | OOS 12/2024–03/2025 (cuối train) | 0.539 | 0.493 |
| C2 time | Validate 04–12/2025 | 0.520 | 0.522 |
| C3 no path | OOS 12/2024–03/2025 (cuối train) | 0.538 | 0.487 |
| C3 no path | Validate 04–12/2025 | 0.528 | 0.533 |
| C4 shuffled | OOS 12/2024–03/2025 (cuối train) | 0.535 | 0.481 |
| C4 shuffled | Validate 04–12/2025 | 0.527 | 0.533 |

AUC 0,5 = không hơn đoán mò. Lưu ý: RR là một đặc trưng, nên mô hình nào cũng học được "mục tiêu gần thì dễ chạm"; điều cần xem là lợi nhuận (bảng dưới), không phải AUC.

## Validate: R thực tế theo nhóm 10% EV dự báo (lgbm)

| Chiều | Nhóm EV (thấp → cao) | Plan | p dự báo | Thắng thực tế | R/plan |
|---|---|---|---|---|---|
| MUA | 1 | 751 | 0.09 | 17% | -0.190 |
| MUA | 2 | 750 | 0.14 | 16% | -0.308 |
| MUA | 3 | 751 | 0.16 | 19% | -0.199 |
| MUA | 4 | 750 | 0.18 | 19% | -0.208 |
| MUA | 5 | 751 | 0.19 | 19% | -0.205 |
| MUA | 6 | 750 | 0.21 | 17% | -0.297 |
| MUA | 7 | 750 | 0.22 | 22% | -0.114 |
| MUA | 8 | 751 | 0.24 | 23% | -0.080 |
| MUA | 9 | 750 | 0.26 | 20% | -0.178 |
| MUA | 10 | 751 | 0.32 | 21% | -0.151 |
| BÁN | 1 | 701 | 0.13 | 19% | -0.041 |
| BÁN | 2 | 700 | 0.17 | 17% | -0.272 |
| BÁN | 3 | 700 | 0.18 | 19% | -0.196 |
| BÁN | 4 | 700 | 0.19 | 18% | -0.243 |
| BÁN | 5 | 701 | 0.20 | 22% | -0.119 |
| BÁN | 6 | 700 | 0.21 | 21% | -0.149 |
| BÁN | 7 | 700 | 0.23 | 18% | -0.268 |
| BÁN | 8 | 700 | 0.24 | 22% | -0.107 |
| BÁN | 9 | 700 | 0.26 | 22% | -0.123 |
| BÁN | 10 | 701 | 0.32 | 26% | +0.070 |

## Lệnh không chồng (mỗi chiều một lệnh mỗi lúc)

| Mô hình | Quy tắc | Kỳ | Chiều | Lệnh | Lệnh/tháng | Thắng | R/lệnh | Cận dưới 90% | Tổng / DD |
|---|---|---|---|---|---|---|---|---|---|
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | MUA | 661 | 165 | 21% | -0.180 | -0.255 | -119.0R / DD 132.0R |
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | BÁN | 767 | 192 | 22% | -0.136 | -0.205 | -104.2R / DD 108.2R |
| (vào mọi plan) | — | Validate 04–12/2025 | MUA | 982 | 140 | 23% | -0.132 | -0.208 | -129.1R / DD 144.6R |
| (vào mọi plan) | — | Validate 04–12/2025 | BÁN | 1218 | 174 | 21% | -0.194 | -0.256 | -236.8R / DD 263.9R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 321 | 80 | 22% | -0.127 | -0.242 | -40.7R / DD 62.7R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 419 | 105 | 21% | -0.179 | -0.267 | -75.0R / DD 81.0R |
| lgbm | EV > 0 | Validate 04–12/2025 | MUA | 413 | 59 | 21% | -0.167 | -0.253 | -68.9R / DD 78.9R |
| lgbm | EV > 0 | Validate 04–12/2025 | BÁN | 467 | 67 | 22% | -0.144 | -0.237 | -67.1R / DD 81.1R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 88 | 22 | 15% | -0.416 | -0.588 | -36.6R / DD 44.0R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 109 | 27 | 18% | -0.266 | -0.438 | -29.0R / DD 35.0R |
| lgbm | top 10% | Validate 04–12/2025 | MUA | 156 | 22 | 24% | -0.051 | -0.212 | -8.0R / DD 23.0R |
| lgbm | top 10% | Validate 04–12/2025 | BÁN | 159 | 23 | 25% | +0.006 | -0.153 | +1.0R / DD 15.0R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 348 | 87 | 25% | -0.037 | -0.148 | -12.9R / DD 47.6R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 320 | 80 | 22% | -0.103 | -0.206 | -32.9R / DD 46.9R |
| knn | EV > 0 | Validate 04–12/2025 | MUA | 438 | 63 | 19% | -0.258 | -0.350 | -112.9R / DD 120.9R |
| knn | EV > 0 | Validate 04–12/2025 | BÁN | 524 | 75 | 23% | -0.108 | -0.198 | -56.6R / DD 72.8R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 105 | 26 | 23% | -0.153 | -0.343 | -16.0R / DD 27.6R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 89 | 22 | 13% | -0.457 | -0.677 | -40.6R / DD 39.6R |
| knn | top 10% | Validate 04–12/2025 | MUA | 180 | 26 | 22% | -0.124 | -0.291 | -22.4R / DD 28.1R |
| knn | top 10% | Validate 04–12/2025 | BÁN | 158 | 23 | 27% | +0.054 | -0.124 | +8.6R / DD 13.0R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 310 | 78 | 22% | -0.121 | -0.231 | -37.5R / DD 65.5R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 350 | 88 | 21% | -0.175 | -0.280 | -61.4R / DD 66.4R |
| C2 time | EV > 0 | Validate 04–12/2025 | MUA | 347 | 50 | 22% | -0.130 | -0.249 | -45.0R / DD 50.0R |
| C2 time | EV > 0 | Validate 04–12/2025 | BÁN | 420 | 60 | 21% | -0.159 | -0.256 | -66.6R / DD 77.6R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 91 | 23 | 21% | -0.165 | -0.392 | -15.0R / DD 35.0R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 71 | 18 | 18% | -0.268 | -0.483 | -19.0R / DD 23.0R |
| C2 time | top 10% | Validate 04–12/2025 | MUA | 177 | 25 | 24% | -0.058 | -0.204 | -10.2R / DD 20.2R |
| C2 time | top 10% | Validate 04–12/2025 | BÁN | 131 | 19 | 26% | +0.038 | -0.172 | +5.0R / DD 18.0R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 317 | 79 | 19% | -0.244 | -0.347 | -77.4R / DD 88.4R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 365 | 91 | 21% | -0.170 | -0.263 | -62.1R / DD 78.7R |
| C3 no path | EV > 0 | Validate 04–12/2025 | MUA | 406 | 58 | 23% | -0.099 | -0.205 | -40.2R / DD 54.2R |
| C3 no path | EV > 0 | Validate 04–12/2025 | BÁN | 436 | 62 | 22% | -0.133 | -0.226 | -57.8R / DD 69.8R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 84 | 21 | 13% | -0.501 | -0.680 | -42.1R / DD 50.5R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 102 | 26 | 18% | -0.294 | -0.475 | -30.0R / DD 36.0R |
| C3 no path | top 10% | Validate 04–12/2025 | MUA | 137 | 20 | 23% | -0.095 | -0.281 | -13.0R / DD 32.0R |
| C3 no path | top 10% | Validate 04–12/2025 | BÁN | 141 | 20 | 25% | -0.007 | -0.188 | -1.0R / DD 15.0R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 333 | 83 | 20% | -0.247 | -0.351 | -82.3R / DD 91.3R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 444 | 111 | 21% | -0.155 | -0.252 | -68.8R / DD 78.8R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | MUA | 448 | 64 | 20% | -0.198 | -0.285 | -88.5R / DD 90.5R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | BÁN | 455 | 65 | 21% | -0.153 | -0.244 | -69.4R / DD 81.4R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 88 | 22 | 14% | -0.455 | -0.604 | -40.0R / DD 45.0R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 120 | 30 | 19% | -0.233 | -0.406 | -28.0R / DD 31.0R |
| C4 shuffled | top 10% | Validate 04–12/2025 | MUA | 149 | 21 | 21% | -0.141 | -0.312 | -21.0R / DD 34.0R |
| C4 shuffled | top 10% | Validate 04–12/2025 | BÁN | 142 | 20 | 21% | -0.155 | -0.321 | -22.0R / DD 31.0R |

## Đối chứng C1: chọn ngẫu nhiên (theo plan, không chồng lệnh)

- MUA: lgbm top 10% trên validate R/plan -0.145; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.192, 95% ≤ -0.087; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.300**
- BÁN: lgbm top 10% trên validate R/plan +0.223; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.119, 95% ≤ +0.004; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.000**

## Học tiếp theo thời gian (lgbm, từng tháng ngoài mẫu)

| Tháng | Plan học | Plan dự báo | AUC | R/plan top 10% EV trong tháng |
|---|---|---|---|---|
| 2024-12 | 15912 | 2231 | 0.531 | -0.100 |
| 2025-01 | 18138 | 2413 | 0.495 | -0.341 |
| 2025-02 | 20554 | 2259 | 0.528 | -0.416 |
| 2025-03 | 22813 | 1899 | 0.523 | -0.116 |
| 2025-04 | 24701 | 2664 | 0.532 | -0.071 |
| 2025-05 | 27372 | 2866 | 0.518 | -0.062 |
| 2025-06 | 30230 | 2676 | 0.548 | +0.029 |
| 2025-07 | 32917 | 2162 | 0.547 | +0.050 |
| 2025-08 | 35081 | 1871 | 0.543 | -0.362 |
| 2025-09 | 36953 | 1833 | 0.528 | +0.022 |
| 2025-10 | 38774 | 436 | 0.460 | +0.000 |

## Kiểm tra cuốn chiếu

| Tháng dự báo | Plan học | Plan dự báo | Lệnh học thoát muộn nhất |
|---|---|---|---|
| 2024-12 | 15912 | 2231 | 2024-11-29 23:50:00 |
| 2025-01 | 18138 | 2413 | 2024-12-31 23:50:00 |
| 2025-02 | 20554 | 2259 | 2025-01-31 23:55:00 |
| 2025-03 | 22813 | 1899 | 2025-02-28 23:45:00 |
| 2025-04 | 24701 | 2664 | 2025-03-31 22:55:00 |
| 2025-05 | 27372 | 2866 | 2025-04-30 23:35:00 |
| 2025-06 | 30230 | 2676 | 2025-05-30 23:55:00 |
| 2025-07 | 32917 | 2162 | 2025-06-30 23:00:00 |
| 2025-08 | 35081 | 1871 | 2025-07-31 23:50:00 |
| 2025-09 | 36953 | 1833 | 2025-08-29 23:55:00 |
| 2025-10 | 38774 | 436 | 2025-09-30 23:10:00 |
