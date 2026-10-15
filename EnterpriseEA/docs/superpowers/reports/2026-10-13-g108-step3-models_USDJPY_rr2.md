# G108 bước 3: plan học cuốn chiếu (kNN, LightGBM) và đối chứng

Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g108-m30-path-plans.md; bước 1–2: reports/2026-10-13-g108-patterns.md. Mỗi tháng từ 12/2024, mô hình học từ các plan đã **thoát lệnh trước ngày đầu tháng** (có assert trong code) rồi dự báo plan của tháng đó. **Kỳ test 2026 vẫn niêm phong.** Script: research/long/g108_features.py, g108_models.py.

Plan đã gộp (một plan một lần): 39233; có dự báo ngoài mẫu: 23310. p = xác suất chạm mục tiêu trước mức sai; EV = p × RR − (1 − p). Nhãn: mục tiêu cố định 2R.

## Mô hình có xếp hạng được plan không (AUC, ngoài mẫu)

| Mô hình | Kỳ | MUA | BÁN |
|---|---|---|---|
| lgbm | OOS 12/2024–03/2025 (cuối train) | 0.519 | 0.491 |
| lgbm | Validate 04–12/2025 | 0.528 | 0.543 |
| knn | OOS 12/2024–03/2025 (cuối train) | 0.548 | 0.496 |
| knn | Validate 04–12/2025 | 0.524 | 0.527 |
| C2 time | OOS 12/2024–03/2025 (cuối train) | 0.532 | 0.491 |
| C2 time | Validate 04–12/2025 | 0.518 | 0.524 |
| C3 no path | OOS 12/2024–03/2025 (cuối train) | 0.517 | 0.487 |
| C3 no path | Validate 04–12/2025 | 0.525 | 0.542 |
| C4 shuffled | OOS 12/2024–03/2025 (cuối train) | 0.508 | 0.487 |
| C4 shuffled | Validate 04–12/2025 | 0.524 | 0.542 |

AUC 0,5 = không hơn đoán mò. Lưu ý: RR là một đặc trưng, nên mô hình nào cũng học được "mục tiêu gần thì dễ chạm"; điều cần xem là lợi nhuận (bảng dưới), không phải AUC.

## Validate: R thực tế theo nhóm 10% EV dự báo (lgbm)

| Chiều | Nhóm EV (thấp → cao) | Plan | p dự báo | Thắng thực tế | R/plan |
|---|---|---|---|---|---|
| MUA | 1 | 751 | 0.15 | 21% | -0.348 |
| MUA | 2 | 750 | 0.21 | 26% | -0.202 |
| MUA | 3 | 751 | 0.23 | 24% | -0.234 |
| MUA | 4 | 750 | 0.25 | 28% | -0.147 |
| MUA | 5 | 751 | 0.27 | 25% | -0.248 |
| MUA | 6 | 750 | 0.28 | 27% | -0.196 |
| MUA | 7 | 750 | 0.29 | 29% | -0.137 |
| MUA | 8 | 751 | 0.31 | 28% | -0.145 |
| MUA | 9 | 750 | 0.34 | 28% | -0.142 |
| MUA | 10 | 751 | 0.40 | 29% | -0.135 |
| BÁN | 1 | 701 | 0.21 | 23% | -0.266 |
| BÁN | 2 | 700 | 0.24 | 25% | -0.230 |
| BÁN | 3 | 700 | 0.26 | 24% | -0.258 |
| BÁN | 4 | 700 | 0.27 | 26% | -0.216 |
| BÁN | 5 | 701 | 0.28 | 28% | -0.151 |
| BÁN | 6 | 700 | 0.29 | 26% | -0.206 |
| BÁN | 7 | 700 | 0.30 | 29% | -0.118 |
| BÁN | 8 | 700 | 0.32 | 33% | -0.007 |
| BÁN | 9 | 700 | 0.34 | 29% | -0.127 |
| BÁN | 10 | 701 | 0.39 | 34% | +0.031 |

## Lệnh không chồng (mỗi chiều một lệnh mỗi lúc)

