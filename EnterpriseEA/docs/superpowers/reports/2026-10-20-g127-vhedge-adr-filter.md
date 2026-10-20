# G127: bộ lọc ADR cho VHedge G119 — kết quả

Kế hoạch: `plans/2026-10-20-g127-vhedge-adr-filter.md`. Lệnh VHedge G119 (bộ sinh `g120_combo.vhedge`, R mỗi nhóm sau chi phí). ADR đã dùng = (cao − thấp từ 00:00 UTC đến nến M30 đã đóng trước lúc vào) ÷ ADR 10 ngày UTC. Bộ lọc cố định: giữ khi < 0.8.

Giai đoạn phát hiện: 230 lệnh (05/2024–12/2025). 2026: 83 lệnh.

## Bước 1 — giai đoạn phát hiện (chỉ mô tả, không đổi bộ lọc)

### 1a. Đường ngưỡng

| Ngưỡng | Giữ: lệnh / R/lệnh / tổng R | Bỏ: lệnh / R/lệnh / tổng R | Chênh (giữ − bỏ) |
|---|---|---|---|
| 0.6 | 148 / +0.611 / tổng +90.5 | 82 / +0.326 / tổng +26.7 | +0.286 |
| 0.7 | 188 / +0.525 / tổng +98.7 | 42 / +0.440 / tổng +18.5 | +0.086 |
| 0.8 | 200 / +0.600 / tổng +120.1 | 30 / -0.095 / tổng -2.8 | +0.695 |
| 0.9 | 214 / +0.525 / tổng +112.4 | 16 / +0.300 / tổng +4.8 | +0.225 |
| 1.0 | 221 / +0.521 / tổng +115.2 | 9 / +0.222 / tổng +2.0 | +0.300 |

### 1b. Trong cùng nhóm giờ UTC lúc vào (ngưỡng 0,8)

| Giờ UTC | Giữ | Bỏ | Chênh |
|---|---|---|---|
| 00–07 | 56 / +0.929 / tổng +52.0 | 2 / +2.211 / tổng +4.4 | -1.282 |
| 07–13 | 70 / +0.308 / tổng +21.6 | 7 / -0.588 / tổng -4.1 | +0.897 |
| 13–21 | 70 / +0.593 / tổng +41.5 | 21 / -0.150 / tổng -3.1 | +0.743 |
| 21–24 | 4 / +1.249 / tổng +5.0 | 0 / +0.000 / tổng +0.0 | +nan |

Chênh trung bình có trọng số (theo min(giữ, bỏ) mỗi nhóm giờ): **+0.644**.

### 1c. Theo năm (ngưỡng 0,8)

| Năm | Giữ | Bỏ |
|---|---|---|
| 2024 | 76 / +0.727 / tổng +55.3 | 9 / +0.327 / tổng +2.9 |
| 2025 | 124 / +0.523 / tổng +64.8 | 21 / -0.276 / tổng -5.8 |

### 1d. Ngày server thay cho ngày UTC (ngưỡng 0,8)

Giữ 204 / +0.618 / tổng +126.0; bỏ 26 / -0.337 / tổng -8.8. Hai cách tính cho cùng quyết định ở 93% số lệnh.

## Bước 2 — test 2026 (mở một lần)

| Nhóm | Lệnh / R/lệnh / tổng R |
|---|---|
| Giữ (ADR đã dùng < 0,8) | 80 / +0.567 / tổng +45.4 |
| Bỏ (≥ 0,8) | 3 / +0.360 / tổng +1.1 |
| Tất cả | 83 / +0.560 / tổng +46.5 |

1. R/lệnh giữ > bỏ: **đạt** (+0.567 so với +0.360)
2. Tổng R nhóm bỏ ≤ 0: **không** (+1.1)
3. ≥ 10 lệnh bị bỏ: **không** (3)
- Hoán vị nhãn (một phía): p = 0.522

- Không lọc: 83 lệnh, +94.7% trong 2026 (+137.1%/năm), DD 6.7% (1,5%/nhóm, lãi kép)
- Có lọc: 80 lệnh, +91.7% trong 2026 (+132.3%/năm), DD 6.7% (1,5%/nhóm, lãi kép)

### 2026: đường ngưỡng (mô tả)

| Ngưỡng | Giữ: lệnh / R/lệnh / tổng R | Bỏ: lệnh / R/lệnh / tổng R | Chênh (giữ − bỏ) |
|---|---|---|---|
| 0.6 | 68 / +0.589 / tổng +40.1 | 15 / +0.427 / tổng +6.4 | +0.162 |
| 0.7 | 72 / +0.597 / tổng +43.0 | 11 / +0.314 / tổng +3.5 | +0.283 |
| 0.8 | 80 / +0.567 / tổng +45.4 | 3 / +0.360 / tổng +1.1 | +0.207 |
| 0.9 | 82 / +0.573 / tổng +47.0 | 1 / -0.500 / tổng -0.5 | +1.073 |
| 1.0 | 83 / +0.560 / tổng +46.5 | 0 / +0.000 / tổng +0.0 | +0.560 |

**Kết luận theo luật: KHÔNG ĐẠT → đóng ý này, VHedge giữ nguyên.**

## Nhận xét

- **Ngay ở giai đoạn phát hiện, hiệu ứng đã mong manh.** Chênh lệch giữ − bỏ không đều theo ngưỡng:

  | Ngưỡng | 0,6 | 0,7 | 0,8 | 0,9 | 1,0 |
  |---|---|---|---|---|---|
  | Chênh (R) | +0,29 | +0,09 | **+0,70** | +0,23 | +0,30 |

  Đỉnh nhọn đúng ở 0,8 là dấu hiệu của ngưỡng "trúng may" trên 30 lệnh. Hiệu ứng không phải do giờ trong ngày (trong cùng nhóm giờ vẫn còn +0,64), nhưng mẫu bỏ chỉ 2–21 lệnh mỗi nhóm.
- **2026 không xác nhận.** Chỉ 3 lệnh bị lọc, và chúng **có lãi** (+0,36R/lệnh). Bỏ chúng làm VHedge 2026 giảm nhẹ (+94,7% → +91,7%), DD không đổi.
- **VHedge G119 không lọc vẫn tốt trên 2026**: 83 lệnh, +0,56R/lệnh, DD 6,7% ở 1,5%/nhóm. Không có lý do thêm bộ lọc ADR.
