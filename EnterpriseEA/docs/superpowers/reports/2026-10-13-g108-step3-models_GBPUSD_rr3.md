# G108 bước 3: plan học cuốn chiếu (kNN, LightGBM) và đối chứng

Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g108-m30-path-plans.md; bước 1–2: reports/2026-10-13-g108-patterns.md. Mỗi tháng từ 12/2024, mô hình học từ các plan đã **thoát lệnh trước ngày đầu tháng** (có assert trong code) rồi dự báo plan của tháng đó. **Kỳ test 2026 vẫn niêm phong.** Script: research/long/g108_features.py, g108_models.py.

Plan đã gộp (một plan một lần): 23583; có dự báo ngoài mẫu: 15898. p = xác suất chạm mục tiêu trước mức sai; EV = p × RR − (1 − p). Nhãn: mục tiêu cố định 3R.

## Mô hình có xếp hạng được plan không (AUC, ngoài mẫu)

| Mô hình | Kỳ | MUA | BÁN |
|---|---|---|---|
| lgbm | OOS 12/2024–03/2025 (cuối train) | 0.574 | 0.526 |
| lgbm | Validate 04–12/2025 | 0.540 | 0.529 |
| knn | OOS 12/2024–03/2025 (cuối train) | 0.519 | 0.511 |
| knn | Validate 04–12/2025 | 0.528 | 0.501 |
| C2 time | OOS 12/2024–03/2025 (cuối train) | 0.539 | 0.514 |
| C2 time | Validate 04–12/2025 | 0.549 | 0.515 |
| C3 no path | OOS 12/2024–03/2025 (cuối train) | 0.575 | 0.538 |
| C3 no path | Validate 04–12/2025 | 0.541 | 0.525 |
| C4 shuffled | OOS 12/2024–03/2025 (cuối train) | 0.572 | 0.529 |
| C4 shuffled | Validate 04–12/2025 | 0.539 | 0.522 |

AUC 0,5 = không hơn đoán mò. Lưu ý: RR là một đặc trưng, nên mô hình nào cũng học được "mục tiêu gần thì dễ chạm"; điều cần xem là lợi nhuận (bảng dưới), không phải AUC.

## Validate: R thực tế theo nhóm 10% EV dự báo (lgbm)

| Chiều | Nhóm EV (thấp → cao) | Plan | p dự báo | Thắng thực tế | R/plan |
|---|---|---|---|---|---|
| MUA | 1 | 517 | 0.09 | 14% | -0.302 |
| MUA | 2 | 517 | 0.14 | 16% | -0.298 |
| MUA | 3 | 516 | 0.16 | 21% | -0.137 |
| MUA | 4 | 517 | 0.18 | 20% | -0.201 |
| MUA | 5 | 517 | 0.19 | 18% | -0.271 |
| MUA | 6 | 516 | 0.21 | 19% | -0.223 |
| MUA | 7 | 517 | 0.23 | 23% | -0.077 |
| MUA | 8 | 516 | 0.25 | 22% | -0.105 |
| MUA | 9 | 517 | 0.28 | 18% | -0.244 |
| MUA | 10 | 517 | 0.35 | 25% | +0.010 |
| BÁN | 1 | 463 | 0.09 | 12% | -0.456 |
| BÁN | 2 | 462 | 0.13 | 19% | -0.244 |
| BÁN | 3 | 462 | 0.14 | 18% | -0.284 |
| BÁN | 4 | 462 | 0.16 | 16% | -0.343 |
| BÁN | 5 | 463 | 0.17 | 19% | -0.236 |
| BÁN | 6 | 462 | 0.18 | 20% | -0.204 |
| BÁN | 7 | 462 | 0.19 | 21% | -0.123 |
| BÁN | 8 | 462 | 0.21 | 21% | -0.148 |
| BÁN | 9 | 462 | 0.23 | 21% | -0.131 |
| BÁN | 10 | 463 | 0.28 | 16% | -0.355 |

## Lệnh không chồng (mỗi chiều một lệnh mỗi lúc)

