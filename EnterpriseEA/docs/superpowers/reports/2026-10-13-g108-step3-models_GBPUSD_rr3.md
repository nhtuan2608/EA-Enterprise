# G108 bước 3: plan học cuốn chiếu (kNN, LightGBM) và đối chứng

Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g108-m30-path-plans.md; bước 1–2: reports/2026-10-13-g108-patterns.md. Mỗi tháng từ 12/2024, mô hình học từ các plan đã **thoát lệnh trước ngày đầu tháng** (có assert trong code) rồi dự báo plan của tháng đó. **Kỳ test 2026 vẫn niêm phong.** Script: research/long/g108_features.py, g108_models.py.

Plan đã gộp (một plan một lần): 23951; có dự báo ngoài mẫu: 16159. p = xác suất chạm mục tiêu trước mức sai; EV = p × RR − (1 − p). Nhãn: mục tiêu cố định 3R.

## Mô hình có xếp hạng được plan không (AUC, ngoài mẫu)

| Mô hình | Kỳ | MUA | BÁN |
|---|---|---|---|
| lgbm | OOS 12/2024–03/2025 (cuối train) | 0.571 | 0.509 |
| lgbm | Validate 04–12/2025 | 0.534 | 0.520 |
| knn | OOS 12/2024–03/2025 (cuối train) | 0.517 | 0.518 |
| knn | Validate 04–12/2025 | 0.514 | 0.517 |
| C2 time | OOS 12/2024–03/2025 (cuối train) | 0.523 | 0.501 |
| C2 time | Validate 04–12/2025 | 0.540 | 0.519 |
| C3 no path | OOS 12/2024–03/2025 (cuối train) | 0.572 | 0.523 |
| C3 no path | Validate 04–12/2025 | 0.529 | 0.528 |
| C4 shuffled | OOS 12/2024–03/2025 (cuối train) | 0.570 | 0.517 |
| C4 shuffled | Validate 04–12/2025 | 0.513 | 0.515 |

AUC 0,5 = không hơn đoán mò. Lưu ý: RR là một đặc trưng, nên mô hình nào cũng học được "mục tiêu gần thì dễ chạm"; điều cần xem là lợi nhuận (bảng dưới), không phải AUC.

## Validate: R thực tế theo nhóm 10% EV dự báo (lgbm)

| Chiều | Nhóm EV (thấp → cao) | Plan | p dự báo | Thắng thực tế | R/plan |
|---|---|---|---|---|---|
| MUA | 1 | 526 | 0.11 | 17% | -0.230 |
| MUA | 2 | 525 | 0.14 | 18% | -0.245 |
| MUA | 3 | 525 | 0.16 | 21% | -0.135 |
| MUA | 4 | 525 | 0.18 | 18% | -0.250 |
| MUA | 5 | 525 | 0.19 | 17% | -0.286 |
| MUA | 6 | 525 | 0.21 | 17% | -0.302 |
| MUA | 7 | 525 | 0.22 | 24% | -0.018 |
| MUA | 8 | 525 | 0.25 | 20% | -0.174 |
| MUA | 9 | 525 | 0.27 | 20% | -0.197 |
| MUA | 10 | 525 | 0.34 | 26% | +0.063 |
| BÁN | 1 | 469 | 0.10 | 15% | -0.358 |
| BÁN | 2 | 469 | 0.13 | 16% | -0.348 |
| BÁN | 3 | 469 | 0.14 | 20% | -0.194 |
| BÁN | 4 | 468 | 0.15 | 16% | -0.329 |
| BÁN | 5 | 469 | 0.16 | 23% | -0.074 |
| BÁN | 6 | 469 | 0.18 | 18% | -0.280 |
| BÁN | 7 | 468 | 0.19 | 17% | -0.288 |
| BÁN | 8 | 469 | 0.20 | 20% | -0.190 |
| BÁN | 9 | 469 | 0.22 | 19% | -0.225 |
| BÁN | 10 | 469 | 0.27 | 19% | -0.236 |

## Lệnh không chồng (mỗi chiều một lệnh mỗi lúc)

