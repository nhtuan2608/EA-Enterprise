# G108 bước 3: plan học cuốn chiếu (kNN, LightGBM) và đối chứng

Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g108-m30-path-plans.md; bước 1–2: reports/2026-10-13-g108-patterns.md. Mỗi tháng từ 12/2024, mô hình học từ các plan đã **thoát lệnh trước ngày đầu tháng** (có assert trong code) rồi dự báo plan của tháng đó. **Kỳ test 2026 vẫn niêm phong.** Script: research/long/g108_features.py, g108_models.py.

Plan đã gộp (một plan một lần): 23229; có dự báo ngoài mẫu: 15806. p = xác suất chạm mục tiêu trước mức sai; EV = p × RR − (1 − p). Nhãn: mục tiêu cố định 3R.

## Mô hình có xếp hạng được plan không (AUC, ngoài mẫu)

| Mô hình | Kỳ | MUA | BÁN |
|---|---|---|---|
| lgbm | OOS 12/2024–03/2025 (cuối train) | 0.536 | 0.521 |
| lgbm | Validate 04–12/2025 | 0.523 | 0.568 |
| knn | OOS 12/2024–03/2025 (cuối train) | 0.517 | 0.495 |
| knn | Validate 04–12/2025 | 0.513 | 0.542 |
| C2 time | OOS 12/2024–03/2025 (cuối train) | 0.511 | 0.525 |
| C2 time | Validate 04–12/2025 | 0.493 | 0.548 |
| C3 no path | OOS 12/2024–03/2025 (cuối train) | 0.518 | 0.518 |
| C3 no path | Validate 04–12/2025 | 0.508 | 0.570 |
| C4 shuffled | OOS 12/2024–03/2025 (cuối train) | 0.517 | 0.520 |
| C4 shuffled | Validate 04–12/2025 | 0.504 | 0.562 |

AUC 0,5 = không hơn đoán mò. Lưu ý: RR là một đặc trưng, nên mô hình nào cũng học được "mục tiêu gần thì dễ chạm"; điều cần xem là lợi nhuận (bảng dưới), không phải AUC.

## Validate: R thực tế theo nhóm 10% EV dự báo (lgbm)

| Chiều | Nhóm EV (thấp → cao) | Plan | p dự báo | Thắng thực tế | R/plan |
|---|---|---|---|---|---|
| MUA | 1 | 509 | 0.11 | 20% | -0.132 |
| MUA | 2 | 509 | 0.15 | 19% | -0.188 |
| MUA | 3 | 508 | 0.17 | 17% | -0.310 |
| MUA | 4 | 509 | 0.18 | 19% | -0.191 |
| MUA | 5 | 509 | 0.20 | 22% | -0.109 |
| MUA | 6 | 508 | 0.21 | 21% | -0.130 |
| MUA | 7 | 509 | 0.23 | 22% | -0.116 |
| MUA | 8 | 508 | 0.25 | 20% | -0.161 |
| MUA | 9 | 509 | 0.28 | 25% | -0.010 |
| MUA | 10 | 509 | 0.35 | 22% | -0.081 |
| BÁN | 1 | 455 | 0.09 | 12% | -0.454 |
| BÁN | 2 | 455 | 0.12 | 15% | -0.393 |
| BÁN | 3 | 454 | 0.14 | 17% | -0.309 |
| BÁN | 4 | 455 | 0.16 | 17% | -0.306 |
| BÁN | 5 | 455 | 0.17 | 17% | -0.306 |
| BÁN | 6 | 454 | 0.18 | 19% | -0.246 |
| BÁN | 7 | 455 | 0.20 | 24% | -0.042 |
| BÁN | 8 | 454 | 0.21 | 24% | -0.023 |
| BÁN | 9 | 455 | 0.23 | 22% | -0.099 |
| BÁN | 10 | 455 | 0.28 | 23% | -0.076 |

## Lệnh không chồng (mỗi chiều một lệnh mỗi lúc)

