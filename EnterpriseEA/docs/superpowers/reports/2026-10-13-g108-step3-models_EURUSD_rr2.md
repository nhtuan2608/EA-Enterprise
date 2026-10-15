# G108 bước 3: plan học cuốn chiếu (kNN, LightGBM) và đối chứng

Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g108-m30-path-plans.md; bước 1–2: reports/2026-10-13-g108-patterns.md. Mỗi tháng từ 12/2024, mô hình học từ các plan đã **thoát lệnh trước ngày đầu tháng** (có assert trong code) rồi dự báo plan của tháng đó. **Kỳ test 2026 vẫn niêm phong.** Script: research/long/g108_features.py, g108_models.py.

Plan đã gộp (một plan một lần): 22930; có dự báo ngoài mẫu: 15609. p = xác suất chạm mục tiêu trước mức sai; EV = p × RR − (1 − p). Nhãn: mục tiêu cố định 2R.

## Mô hình có xếp hạng được plan không (AUC, ngoài mẫu)

| Mô hình | Kỳ | MUA | BÁN |
|---|---|---|---|
| lgbm | OOS 12/2024–03/2025 (cuối train) | 0.537 | 0.529 |
| lgbm | Validate 04–12/2025 | 0.522 | 0.554 |
| knn | OOS 12/2024–03/2025 (cuối train) | 0.507 | 0.509 |
| knn | Validate 04–12/2025 | 0.518 | 0.530 |
| C2 time | OOS 12/2024–03/2025 (cuối train) | 0.523 | 0.539 |
| C2 time | Validate 04–12/2025 | 0.498 | 0.552 |
| C3 no path | OOS 12/2024–03/2025 (cuối train) | 0.531 | 0.531 |
| C3 no path | Validate 04–12/2025 | 0.510 | 0.553 |
| C4 shuffled | OOS 12/2024–03/2025 (cuối train) | 0.520 | 0.519 |
| C4 shuffled | Validate 04–12/2025 | 0.496 | 0.544 |

AUC 0,5 = không hơn đoán mò. Lưu ý: RR là một đặc trưng, nên mô hình nào cũng học được "mục tiêu gần thì dễ chạm"; điều cần xem là lợi nhuận (bảng dưới), không phải AUC.

## Validate: R thực tế theo nhóm 10% EV dự báo (lgbm)

| Chiều | Nhóm EV (thấp → cao) | Plan | p dự báo | Thắng thực tế | R/plan |
|---|---|---|---|---|---|
| MUA | 1 | 502 | 0.16 | 31% | -0.080 |
| MUA | 2 | 502 | 0.21 | 24% | -0.272 |
| MUA | 3 | 502 | 0.23 | 25% | -0.247 |
| MUA | 4 | 502 | 0.25 | 24% | -0.264 |
| MUA | 5 | 502 | 0.27 | 27% | -0.174 |
| MUA | 6 | 502 | 0.28 | 29% | -0.113 |
| MUA | 7 | 502 | 0.30 | 30% | -0.074 |
| MUA | 8 | 502 | 0.32 | 30% | -0.086 |
| MUA | 9 | 502 | 0.35 | 28% | -0.151 |
| MUA | 10 | 502 | 0.41 | 32% | -0.030 |
| BÁN | 1 | 450 | 0.15 | 18% | -0.467 |
| BÁN | 2 | 450 | 0.19 | 22% | -0.336 |
| BÁN | 3 | 449 | 0.21 | 24% | -0.257 |
| BÁN | 4 | 450 | 0.23 | 26% | -0.231 |
| BÁN | 5 | 449 | 0.24 | 30% | -0.096 |
| BÁN | 6 | 450 | 0.25 | 25% | -0.249 |
| BÁN | 7 | 449 | 0.27 | 28% | -0.159 |
| BÁN | 8 | 450 | 0.28 | 31% | -0.073 |
| BÁN | 9 | 449 | 0.31 | 31% | -0.065 |
| BÁN | 10 | 450 | 0.36 | 30% | -0.096 |

## Lệnh không chồng (mỗi chiều một lệnh mỗi lúc)