| Mô hình | Quy tắc | Kỳ | Chiều | Lệnh | Lệnh/tháng | Thắng | R/lệnh | Cận dưới 90% | Tổng / DD |
|---|---|---|---|---|---|---|---|---|---|
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | MUA | 571 | 143 | 22% | -0.159 | -0.231 | -91.0R / DD 107.0R |
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | BÁN | 729 | 182 | 22% | -0.188 | -0.263 | -136.8R / DD 150.0R |
| (vào mọi plan) | — | Validate 04–12/2025 | MUA | 995 | 142 | 21% | -0.208 | -0.267 | -207.0R / DD 223.4R |
| (vào mọi plan) | — | Validate 04–12/2025 | BÁN | 1219 | 174 | 19% | -0.255 | -0.315 | -311.3R / DD 317.5R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 337 | 84 | 23% | -0.083 | -0.200 | -27.9R / DD 47.2R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 236 | 59 | 21% | -0.171 | -0.311 | -40.4R / DD 57.9R |
| lgbm | EV > 0 | Validate 04–12/2025 | MUA | 544 | 78 | 20% | -0.190 | -0.273 | -103.4R / DD 109.4R |
| lgbm | EV > 0 | Validate 04–12/2025 | BÁN | 208 | 30 | 19% | -0.250 | -0.381 | -52.0R / DD 55.0R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 90 | 22 | 22% | -0.111 | -0.292 | -10.0R / DD 19.0R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 53 | 13 | 21% | -0.170 | -0.462 | -9.0R / DD 24.0R |
| lgbm | top 10% | Validate 04–12/2025 | MUA | 277 | 40 | 24% | -0.036 | -0.156 | -9.9R / DD 32.1R |
| lgbm | top 10% | Validate 04–12/2025 | BÁN | 71 | 10 | 21% | -0.155 | -0.394 | -11.0R / DD 20.0R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 237 | 59 | 23% | -0.110 | -0.230 | -26.2R / DD 39.9R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 66 | 16 | 15% | -0.394 | -0.667 | -26.0R / DD 32.0R |
| knn | EV > 0 | Validate 04–12/2025 | MUA | 302 | 43 | 22% | -0.154 | -0.253 | -46.5R / DD 58.2R |
| knn | EV > 0 | Validate 04–12/2025 | BÁN | 91 | 13 | 15% | -0.415 | -0.600 | -37.8R / DD 46.8R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 145 | 36 | 25% | -0.069 | -0.240 | -10.0R / DD 20.3R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 33 | 8 | 9% | -0.636 | -1.000 | -21.0R / DD 24.0R |
| knn | top 10% | Validate 04–12/2025 | MUA | 308 | 44 | 22% | -0.140 | -0.245 | -43.0R / DD 54.7R |
| knn | top 10% | Validate 04–12/2025 | BÁN | 93 | 13 | 13% | -0.514 | -0.685 | -47.8R / DD 46.8R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 283 | 71 | 22% | -0.127 | -0.258 | -35.8R / DD 62.8R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 161 | 40 | 20% | -0.250 | -0.389 | -40.2R / DD 41.2R |
| C2 time | EV > 0 | Validate 04–12/2025 | MUA | 355 | 51 | 24% | -0.060 | -0.181 | -21.2R / DD 46.2R |
| C2 time | EV > 0 | Validate 04–12/2025 | BÁN | 100 | 14 | 20% | -0.214 | -0.391 | -21.4R / DD 27.7R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 81 | 20 | 16% | -0.388 | -0.571 | -31.4R / DD 31.4R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 59 | 15 | 19% | -0.299 | -0.509 | -17.7R / DD 25.0R |
| C2 time | top 10% | Validate 04–12/2025 | MUA | 299 | 43 | 23% | -0.071 | -0.189 | -21.2R / DD 45.2R |
| C2 time | top 10% | Validate 04–12/2025 | BÁN | 67 | 10 | 18% | -0.320 | -0.567 | -21.5R / DD 31.0R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 344 | 86 | 24% | -0.065 | -0.175 | -22.4R / DD 50.0R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 232 | 58 | 20% | -0.202 | -0.353 | -46.9R / DD 56.9R |
| C3 no path | EV > 0 | Validate 04–12/2025 | MUA | 517 | 74 | 21% | -0.153 | -0.243 | -79.0R / DD 85.4R |
| C3 no path | EV > 0 | Validate 04–12/2025 | BÁN | 219 | 31 | 18% | -0.276 | -0.410 | -60.5R / DD 59.5R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 73 | 18 | 21% | -0.203 | -0.412 | -14.9R / DD 23.9R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 62 | 16 | 15% | -0.419 | -0.667 | -26.0R / DD 32.0R |
| C3 no path | top 10% | Validate 04–12/2025 | MUA | 255 | 36 | 26% | +0.035 | -0.096 | +8.8R / DD 27.0R |
| C3 no path | top 10% | Validate 04–12/2025 | BÁN | 63 | 9 | 16% | -0.365 | -0.550 | -23.0R / DD 24.0R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 367 | 92 | 23% | -0.073 | -0.173 | -27.0R / DD 40.0R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 221 | 55 | 19% | -0.285 | -0.422 | -62.9R / DD 68.3R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | MUA | 511 | 73 | 21% | -0.153 | -0.239 | -78.1R / DD 90.1R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | BÁN | 215 | 31 | 20% | -0.228 | -0.368 | -49.1R / DD 53.1R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 93 | 23 | 24% | -0.054 | -0.229 | -5.0R / DD 15.0R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 52 | 13 | 21% | -0.154 | -0.462 | -8.0R / DD 17.0R |
| C4 shuffled | top 10% | Validate 04–12/2025 | MUA | 263 | 38 | 22% | -0.108 | -0.222 | -28.3R / DD 42.1R |
| C4 shuffled | top 10% | Validate 04–12/2025 | BÁN | 75 | 11 | 20% | -0.228 | -0.426 | -17.1R / DD 21.1R |