| Mô hình | Quy tắc | Kỳ | Chiều | Lệnh | Lệnh/tháng | Thắng | R/lệnh | Cận dưới 90% | Tổng / DD |
|---|---|---|---|---|---|---|---|---|---|
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | MUA | 614 | 154 | 22% | -0.142 | -0.224 | -87.1R / DD 95.4R |
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | BÁN | 698 | 174 | 22% | -0.141 | -0.216 | -98.3R / DD 127.2R |
| (vào mọi plan) | — | Validate 04–12/2025 | MUA | 940 | 134 | 22% | -0.138 | -0.205 | -129.8R / DD 157.3R |
| (vào mọi plan) | — | Validate 04–12/2025 | BÁN | 1254 | 179 | 20% | -0.223 | -0.285 | -279.3R / DD 278.3R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 296 | 74 | 23% | -0.091 | -0.203 | -26.9R / DD 42.9R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 256 | 64 | 23% | -0.108 | -0.238 | -27.7R / DD 40.7R |
| lgbm | EV > 0 | Validate 04–12/2025 | MUA | 465 | 66 | 23% | -0.087 | -0.190 | -40.6R / DD 67.8R |
| lgbm | EV > 0 | Validate 04–12/2025 | BÁN | 256 | 37 | 22% | -0.109 | -0.221 | -28.0R / DD 41.0R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 95 | 24 | 19% | -0.242 | -0.448 | -23.0R / DD 26.0R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 69 | 17 | 25% | -0.014 | -0.342 | -1.0R / DD 18.0R |
| lgbm | top 10% | Validate 04–12/2025 | MUA | 285 | 41 | 27% | +0.060 | -0.060 | +17.0R / DD 39.9R |
| lgbm | top 10% | Validate 04–12/2025 | BÁN | 110 | 16 | 15% | -0.382 | -0.524 | -42.0R / DD 47.0R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 121 | 30 | 21% | -0.174 | -0.339 | -21.0R / DD 32.0R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 84 | 21 | 20% | -0.206 | -0.435 | -17.3R / DD 20.3R |
| knn | EV > 0 | Validate 04–12/2025 | MUA | 337 | 48 | 22% | -0.187 | -0.290 | -62.9R / DD 85.7R |
| knn | EV > 0 | Validate 04–12/2025 | BÁN | 112 | 16 | 17% | -0.321 | -0.492 | -36.0R / DD 40.0R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 165 | 41 | 19% | -0.222 | -0.342 | -36.6R / DD 38.6R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 92 | 23 | 27% | +0.032 | -0.213 | +3.0R / DD 16.1R |
| knn | top 10% | Validate 04–12/2025 | MUA | 444 | 63 | 24% | -0.107 | -0.204 | -47.7R / DD 69.9R |
| knn | top 10% | Validate 04–12/2025 | BÁN | 169 | 24 | 20% | -0.195 | -0.345 | -33.0R / DD 42.0R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 171 | 43 | 23% | -0.064 | -0.213 | -11.0R / DD 39.0R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 151 | 38 | 23% | -0.130 | -0.290 | -19.6R / DD 21.6R |
| C2 time | EV > 0 | Validate 04–12/2025 | MUA | 281 | 40 | 24% | -0.085 | -0.201 | -23.9R / DD 44.7R |
| C2 time | EV > 0 | Validate 04–12/2025 | BÁN | 120 | 17 | 16% | -0.388 | -0.538 | -46.6R / DD 48.6R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 115 | 29 | 28% | +0.113 | -0.059 | +13.0R / DD 16.0R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 79 | 20 | 23% | -0.174 | -0.387 | -13.8R / DD 21.9R |
| C2 time | top 10% | Validate 04–12/2025 | MUA | 291 | 42 | 24% | -0.062 | -0.164 | -17.9R / DD 43.7R |
| C2 time | top 10% | Validate 04–12/2025 | BÁN | 147 | 21 | 16% | -0.392 | -0.541 | -57.6R / DD 57.6R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 272 | 68 | 25% | -0.005 | -0.108 | -1.3R / DD 20.6R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 242 | 60 | 24% | -0.062 | -0.205 | -15.0R / DD 44.0R |
| C3 no path | EV > 0 | Validate 04–12/2025 | MUA | 430 | 61 | 23% | -0.129 | -0.220 | -55.4R / DD 88.9R |
| C3 no path | EV > 0 | Validate 04–12/2025 | BÁN | 289 | 41 | 23% | -0.095 | -0.193 | -27.6R / DD 41.6R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 92 | 23 | 18% | -0.257 | -0.464 | -23.6R / DD 30.6R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 51 | 13 | 24% | -0.059 | -0.429 | -3.0R / DD 19.0R |
| C3 no path | top 10% | Validate 04–12/2025 | MUA | 220 | 31 | 23% | -0.085 | -0.216 | -18.6R / DD 25.7R |
| C3 no path | top 10% | Validate 04–12/2025 | BÁN | 103 | 15 | 19% | -0.223 | -0.412 | -23.0R / DD 33.0R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 301 | 75 | 20% | -0.227 | -0.326 | -68.3R / DD 78.3R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 286 | 72 | 22% | -0.140 | -0.264 | -40.1R / DD 58.1R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | MUA | 572 | 82 | 20% | -0.193 | -0.270 | -110.4R / DD 129.3R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | BÁN | 320 | 46 | 22% | -0.138 | -0.231 | -44.0R / DD 51.0R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 95 | 24 | 28% | +0.078 | -0.136 | +7.4R / DD 13.6R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 72 | 18 | 22% | -0.111 | -0.371 | -8.0R / DD 21.0R |
| C4 shuffled | top 10% | Validate 04–12/2025 | MUA | 324 | 46 | 20% | -0.210 | -0.320 | -68.1R / DD 70.6R |
| C4 shuffled | top 10% | Validate 04–12/2025 | BÁN | 117 | 17 | 17% | -0.316 | -0.469 | -37.0R / DD 40.0R |