| Mô hình | Quy tắc | Kỳ | Chiều | Lệnh | Lệnh/tháng | Thắng | R/lệnh | Cận dưới 90% | Tổng / DD |
|---|---|---|---|---|---|---|---|---|---|
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | MUA | 807 | 202 | 28% | -0.178 | -0.237 | -143.6R / DD 142.6R |
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | BÁN | 951 | 238 | 29% | -0.148 | -0.199 | -140.7R / DD 168.2R |
| (vào mọi plan) | — | Validate 04–12/2025 | MUA | 1345 | 192 | 28% | -0.153 | -0.198 | -205.5R / DD 226.5R |
| (vào mọi plan) | — | Validate 04–12/2025 | BÁN | 1614 | 231 | 27% | -0.196 | -0.238 | -316.7R / DD 319.7R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 261 | 65 | 28% | -0.171 | -0.260 | -44.6R / DD 50.6R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 253 | 63 | 32% | -0.064 | -0.167 | -16.3R / DD 36.7R |
| lgbm | EV > 0 | Validate 04–12/2025 | MUA | 498 | 71 | 31% | -0.089 | -0.162 | -44.1R / DD 69.3R |
| lgbm | EV > 0 | Validate 04–12/2025 | BÁN | 249 | 36 | 31% | -0.095 | -0.199 | -23.7R / DD 31.1R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 109 | 27 | 30% | -0.092 | -0.214 | -10.0R / DD 19.0R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 106 | 26 | 29% | -0.123 | -0.291 | -13.0R / DD 30.0R |
| lgbm | top 10% | Validate 04–12/2025 | MUA | 328 | 47 | 32% | -0.051 | -0.140 | -16.7R / DD 42.0R |
| lgbm | top 10% | Validate 04–12/2025 | BÁN | 135 | 19 | 33% | -0.028 | -0.170 | -3.7R / DD 14.0R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 96 | 24 | 22% | -0.344 | -0.495 | -33.0R / DD 37.0R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 47 | 12 | 34% | +0.021 | -0.234 | +1.0R / DD 13.0R |
| knn | EV > 0 | Validate 04–12/2025 | MUA | 287 | 41 | 34% | +0.006 | -0.088 | +1.7R / DD 17.8R |
| knn | EV > 0 | Validate 04–12/2025 | BÁN | 60 | 9 | 22% | -0.350 | -0.556 | -21.0R / DD 22.0R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 204 | 51 | 24% | -0.286 | -0.380 | -58.3R / DD 62.3R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 92 | 23 | 30% | -0.094 | -0.268 | -8.6R / DD 15.6R |
| knn | top 10% | Validate 04–12/2025 | MUA | 466 | 67 | 34% | +0.006 | -0.068 | +2.7R / DD 26.8R |
| knn | top 10% | Validate 04–12/2025 | BÁN | 206 | 29 | 26% | -0.228 | -0.353 | -47.0R / DD 53.0R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 134 | 34 | 27% | -0.194 | -0.331 | -26.0R / DD 33.0R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 174 | 44 | 32% | -0.038 | -0.181 | -6.6R / DD 23.0R |
| C2 time | EV > 0 | Validate 04–12/2025 | MUA | 177 | 25 | 29% | -0.149 | -0.280 | -26.5R / DD 31.6R |
| C2 time | EV > 0 | Validate 04–12/2025 | BÁN | 201 | 29 | 32% | -0.044 | -0.173 | -8.9R / DD 20.9R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 81 | 20 | 27% | -0.185 | -0.407 | -15.0R / DD 20.0R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 125 | 31 | 31% | -0.069 | -0.243 | -8.6R / DD 20.0R |
| C2 time | top 10% | Validate 04–12/2025 | MUA | 225 | 32 | 29% | -0.131 | -0.244 | -29.5R / DD 32.5R |
| C2 time | top 10% | Validate 04–12/2025 | BÁN | 261 | 37 | 32% | -0.046 | -0.171 | -11.9R / DD 24.9R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 261 | 65 | 27% | -0.209 | -0.296 | -54.7R / DD 56.7R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 245 | 61 | 31% | -0.089 | -0.203 | -21.8R / DD 48.1R |
| C3 no path | EV > 0 | Validate 04–12/2025 | MUA | 468 | 67 | 30% | -0.100 | -0.184 | -47.0R / DD 56.0R |
| C3 no path | EV > 0 | Validate 04–12/2025 | BÁN | 231 | 33 | 29% | -0.145 | -0.250 | -33.5R / DD 41.5R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 92 | 23 | 29% | -0.120 | -0.275 | -11.0R / DD 16.0R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 66 | 16 | 23% | -0.318 | -0.493 | -21.0R / DD 24.0R |
| C3 no path | top 10% | Validate 04–12/2025 | MUA | 275 | 39 | 29% | -0.152 | -0.241 | -41.7R / DD 47.7R |
| C3 no path | top 10% | Validate 04–12/2025 | BÁN | 114 | 16 | 28% | -0.150 | -0.308 | -17.2R / DD 20.2R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 306 | 76 | 27% | -0.192 | -0.270 | -58.7R / DD 67.7R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 278 | 70 | 29% | -0.147 | -0.262 | -40.9R / DD 59.9R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | MUA | 520 | 74 | 28% | -0.165 | -0.239 | -85.6R / DD 105.6R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | BÁN | 254 | 36 | 31% | -0.075 | -0.185 | -19.2R / DD 27.2R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 122 | 30 | 27% | -0.189 | -0.328 | -23.0R / DD 28.0R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 104 | 26 | 26% | -0.238 | -0.395 | -24.8R / DD 35.8R |
| C4 shuffled | top 10% | Validate 04–12/2025 | MUA | 361 | 52 | 27% | -0.191 | -0.276 | -69.0R / DD 79.0R |
| C4 shuffled | top 10% | Validate 04–12/2025 | BÁN | 142 | 20 | 26% | -0.218 | -0.356 | -31.0R / DD 32.0R |

