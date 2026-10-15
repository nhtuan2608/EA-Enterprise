# G108 bước 3: plan học cuốn chiếu (kNN, LightGBM) và đối chứng

Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g108-m30-path-plans.md; bước 1–2: reports/2026-10-13-g108-patterns.md. Mỗi tháng từ 12/2024, mô hình học từ các plan đã **thoát lệnh trước ngày đầu tháng** (có assert trong code) rồi dự báo plan của tháng đó. **Kỳ test 2026 vẫn niêm phong.** Script: research/long/g108_features.py, g108_models.py.

Plan đã gộp (một plan một lần): 22930; có dự báo ngoài mẫu: 15609. p = xác suất chạm mục tiêu trước mức sai; EV = p × RR − (1 − p). Nhãn: mục tiêu cố định 3R.

## Mô hình có xếp hạng được plan không (AUC, ngoài mẫu)

| Mô hình | Kỳ | MUA | BÁN |
|---|---|---|---|
| lgbm | OOS 12/2024–03/2025 (cuối train) | 0.506 | 0.517 |
| lgbm | Validate 04–12/2025 | 0.500 | 0.560 |
| knn | OOS 12/2024–03/2025 (cuối train) | 0.503 | 0.494 |
| knn | Validate 04–12/2025 | 0.512 | 0.522 |
| C2 time | OOS 12/2024–03/2025 (cuối train) | 0.509 | 0.536 |
| C2 time | Validate 04–12/2025 | 0.487 | 0.534 |
| C3 no path | OOS 12/2024–03/2025 (cuối train) | 0.504 | 0.515 |
| C3 no path | Validate 04–12/2025 | 0.492 | 0.568 |
| C4 shuffled | OOS 12/2024–03/2025 (cuối train) | 0.491 | 0.507 |
| C4 shuffled | Validate 04–12/2025 | 0.482 | 0.551 |

AUC 0,5 = không hơn đoán mò. Lưu ý: RR là một đặc trưng, nên mô hình nào cũng học được "mục tiêu gần thì dễ chạm"; điều cần xem là lợi nhuận (bảng dưới), không phải AUC.

## Validate: R thực tế theo nhóm 10% EV dự báo (lgbm)

| Chiều | Nhóm EV (thấp → cao) | Plan | p dự báo | Thắng thực tế | R/plan |
|---|---|---|---|---|---|
| MUA | 1 | 502 | 0.12 | 26% | +0.082 |
| MUA | 2 | 502 | 0.15 | 19% | -0.230 |
| MUA | 3 | 502 | 0.17 | 20% | -0.177 |
| MUA | 4 | 502 | 0.18 | 18% | -0.265 |
| MUA | 5 | 502 | 0.19 | 20% | -0.169 |
| MUA | 6 | 502 | 0.21 | 22% | -0.099 |
| MUA | 7 | 502 | 0.22 | 18% | -0.263 |
| MUA | 8 | 502 | 0.24 | 21% | -0.165 |
| MUA | 9 | 502 | 0.27 | 24% | -0.001 |
| MUA | 10 | 502 | 0.33 | 21% | -0.155 |
| BÁN | 1 | 450 | 0.10 | 12% | -0.457 |
| BÁN | 2 | 450 | 0.13 | 14% | -0.397 |
| BÁN | 3 | 449 | 0.14 | 18% | -0.271 |
| BÁN | 4 | 450 | 0.16 | 20% | -0.207 |
| BÁN | 5 | 449 | 0.17 | 19% | -0.208 |
| BÁN | 6 | 450 | 0.18 | 19% | -0.218 |
| BÁN | 7 | 449 | 0.19 | 17% | -0.305 |
| BÁN | 8 | 450 | 0.21 | 23% | -0.071 |
| BÁN | 9 | 449 | 0.23 | 22% | -0.100 |
| BÁN | 10 | 450 | 0.27 | 24% | -0.043 |

## Lệnh không chồng (mỗi chiều một lệnh mỗi lúc)