| Mô hình | Quy tắc | Kỳ | Chiều | Lệnh | Lệnh/tháng | Thắng | R/lệnh | Cận dưới 90% | Tổng / DD |
|---|---|---|---|---|---|---|---|---|---|
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | MUA | 570 | 142 | 22% | -0.158 | -0.232 | -90.0R / DD 107.0R |
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | BÁN | 729 | 182 | 21% | -0.193 | -0.269 | -140.8R / DD 154.0R |
| (vào mọi plan) | — | Validate 04–12/2025 | MUA | 1006 | 144 | 21% | -0.203 | -0.268 | -203.9R / DD 219.4R |
| (vào mọi plan) | — | Validate 04–12/2025 | BÁN | 1222 | 175 | 19% | -0.259 | -0.321 | -316.0R / DD 322.2R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 369 | 92 | 22% | -0.128 | -0.227 | -47.3R / DD 48.3R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 194 | 48 | 22% | -0.144 | -0.301 | -27.9R / DD 44.0R |
| lgbm | EV > 0 | Validate 04–12/2025 | MUA | 554 | 79 | 22% | -0.121 | -0.201 | -67.2R / DD 90.6R |
| lgbm | EV > 0 | Validate 04–12/2025 | BÁN | 246 | 35 | 18% | -0.301 | -0.417 | -74.1R / DD 83.1R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 102 | 26 | 20% | -0.216 | -0.358 | -22.0R / DD 22.0R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 48 | 12 | 17% | -0.333 | -0.600 | -16.0R / DD 24.0R |
| lgbm | top 10% | Validate 04–12/2025 | MUA | 242 | 35 | 26% | +0.008 | -0.117 | +1.8R / DD 29.0R |
| lgbm | top 10% | Validate 04–12/2025 | BÁN | 81 | 12 | 17% | -0.360 | -0.526 | -29.2R / DD 30.8R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 193 | 48 | 23% | -0.094 | -0.224 | -18.1R / DD 27.7R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 51 | 13 | 12% | -0.529 | -0.745 | -27.0R / DD 30.0R |
| knn | EV > 0 | Validate 04–12/2025 | MUA | 282 | 40 | 24% | -0.061 | -0.184 | -17.1R / DD 42.0R |
| knn | EV > 0 | Validate 04–12/2025 | BÁN | 91 | 13 | 20% | -0.233 | -0.440 | -21.2R / DD 31.8R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 152 | 38 | 22% | -0.135 | -0.265 | -20.5R / DD 23.7R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 39 | 10 | 10% | -0.590 | -0.805 | -23.0R / DD 22.0R |
| knn | top 10% | Validate 04–12/2025 | MUA | 322 | 46 | 23% | -0.092 | -0.202 | -29.6R / DD 61.1R |
| knn | top 10% | Validate 04–12/2025 | BÁN | 91 | 13 | 20% | -0.233 | -0.440 | -21.2R / DD 31.8R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 295 | 74 | 23% | -0.112 | -0.252 | -32.9R / DD 71.0R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 106 | 26 | 19% | -0.313 | -0.477 | -33.2R / DD 36.2R |
| C2 time | EV > 0 | Validate 04–12/2025 | MUA | 342 | 49 | 25% | -0.054 | -0.160 | -18.3R / DD 53.1R |
| C2 time | EV > 0 | Validate 04–12/2025 | BÁN | 109 | 16 | 17% | -0.388 | -0.549 | -42.3R / DD 46.0R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 124 | 31 | 19% | -0.240 | -0.422 | -29.8R / DD 37.8R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 47 | 12 | 21% | -0.266 | -0.515 | -12.5R / DD 18.8R |
| C2 time | top 10% | Validate 04–12/2025 | MUA | 252 | 36 | 26% | -0.008 | -0.145 | -2.0R / DD 42.0R |
| C2 time | top 10% | Validate 04–12/2025 | BÁN | 55 | 8 | 20% | -0.252 | -0.531 | -13.9R / DD 15.9R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 345 | 86 | 23% | -0.109 | -0.215 | -37.5R / DD 47.5R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 223 | 56 | 22% | -0.148 | -0.286 | -32.9R / DD 48.9R |
| C3 no path | EV > 0 | Validate 04–12/2025 | MUA | 544 | 78 | 22% | -0.123 | -0.212 | -66.8R / DD 93.0R |
| C3 no path | EV > 0 | Validate 04–12/2025 | BÁN | 235 | 34 | 20% | -0.207 | -0.352 | -48.6R / DD 47.6R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 91 | 23 | 19% | -0.253 | -0.435 | -23.0R / DD 26.0R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 54 | 14 | 22% | -0.111 | -0.446 | -6.0R / DD 22.0R |
| C3 no path | top 10% | Validate 04–12/2025 | MUA | 255 | 36 | 26% | +0.037 | -0.082 | +9.5R / DD 32.0R |
| C3 no path | top 10% | Validate 04–12/2025 | BÁN | 68 | 10 | 16% | -0.373 | -0.556 | -25.4R / DD 26.0R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 391 | 98 | 23% | -0.085 | -0.182 | -33.4R / DD 50.4R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 190 | 48 | 23% | -0.089 | -0.257 | -16.9R / DD 41.0R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | MUA | 568 | 81 | 23% | -0.098 | -0.186 | -55.7R / DD 82.4R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | BÁN | 238 | 34 | 20% | -0.222 | -0.354 | -52.9R / DD 55.5R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 101 | 25 | 22% | -0.129 | -0.308 | -13.0R / DD 21.0R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 49 | 12 | 14% | -0.429 | -0.652 | -21.0R / DD 25.0R |
| C4 shuffled | top 10% | Validate 04–12/2025 | MUA | 271 | 39 | 27% | +0.076 | -0.049 | +20.6R / DD 24.0R |
| C4 shuffled | top 10% | Validate 04–12/2025 | BÁN | 78 | 11 | 18% | -0.300 | -0.498 | -23.4R / DD 24.0R |