| Mô hình | Quy tắc | Kỳ | Chiều | Lệnh | Lệnh/tháng | Thắng | R/lệnh | Cận dưới 90% | Tổng / DD |
|---|---|---|---|---|---|---|---|---|---|
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | MUA | 743 | 186 | 29% | -0.129 | -0.188 | -95.8R / DD 113.8R |
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | BÁN | 1016 | 254 | 29% | -0.150 | -0.196 | -152.7R / DD 157.7R |
| (vào mọi plan) | — | Validate 04–12/2025 | MUA | 1182 | 169 | 27% | -0.193 | -0.248 | -228.4R / DD 237.8R |
| (vào mọi plan) | — | Validate 04–12/2025 | BÁN | 1488 | 213 | 27% | -0.202 | -0.252 | -300.2R / DD 323.9R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 292 | 73 | 27% | -0.187 | -0.276 | -54.5R / DD 62.5R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 388 | 97 | 27% | -0.212 | -0.293 | -82.3R / DD 85.3R |
| lgbm | EV > 0 | Validate 04–12/2025 | MUA | 369 | 53 | 29% | -0.135 | -0.223 | -49.8R / DD 55.8R |
| lgbm | EV > 0 | Validate 04–12/2025 | BÁN | 484 | 69 | 30% | -0.101 | -0.172 | -48.9R / DD 75.1R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 92 | 23 | 27% | -0.185 | -0.321 | -17.0R / DD 20.0R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 113 | 28 | 22% | -0.350 | -0.508 | -39.6R / DD 38.6R |
| lgbm | top 10% | Validate 04–12/2025 | MUA | 160 | 23 | 32% | -0.025 | -0.154 | -4.0R / DD 17.0R |
| lgbm | top 10% | Validate 04–12/2025 | BÁN | 196 | 28 | 31% | -0.082 | -0.194 | -16.0R / DD 25.0R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 308 | 77 | 31% | -0.083 | -0.174 | -25.6R / DD 38.6R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 283 | 71 | 29% | -0.136 | -0.235 | -38.6R / DD 43.6R |
| knn | EV > 0 | Validate 04–12/2025 | MUA | 392 | 56 | 24% | -0.280 | -0.361 | -109.7R / DD 112.7R |
| knn | EV > 0 | Validate 04–12/2025 | BÁN | 467 | 67 | 31% | -0.084 | -0.163 | -39.0R / DD 54.0R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 149 | 37 | 38% | +0.138 | -0.007 | +20.6R / DD 9.0R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 130 | 32 | 24% | -0.285 | -0.420 | -37.0R / DD 44.0R |
| knn | top 10% | Validate 04–12/2025 | MUA | 215 | 31 | 29% | -0.134 | -0.252 | -28.7R / DD 32.7R |
| knn | top 10% | Validate 04–12/2025 | BÁN | 207 | 30 | 34% | +0.014 | -0.103 | +3.0R / DD 11.0R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 268 | 67 | 30% | -0.096 | -0.214 | -25.9R / DD 49.0R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 389 | 97 | 27% | -0.197 | -0.275 | -76.6R / DD 83.6R |
| C2 time | EV > 0 | Validate 04–12/2025 | MUA | 274 | 39 | 28% | -0.150 | -0.253 | -41.0R / DD 41.0R |
| C2 time | EV > 0 | Validate 04–12/2025 | BÁN | 377 | 54 | 27% | -0.189 | -0.280 | -71.1R / DD 80.1R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 79 | 20 | 28% | -0.165 | -0.346 | -13.0R / DD 24.0R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 95 | 24 | 25% | -0.242 | -0.419 | -23.0R / DD 29.0R |
| C2 time | top 10% | Validate 04–12/2025 | MUA | 198 | 28 | 28% | -0.157 | -0.273 | -31.0R / DD 32.0R |
| C2 time | top 10% | Validate 04–12/2025 | BÁN | 114 | 16 | 34% | +0.026 | -0.150 | +3.0R / DD 14.0R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 331 | 83 | 28% | -0.169 | -0.246 | -55.8R / DD 64.8R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 359 | 90 | 27% | -0.205 | -0.295 | -73.5R / DD 82.5R |
| C3 no path | EV > 0 | Validate 04–12/2025 | MUA | 378 | 54 | 26% | -0.211 | -0.310 | -79.8R / DD 84.8R |
| C3 no path | EV > 0 | Validate 04–12/2025 | BÁN | 423 | 60 | 29% | -0.140 | -0.219 | -59.3R / DD 71.3R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 91 | 23 | 23% | -0.308 | -0.448 | -28.0R / DD 31.0R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 102 | 26 | 22% | -0.353 | -0.518 | -36.0R / DD 35.0R |
| C3 no path | top 10% | Validate 04–12/2025 | MUA | 173 | 25 | 29% | -0.125 | -0.241 | -21.6R / DD 29.6R |
| C3 no path | top 10% | Validate 04–12/2025 | BÁN | 174 | 25 | 28% | -0.155 | -0.275 | -27.0R / DD 32.0R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 327 | 82 | 24% | -0.296 | -0.402 | -96.9R / DD 103.9R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 384 | 96 | 26% | -0.227 | -0.303 | -87.1R / DD 90.1R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | MUA | 406 | 58 | 29% | -0.147 | -0.245 | -59.8R / DD 65.8R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | BÁN | 489 | 70 | 31% | -0.078 | -0.138 | -38.3R / DD 58.8R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 108 | 27 | 25% | -0.267 | -0.406 | -28.8R / DD 32.8R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 95 | 24 | 21% | -0.384 | -0.552 | -36.5R / DD 38.5R |
| C4 shuffled | top 10% | Validate 04–12/2025 | MUA | 165 | 24 | 30% | -0.119 | -0.260 | -19.6R / DD 26.6R |
| C4 shuffled | top 10% | Validate 04–12/2025 | BÁN | 171 | 24 | 33% | -0.018 | -0.138 | -3.0R / DD 14.0R |