| Mô hình | Quy tắc | Kỳ | Chiều | Lệnh | Lệnh/tháng | Thắng | R/lệnh | Cận dưới 90% | Tổng / DD |
|---|---|---|---|---|---|---|---|---|---|
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | MUA | 614 | 154 | 22% | -0.142 | -0.221 | -87.1R / DD 95.4R |
| (vào mọi plan) | — | OOS 12/2024–03/2025 (cuối train) | BÁN | 696 | 174 | 22% | -0.144 | -0.218 | -100.3R / DD 129.2R |
| (vào mọi plan) | — | Validate 04–12/2025 | MUA | 956 | 137 | 22% | -0.130 | -0.196 | -124.3R / DD 156.3R |
| (vào mọi plan) | — | Validate 04–12/2025 | BÁN | 1261 | 180 | 20% | -0.224 | -0.283 | -282.3R / DD 281.3R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 253 | 63 | 21% | -0.173 | -0.291 | -43.9R / DD 51.9R |
| lgbm | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 256 | 64 | 22% | -0.140 | -0.268 | -35.9R / DD 50.1R |
| lgbm | EV > 0 | Validate 04–12/2025 | MUA | 475 | 68 | 22% | -0.130 | -0.214 | -61.6R / DD 75.7R |
| lgbm | EV > 0 | Validate 04–12/2025 | BÁN | 243 | 35 | 22% | -0.116 | -0.219 | -28.2R / DD 32.2R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 83 | 21 | 24% | -0.036 | -0.334 | -3.0R / DD 10.0R |
| lgbm | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 52 | 13 | 21% | -0.154 | -0.410 | -8.0R / DD 20.0R |
| lgbm | top 10% | Validate 04–12/2025 | MUA | 315 | 45 | 23% | -0.086 | -0.205 | -27.0R / DD 43.8R |
| lgbm | top 10% | Validate 04–12/2025 | BÁN | 105 | 15 | 19% | -0.256 | -0.427 | -26.9R / DD 27.9R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 121 | 30 | 21% | -0.154 | -0.317 | -18.7R / DD 32.0R |
| knn | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 72 | 18 | 22% | -0.140 | -0.374 | -10.1R / DD 16.1R |
| knn | EV > 0 | Validate 04–12/2025 | MUA | 342 | 49 | 23% | -0.152 | -0.256 | -52.1R / DD 67.4R |
| knn | EV > 0 | Validate 04–12/2025 | BÁN | 86 | 12 | 22% | -0.116 | -0.341 | -10.0R / DD 19.0R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 171 | 43 | 20% | -0.181 | -0.334 | -31.0R / DD 40.0R |
| knn | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 66 | 16 | 17% | -0.365 | -0.582 | -24.1R / DD 33.1R |
| knn | top 10% | Validate 04–12/2025 | MUA | 429 | 61 | 26% | -0.048 | -0.145 | -20.5R / DD 47.8R |
| knn | top 10% | Validate 04–12/2025 | BÁN | 134 | 19 | 19% | -0.248 | -0.429 | -33.3R / DD 38.3R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 139 | 35 | 20% | -0.214 | -0.365 | -29.7R / DD 32.7R |
| C2 time | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 170 | 42 | 21% | -0.181 | -0.322 | -30.7R / DD 31.7R |
| C2 time | EV > 0 | Validate 04–12/2025 | MUA | 235 | 34 | 27% | +0.032 | -0.103 | +7.6R / DD 16.8R |
| C2 time | EV > 0 | Validate 04–12/2025 | BÁN | 187 | 27 | 18% | -0.292 | -0.437 | -54.6R / DD 58.6R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 88 | 22 | 15% | -0.409 | -0.577 | -36.0R / DD 35.0R |
| C2 time | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 96 | 24 | 23% | -0.133 | -0.318 | -12.7R / DD 21.7R |
| C2 time | top 10% | Validate 04–12/2025 | MUA | 231 | 33 | 26% | +0.016 | -0.124 | +3.6R / DD 18.8R |
| C2 time | top 10% | Validate 04–12/2025 | BÁN | 194 | 28 | 19% | -0.276 | -0.411 | -53.6R / DD 57.6R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 262 | 66 | 19% | -0.224 | -0.336 | -58.8R / DD 60.8R |
| C3 no path | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 247 | 62 | 25% | -0.017 | -0.138 | -4.2R / DD 27.0R |
| C3 no path | EV > 0 | Validate 04–12/2025 | MUA | 426 | 61 | 24% | -0.083 | -0.183 | -35.4R / DD 52.3R |
| C3 no path | EV > 0 | Validate 04–12/2025 | BÁN | 249 | 36 | 19% | -0.238 | -0.334 | -59.3R / DD 62.3R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 69 | 17 | 22% | -0.135 | -0.385 | -9.3R / DD 16.0R |
| C3 no path | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 46 | 12 | 28% | +0.130 | -0.172 | +6.0R / DD 7.0R |
| C3 no path | top 10% | Validate 04–12/2025 | MUA | 237 | 34 | 24% | -0.051 | -0.185 | -12.0R / DD 34.1R |
| C3 no path | top 10% | Validate 04–12/2025 | BÁN | 92 | 13 | 21% | -0.174 | -0.385 | -16.0R / DD 20.0R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | MUA | 282 | 70 | 21% | -0.197 | -0.315 | -55.5R / DD 61.5R |
| C4 shuffled | EV > 0 | OOS 12/2024–03/2025 (cuối train) | BÁN | 277 | 69 | 20% | -0.213 | -0.313 | -59.1R / DD 72.1R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | MUA | 543 | 78 | 21% | -0.201 | -0.284 | -108.9R / DD 117.4R |
| C4 shuffled | EV > 0 | Validate 04–12/2025 | BÁN | 306 | 44 | 21% | -0.191 | -0.282 | -58.5R / DD 71.5R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | MUA | 87 | 22 | 20% | -0.218 | -0.422 | -19.0R / DD 24.0R |
| C4 shuffled | top 10% | OOS 12/2024–03/2025 (cuối train) | BÁN | 62 | 16 | 16% | -0.355 | -0.564 | -22.0R / DD 29.0R |
| C4 shuffled | top 10% | Validate 04–12/2025 | MUA | 347 | 50 | 23% | -0.117 | -0.223 | -40.7R / DD 60.4R |
| C4 shuffled | top 10% | Validate 04–12/2025 | BÁN | 125 | 18 | 22% | -0.157 | -0.328 | -19.6R / DD 23.0R |