## Đối chứng C1: chọn ngẫu nhiên (theo plan, không chồng lệnh)

- MUA: lgbm top 10% trên validate R/plan +0.009; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.185, 95% ≤ -0.089; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.000**
- BÁN: lgbm top 10% trên validate R/plan -0.172; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.249, 95% ≤ +0.026; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.285**

## Học tiếp theo thời gian (lgbm, từng tháng ngoài mẫu)

| Tháng | Plan học | Plan dự báo | AUC | R/plan top 10% EV trong tháng |
|---|---|---|---|---|
| 2024-12 | 7782 | 1512 | 0.540 | +0.032 |
| 2025-01 | 9296 | 1679 | 0.537 | -0.158 |
| 2025-02 | 10977 | 1435 | 0.534 | +0.000 |
| 2025-03 | 12409 | 1594 | 0.563 | -0.037 |
| 2025-04 | 14003 | 1607 | 0.471 | -0.119 |
| 2025-05 | 15602 | 1658 | 0.573 | +0.151 |
| 2025-06 | 17271 | 1584 | 0.571 | +0.201 |
| 2025-07 | 18850 | 1677 | 0.509 | -0.190 |
| 2025-08 | 20531 | 1494 | 0.553 | +0.173 |
| 2025-09 | 22020 | 1553 | 0.497 | -0.379 |
| 2025-10 | 23575 | 366 | 0.576 | -0.351 |

## Kiểm tra cuốn chiếu

| Tháng dự báo | Plan học | Plan dự báo | Lệnh học thoát muộn nhất |
|---|---|---|---|
| 2024-12 | 7782 | 1512 | 2024-11-29 19:55:00 |
| 2025-01 | 9296 | 1679 | 2024-12-31 21:50:00 |
| 2025-02 | 10977 | 1435 | 2025-01-31 22:00:00 |
| 2025-03 | 12409 | 1594 | 2025-02-28 20:55:00 |
| 2025-04 | 14003 | 1607 | 2025-03-31 23:25:00 |
| 2025-05 | 15602 | 1658 | 2025-04-30 23:20:00 |
| 2025-06 | 17271 | 1584 | 2025-05-30 20:30:00 |
| 2025-07 | 18850 | 1677 | 2025-06-30 23:30:00 |
| 2025-08 | 20531 | 1494 | 2025-07-31 23:45:00 |
| 2025-09 | 22020 | 1553 | 2025-08-31 23:55:00 |
| 2025-10 | 23575 | 366 | 2025-09-30 22:05:00 |
