# G68: Chau chuốt setup nén → bung DMI + EMA (XAUUSD M30) — kết quả

Kế hoạch đăng ký trước: `plans/2026-10-09-g68-dmi-ema-refine.md`. Chỉ dữ liệu MT5. Ô: số lệnh / R trung bình mỗi lệnh sau spread + commission. Quyết định chỉ dựa trên train + validate.

## C0 (bản gốc)

| 09/2018–07/2021 | Train 2021–2023 | Validate 2024–06/2025 | Test 07/2025–06/2026 | 07/2026–nay |
|---|---|---|---|---|
| 320 / +0.132 | 300 / +0.065 | 175 / +0.323 | 121 / +0.567 | 28 / +0.172 |

## Bước 1 — độ bền

**1a. 81 bộ lân cận** (ADX đáy 18/20/22 × DI 4/6/8 × ADX tăng 8/10/12 × cửa sổ 6/8/10 nến):

- Dương cả train và validate: 62/81 (77%)
- Dương cả 2018–2021 và test: 78/81 (96%)
- Dương cả 4 kỳ: 62/81 (77%)
- R/lệnh trung bình 4 kỳ: thấp nhất +0.176, trung vị +0.251, cao nhất +0.302
- **ĐẠT** (cần ≥ 60% ở cả hai)

Ba bộ yếu nhất: ADX≤22 DI≤8 tăng≤10 6 nến; ADX≤22 DI≤8 tăng≤12 6 nến; ADX≤22 DI≤8 tăng≤8 6 nến

**1b. Khớp lệnh khắt khe** (trượt 0,5 × spread mỗi chiều, spread ×3 lúc chuyển ngày, commission ×2):

| 09/2018–07/2021 | Train 2021–2023 | Validate 2024–06/2025 | Test 07/2025–06/2026 | 07/2026–nay | 2018–06/2026 |
|---|---|---|---|---|---|
| 320 / +0.067 | 300 / +0.011 | 175 / +0.289 | 121 / +0.550 | 28 / +0.161 | +0.155 |

**ĐẠT** (cần > 0 ở toàn kỳ và ở test).

## Bước 2 — mỗi thay đổi thử riêng so với C0

| # | Thay đổi | 09/2018–07/2021 | Train 2021–2023 | Validate 2024–06/2025 | Test 07/2025–06/2026 | 07/2026–nay | Lệnh còn | Giữ? |
|---|---|---|---|---|---|---|---|---|
| C0 | (gốc) | 320 / +0.132 | 300 / +0.065 | 175 / +0.323 | 121 / +0.567 | 28 / +0.172 | 100% | |
| R1 | Chỉ lệnh mua | 205 / +0.155 | 143 / +0.249 | 140 / +0.488 | 71 / +0.793 | 10 / -0.010 | 60% | giữ |
| R2 | Bán chỉ khi D1 dưới EMA200 D1 | 241 / +0.171 | 249 / +0.114 | 140 / +0.488 | 77 / +0.713 | 25 / +0.012 | 82% | giữ |
| R3 | SL bỏ nến trước khoảng trống > 6 giờ | 323 / +0.134 | 300 / +0.088 | 175 / +0.382 | 122 / +0.514 | 28 / +0.301 | 100% | giữ |
| R4 | Thoát khi cạn đà (EMA21 hết dốc + ADX giảm) | 323 / +0.128 | 305 / +0.038 | 181 / +0.306 | 114 / +0.510 | 28 / +0.169 | 102% | bỏ |
| R5 | ≥ 3R thì thoát theo EMA100 | 308 / +0.170 | 291 / +0.071 | 165 / +0.325 | 114 / +0.596 | 28 / -0.007 | 96% | giữ |
| R6 | Chặn ngày: 2 lệnh thua → nghỉ hết ngày | 310 / +0.127 | 292 / +0.060 | 170 / +0.335 | 116 / +0.617 | 28 / +0.172 | 97% | giữ (DD p90 1 năm ở 1,5%: 26% so với 27%; tổng R train+val +74 so với +76) |
| R7 | Chặn tuần: lỗ ≥ 4R → nghỉ hết tuần | 320 / +0.132 | 300 / +0.065 | 175 / +0.323 | 121 / +0.567 | 28 / +0.172 | 100% | bỏ (DD p90 1 năm ở 1,5%: 27% so với 27%; tổng R train+val +76 so với +76) |

**Bản cuối: C0 + R1 + R3 + R5**

## Bước 3 — phương án tốt nhất so với C0