## Đối chứng C1: chọn ngẫu nhiên (theo plan, không chồng lệnh)

- MUA: lgbm top 10% trên validate R/plan -0.118; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.156, 95% ≤ -0.069; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.270**
- BÁN: lgbm top 10% trên validate R/plan -0.184; chọn ngẫu nhiên cùng số plan mỗi tháng: trung bình -0.203, 95% ≤ +0.031; tỉ lệ lần ngẫu nhiên ≥ mô hình: **0.450**

## Học tiếp theo thời gian (lgbm, từng tháng ngoài mẫu)

| Tháng | Plan học | Plan dự báo | AUC | R/plan top 10% EV trong tháng |
|---|---|---|---|---|
| 2024-12 | 7315 | 1515 | 0.521 | -0.210 |
| 2025-01 | 8829 | 1610 | 0.493 | -0.155 |
| 2025-02 | 10441 | 1418 | 0.478 | -0.343 |
| 2025-03 | 11856 | 1550 | 0.551 | +0.149 |
| 2025-04 | 13403 | 1583 | 0.509 | +0.183 |
| 2025-05 | 14993 | 1670 | 0.518 | -0.333 |
| 2025-06 | 16658 | 1514 | 0.546 | +0.024 |
| 2025-07 | 18174 | 1599 | 0.557 | -0.200 |
| 2025-08 | 19770 | 1490 | 0.513 | -0.152 |
| 2025-09 | 21266 | 1524 | 0.534 | -0.089 |
| 2025-10 | 22788 | 136 | 0.500 | -0.429 |

## Kiểm tra cuốn chiếu

| Tháng dự báo | Plan học | Plan dự báo | Lệnh học thoát muộn nhất |
|---|---|---|---|
| 2024-12 | 7315 | 1515 | 2024-11-29 23:55:00 |
| 2025-01 | 8829 | 1610 | 2024-12-31 23:50:00 |
| 2025-02 | 10441 | 1418 | 2025-01-31 23:15:00 |
| 2025-03 | 11856 | 1550 | 2025-02-28 23:00:00 |
| 2025-04 | 13403 | 1583 | 2025-03-31 23:10:00 |
| 2025-05 | 14993 | 1670 | 2025-04-30 23:10:00 |
| 2025-06 | 16658 | 1514 | 2025-05-30 23:30:00 |
| 2025-07 | 18174 | 1599 | 2025-06-30 23:55:00 |
| 2025-08 | 19770 | 1490 | 2025-07-31 23:00:00 |
| 2025-09 | 21266 | 1524 | 2025-08-29 23:55:00 |
| 2025-10 | 22788 | 136 | 2025-09-30 23:55:00 |