## Đối chứng C1: chọn ngẫu nhiên (theo plan, không chồng lệnh)

- MUA: lgbm top 10% trên validate R/plan -0.010; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.185, 95% ≤ -0.073; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.005**
- BÁN: lgbm top 10% trên validate R/plan -0.353; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.265, 95% ≤ -0.021; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.740**

## Học tiếp theo thời gian (lgbm, từng tháng ngoài mẫu)

| Tháng | Plan học | Plan dự báo | AUC | R/plan top 10% EV trong tháng |
|---|---|---|---|---|
| 2024-12 | 7675 | 1486 | 0.558 | -0.081 |
| 2025-01 | 9163 | 1654 | 0.555 | -0.099 |
| 2025-02 | 10818 | 1413 | 0.526 | -0.211 |
| 2025-03 | 12229 | 1555 | 0.570 | -0.217 |
| 2025-04 | 13786 | 1581 | 0.509 | -0.138 |
| 2025-05 | 15364 | 1646 | 0.582 | +0.072 |
| 2025-06 | 17014 | 1543 | 0.564 | +0.025 |
| 2025-07 | 18557 | 1647 | 0.497 | -0.459 |
| 2025-08 | 20206 | 1463 | 0.545 | -0.112 |
| 2025-09 | 21668 | 1545 | 0.529 | -0.146 |
| 2025-10 | 23208 | 365 | 0.555 | -0.351 |

## Kiểm tra cuốn chiếu

| Tháng dự báo | Plan học | Plan dự báo | Lệnh học thoát muộn nhất |
|---|---|---|---|
| 2024-12 | 7675 | 1486 | 2024-11-29 21:55:00 |
| 2025-01 | 9163 | 1654 | 2024-12-31 23:50:00 |
| 2025-02 | 10818 | 1413 | 2025-01-31 23:15:00 |
| 2025-03 | 12229 | 1555 | 2025-02-28 22:55:00 |
| 2025-04 | 13786 | 1581 | 2025-03-31 22:50:00 |
| 2025-05 | 15364 | 1646 | 2025-04-30 23:20:00 |
| 2025-06 | 17014 | 1543 | 2025-05-30 23:30:00 |
| 2025-07 | 18557 | 1647 | 2025-06-30 23:15:00 |
| 2025-08 | 20206 | 1463 | 2025-07-31 23:50:00 |
| 2025-09 | 21668 | 1545 | 2025-08-29 23:50:00 |
| 2025-10 | 23208 | 365 | 2025-09-30 23:05:00 |