| Bản | 09/2018–07/2021 | Train 2021–2023 | Validate 2024–06/2025 | Test 07/2025–06/2026 | 07/2026–nay |
|---|---|---|---|---|---|
| C0 | 320 / +0.132 | 300 / +0.065 | 175 / +0.323 | 121 / +0.567 | 28 / +0.172 |
| C0 + R1 + R3 + R5 | 196 / +0.225 | 136 / +0.339 | 130 / +0.596 | 66 / +0.806 | 10 / -0.054 |
| C0 + R1 + R3 + R5, khớp khắt khe | 196 / +0.159 | 136 / +0.288 | 130 / +0.562 | 66 / +0.789 | 10 / -0.062 |

- Ngẫu nhiên (200 lần): TB +0.053R, p = 0.000 (đạt p < 0,01).
- 2018–06/2026: 528 lệnh, +0.418R/lệnh, thắng 32%, lệnh thắng TB +2.60R, DD 12.8R, tổng +221R.
- Giữ lệnh: trung vị 8.5 giờ, 90% ≤ 43 giờ. Thoát: SL 101, TP 34, TREND 393

- Theo chiều (2018–06/2026): mua 528 / +0.418, bán —.

Theo năm: 2018: 26 lệnh -0.31R, 2019: 74 lệnh +0.11R, 2020: 76 lệnh +0.55R, 2021: 43 lệnh -0.07R, 2022: 56 lệnh +0.47R, 2023: 57 lệnh +0.42R, 2024: 76 lệnh +0.74R, 2025: 103 lệnh +0.50R, 2026: 27 lệnh +0.82R

### Rủi ro mỗi lệnh (lãi kép, 2018–06/2026)

| Rủi ro | %/năm | DD lớn nhất | 1 năm: trung vị | 1 năm: p10 | DD p90 1 năm | Chạm DD 10% | Chạm DD 20% |
|---|---|---|---|---|---|---|---|
| 1.0% | +31% | 12% | +33% | +8% | 9% | 1% | 0% |
| 1.5% | +49% | 18% | +51% | +12% | 14% | 31% | 0% |

### Danh mục với S04 + S06B (09/2018–09/2025, không lãi kép)

- Tương quan lãi/lỗ theo ngày (ngày cả hai có lệnh đóng, 35 ngày): +0.04

| Danh mục | %/năm | DD lớn nhất |
|---|---|---|
| S04 + S06B (0,5%) | +2.5% | 5.1% |
| Setup này (1,5%) | +38.4% | 19.2% |
| Cả ba | +41.0% | 19.0% |

### Lân cận của bản cuối (81 bộ)

- Dương cả 4 kỳ (2018–2021, train, validate, test): 81/81 (100%)
- R/lệnh trung bình 4 kỳ: thấp nhất +0.382, trung vị +0.479, cao nhất +0.605

### Ghi chú sau khi chạy (không đăng ký trước, không dùng để chọn)

- Theo chế độ D1 (2018–06/2026): khi giá D1 trên EMA200 D1, bản cuối 480 lệnh +0,47R; khi D1 dưới EMA200 D1, 48 lệnh −0,11R. Các năm vàng đi ngang/giảm (2018 −0,31R, 2021 −0,07R) là các năm âm. Lợi thế gắn với xu hướng tăng dài hạn của vàng 2018–2026; nên kiểm chứng riêng một công tắc "chỉ mua khi D1 trên EMA200" ở lần đăng ký sau.

## Kết luận

**Phương án tốt nhất: C0 + R1 + R3 + R5** — XAUUSD M30, nén 4 giờ, chỉ lệnh mua, cùng chiều EMA200 H4, SL bỏ qua nến trước khoảng trống cuối tuần, thoát theo EMA55 rồi EMA100 khi lãi ≥ 3R, TP 8R.

- Bước 1 (độ bền) đạt: 77% bộ lân cận của C0 dương cả 4 kỳ; khớp lệnh khắt khe vẫn +0,16R/lệnh.
- Bản cuối dương ở 2018–2021 (+0,23), train (+0,34), validate (+0,60), test (+0,81); khớp khắt khe +0,16 / +0,29 / +0,56 / +0,79; thắng ngẫu nhiên p < 0,001; 81/81 bộ lân cận dương cả 4 kỳ.
- 1,5%/lệnh: +49%/năm, DD lớn nhất 18%, DD p90 1 năm 14%, 31% số năm chạm DD 10%, 0% chạm 20%. 1%/lệnh: +31%/năm, DD 12%.
- Ghép với S04 + S06B: tương quan theo ngày +0,04; DD của cả ba (19,0%) không lớn hơn setup này một mình (19,2%).
- Rủi ro chính: chỉ mua, phụ thuộc xu hướng tăng của vàng; 07/2026–nay 10 lệnh −0,05R.