## Đối chứng C1: chọn ngẫu nhiên (theo plan, không chồng lệnh)

- MUA: lgbm top 10% trên validate R/plan -0.040; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.156, 95% ≤ -0.058; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.025**
- BÁN: lgbm top 10% trên validate R/plan -0.391; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.221, 95% ≤ +0.027; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.925**

## Học tiếp theo thời gian (lgbm, từng tháng ngoài mẫu)

| Tháng | Plan học | Plan dự báo | AUC | R/plan top 10% EV trong tháng |
|---|---|---|---|---|
| 2024-12 | 7417 | 1533 | 0.562 | -0.163 |
| 2025-01 | 8950 | 1637 | 0.510 | -0.171 |
| 2025-02 | 10588 | 1429 | 0.499 | -0.257 |
| 2025-03 | 12014 | 1573 | 0.553 | +0.038 |
| 2025-04 | 13584 | 1603 | 0.508 | +0.247 |
| 2025-05 | 15187 | 1678 | 0.570 | -0.048 |
| 2025-06 | 16867 | 1548 | 0.569 | -0.071 |
| 2025-07 | 18413 | 1616 | 0.567 | -0.185 |
| 2025-08 | 20029 | 1520 | 0.535 | -0.229 |
| 2025-09 | 21543 | 1543 | 0.524 | -0.292 |
| 2025-10 | 23096 | 126 | 0.489 | -0.385 |

## Kiểm tra cuốn chiếu

| Tháng dự báo | Plan học | Plan dự báo | Lệnh học thoát muộn nhất |
|---|---|---|---|
| 2024-12 | 7417 | 1533 | 2024-11-29 21:55:00 |
| 2025-01 | 8950 | 1637 | 2024-12-31 22:00:00 |
| 2025-02 | 10588 | 1429 | 2025-01-31 21:15:00 |
| 2025-03 | 12014 | 1573 | 2025-02-28 21:00:00 |
| 2025-04 | 13584 | 1603 | 2025-03-31 23:25:00 |
| 2025-05 | 15187 | 1678 | 2025-04-30 23:15:00 |
| 2025-06 | 16867 | 1548 | 2025-05-30 20:30:00 |
| 2025-07 | 18413 | 1616 | 2025-06-30 23:30:00 |
| 2025-08 | 20029 | 1520 | 2025-07-31 23:50:00 |
| 2025-09 | 21543 | 1543 | 2025-08-31 23:55:00 |
| 2025-10 | 23096 | 126 | 2025-09-30 23:15:00 |