## Đối chứng C1: chọn ngẫu nhiên (theo plan, không chồng lệnh)

- MUA: lgbm top 10% trên validate R/plan -0.056; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.160, 95% ≤ -0.075; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.015**
- BÁN: lgbm top 10% trên validate R/plan -0.009; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.189, 95% ≤ -0.037; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.020**

## Học tiếp theo thời gian (lgbm, từng tháng ngoài mẫu)

| Tháng | Plan học | Plan dự báo | AUC | R/plan top 10% EV trong tháng |
|---|---|---|---|---|
| 2024-12 | 7317 | 1515 | 0.541 | -0.277 |
| 2025-01 | 8829 | 1610 | 0.530 | -0.183 |
| 2025-02 | 10441 | 1418 | 0.522 | -0.070 |
| 2025-03 | 11857 | 1550 | 0.543 | -0.051 |
| 2025-04 | 13405 | 1583 | 0.532 | +0.106 |
| 2025-05 | 14994 | 1670 | 0.529 | -0.102 |
| 2025-06 | 16661 | 1514 | 0.552 | +0.086 |
| 2025-07 | 18176 | 1599 | 0.574 | -0.063 |
| 2025-08 | 19773 | 1490 | 0.502 | -0.219 |
| 2025-09 | 21269 | 1524 | 0.543 | -0.157 |
| 2025-10 | 22788 | 136 | 0.538 | +0.286 |

## Kiểm tra cuốn chiếu

| Tháng dự báo | Plan học | Plan dự báo | Lệnh học thoát muộn nhất |
|---|---|---|---|
| 2024-12 | 7317 | 1515 | 2024-11-29 23:55:00 |
| 2025-01 | 8829 | 1610 | 2024-12-31 23:50:00 |
| 2025-02 | 10441 | 1418 | 2025-01-31 23:15:00 |
| 2025-03 | 11857 | 1550 | 2025-02-28 23:00:00 |
| 2025-04 | 13405 | 1583 | 2025-03-31 23:10:00 |
| 2025-05 | 14994 | 1670 | 2025-04-30 23:10:00 |
| 2025-06 | 16661 | 1514 | 2025-05-30 23:30:00 |
| 2025-07 | 18176 | 1599 | 2025-06-30 23:55:00 |
| 2025-08 | 19773 | 1490 | 2025-07-31 23:05:00 |
| 2025-09 | 21269 | 1524 | 2025-08-29 23:55:00 |
| 2025-10 | 22788 | 136 | 2025-09-30 23:55:00 |