## Đối chứng C1: chọn ngẫu nhiên (theo plan, không chồng lệnh)

- MUA: lgbm top 10% trên validate R/plan -0.109; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.192, 95% ≤ -0.105; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.060**
- BÁN: lgbm top 10% trên validate R/plan +0.086; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.136, 95% ≤ -0.023; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.000**

## Học tiếp theo thời gian (lgbm, từng tháng ngoài mẫu)

| Tháng | Plan học | Plan dự báo | AUC | R/plan top 10% EV trong tháng |
|---|---|---|---|---|
| 2024-12 | 15914 | 2231 | 0.514 | -0.053 |
| 2025-01 | 18140 | 2413 | 0.492 | -0.415 |
| 2025-02 | 20557 | 2259 | 0.507 | -0.257 |
| 2025-03 | 22815 | 1899 | 0.510 | -0.368 |
| 2025-04 | 24705 | 2664 | 0.534 | -0.225 |
| 2025-05 | 27380 | 2866 | 0.518 | -0.164 |
| 2025-06 | 30238 | 2676 | 0.544 | +0.055 |
| 2025-07 | 32921 | 2162 | 0.540 | +0.037 |
| 2025-08 | 35083 | 1871 | 0.541 | -0.074 |
| 2025-09 | 36956 | 1833 | 0.547 | -0.120 |
| 2025-10 | 38777 | 436 | 0.490 | -0.114 |

## Kiểm tra cuốn chiếu

| Tháng dự báo | Plan học | Plan dự báo | Lệnh học thoát muộn nhất |
|---|---|---|---|
| 2024-12 | 15914 | 2231 | 2024-11-29 23:50:00 |
| 2025-01 | 18140 | 2413 | 2024-12-31 23:50:00 |
| 2025-02 | 20557 | 2259 | 2025-01-31 23:55:00 |
| 2025-03 | 22815 | 1899 | 2025-02-28 23:45:00 |
| 2025-04 | 24705 | 2664 | 2025-03-31 22:55:00 |
| 2025-05 | 27380 | 2866 | 2025-04-30 23:35:00 |
| 2025-06 | 30238 | 2676 | 2025-05-30 23:55:00 |
| 2025-07 | 32921 | 2162 | 2025-06-30 23:00:00 |
| 2025-08 | 35083 | 1871 | 2025-07-31 23:50:00 |
| 2025-09 | 36956 | 1833 | 2025-08-29 23:55:00 |
| 2025-10 | 38777 | 436 | 2025-09-30 23:15:00 |
