# G137 — các họ mẫu hình chưa từng thử, kèm P5 của G136: bản chính thức trên dữ liệu PC (22/10/2026)

Kế hoạch: [2026-10-21-g137-pattern-families.md](../plans/2026-10-21-g137-pattern-families.md) (đăng ký trước, commit `5a3c30a`).
Bản sơ bộ VPS: [2026-10-21-g137-prelim-vps.md](2026-10-21-g137-prelim-vps.md).

Script: [`research/long/g137_patterns.py`](../../research/long/g137_patterns.py), seed 137. Đây là `g137_prelim.py`, chỉ đổi đúng
các mục trong bảng "phải đổi" của [file bàn giao](../plans/2026-10-21-pc-handoff-g136-g138.md):
- kỳ sớm bắt đầu 01/2018 thay vì 06/2019;
- P5 dùng mặc định G89: nến con M15 và bồi M15 từ 20/07/2021, không còn `SPLIT = 2022-09` / `START = 2019-06`;
- P5 có kỳ train (từ 20/07/2021) và bản chi phí × 1,5.

Luật tín hiệu, thoát lệnh, đối chứng và ngưỡng giữ nguyên, không chỉnh sau khi chạy.

Dữ liệu: `research/long/data/{h1v,m30v,m15v}/XAUUSD.csv` (XAUUSD-VIP, giờ server, 5 ngày/tuần, xem
[G138 PC](2026-10-22-g138-d1-divergence-pc.md)). H1/M30 từ 2010, M15 từ 20/07/2021.

Quy ước như kế hoạch:
- chi phí harsh G68;
- đối chứng ngẫu nhiên 200 lần (cùng chiều, giờ server, kỳ, khoảng SL theo ATR, cách thoát), p gộp train + validate;
- ngưỡng một ô p ≤ 0,005;
- đạt khi R/lệnh > 0 ở train, validate và test, ≥ 30 lệnh mỗi kỳ (H1) hoặc ≥ 40 (M30), và R gộp train + validate > 0 với chi phí × 1,5.

## G1–G5

Ô: số lệnh / R trung bình / tổng R (phí harsh). Kỳ sớm 01/2018–06/2021 và sau 07/2026 chỉ để xem.

| Ô | Sớm | Train | Validate | Test | Sau 07/2026 | p | Kết luận theo luật |
|---|---|---|---|---|---|---|---|
| G1 vai-đầu-vai H1 | 43 / −0,163 | 24 / −0,376 | 15 / −0,831 | 9 / −0,608 | 7 / −0,466 | 0,97 | **KHÔNG ĐẠT** |
| G1 vai-đầu-vai M30 | 67 / −0,149 | 39 / −0,065 | 35 / −0,102 | 15 / +0,396 | 3 / −1,031 | 0,58 | **KHÔNG ĐẠT** |
| G2 tam giác H1 | 159 / −0,063 | 107 / −0,104 | 62 / +0,118 | 46 / +0,027 | 12 / +0,235 | 0,27 | **KHÔNG ĐẠT** |
| G2 tam giác M30 | 249 / −0,172 | 188 / −0,080 | 116 / −0,107 | 79 / +0,185 | 22 / +0,480 | 0,32 | **KHÔNG ĐẠT** |
| G3 harmonic H1 | 25 / +0,121 | 26 / +0,384 | 13 / +0,047 | 9 / **−0,243** | — | 0,020 | **KHÔNG ĐẠT** |
| G4 Bollinger sideway H1 | 55 / −0,518 | 38 / −0,349 | 25 / −0,038 | 13 / −0,091 | 7 / −0,327 | 0,65 | **KHÔNG ĐẠT** |
| G4 Bollinger sideway M30 | 99 / −0,489 | 81 / −0,452 | 65 / −0,107 | 29 / −0,203 | 13 / −0,188 | 0,81 | **KHÔNG ĐẠT** |
| G5 kênh song song H1 | 110 / −0,256 | 85 / −0,401 | 52 / −0,132 | 38 / −0,211 | 9 / −0,356 | 0,96 | **KHÔNG ĐẠT** |
| G5 kênh song song M30 | 198 / −0,105 | 131 / −0,234 | 88 / +0,072 | 74 / −0,192 | 18 / −0,353 | 0,31 | **KHÔNG ĐẠT** |

Chi phí × 1,5 (train / validate / test), không làm ô nào đổi kết luận:

| Ô | Train | Validate | Test |
|---|---|---|---|
| G1 H1 | −0,395 | −0,844 | −0,614 |
| G1 M30 | −0,092 | −0,120 | +0,389 |
| G2 H1 | −0,128 | +0,100 | +0,021 |
| G2 M30 | −0,120 | −0,133 | +0,175 |
| G3 H1 | +0,360 | +0,033 | −0,248 |
| G4 H1 | −0,391 | −0,057 | −0,106 |
| G4 M30 | −0,513 | −0,144 | −0,222 |
| G5 H1 | −0,434 | −0,155 | −0,222 |
| G5 M30 | −0,285 | +0,036 | −0,206 |

### G3 harmonic H1 (ô gần nhất ở bản sơ bộ)

| Nhóm | Train | Validate | Test |
|---|---|---|---|
| Gartley | 16 / +0,236 | 6 / +0,109 | 7 / −0,021 |
| Bat | 10 / +0,621 | 7 / −0,006 | 2 / −1,018 |
| Mua | 13 / +0,569 | 6 / −0,249 | 5 / +0,372 |
| Bán | 13 / +0,199 | 7 / +0,301 | 4 / −1,011 |

Trên dữ liệu PC, G3 **yếu hơn** bản sơ bộ:
- Test chuyển sang âm (−0,24R trên 9 lệnh), validate gần 0 (+0,05R trên 13 lệnh).
- p 0,020 vẫn xa ngưỡng 0,005.
- Không kỳ nào đủ 30 lệnh.
- Phần dương gần như chỉ nằm ở train và kỳ sớm (+0,12R). Đó là đặc điểm của một mẫu nhỏ, không phải lợi thế ổn định.

### Ghi chú các ô khác

- **G2 tam giác** vẫn chỉ dương từ 2024/2025, train âm ở cả hai khung. Tam giác M30 phá cùng chiều EMA200: +0,09 / −0,08 / +0,42
  (báo cáo, không quyết định). Không ổn định qua các kỳ.
- **G1 vai-đầu-vai H1** âm ở mọi kỳ, kể cả kỳ sớm. Trên M30 chỉ test dương (15 lệnh).
- **G4 Bollinger khi sideway** âm ở mọi kỳ, mọi khung, khớp G130/G131 (đảo về trung bình không có lợi thế trên vàng).
- **G5 kênh song song** chỉ validate M30 dương (+0,07R), bán H1/M30 âm ở test.

## P5 — phá kênh hồi làm điểm bồi S07A (luật G136, ngân sách G136)

Sổ S07 M30 chiều mua (bản Python G89 với mặc định: nến con M15 từ 20/07/2021). Chỉ lấy các chân gốc từ 20/07/2021, vì phá kênh
cần nến M15. Ô: số lệnh gốc / tổng R mỗi lệnh gốc (gốc × trọng số + bồi × 0,67) / số lệnh bồi.

| Biến thể | Train (20/07/2021–2023) | Validate | Test | Sau 07/2026 | DD p90 1 năm (07/2021–06/2026) |
|---|---|---|---|---|---|
| A1 (bồi hiện tại) | 164 / +0,378 / 133 | 163 / **+0,862** / 115 | 76 / **+0,960** / 77 | 13 / +0,165 / 8 | 17,2% |
| C1 (thay bằng phá kênh) | 164 / +0,425 / 44 | 163 / +0,464 / 52 | 76 / +0,722 / 29 | 13 / −0,038 / 2 | 21,9% |
| C2 (A1 + phá kênh) | 164 / **+0,456** / 142 | 163 / +0,838 / 130 | 76 / +0,943 / 85 | 13 / +0,165 / 8 | 17,2% |

Chi phí × 1,5, R mỗi lệnh gốc (train / validate / test): A1 +0,343 / +0,839 / +0,948; C1 +0,393 / +0,440 / +0,710; C2
+0,418 / +0,812 / +0,929.

Luật P5: hơn A1 ở cả ba kỳ, DD p90 không cao hơn A1, giữ nguyên với chi phí × 1,5.

| Tiêu chí | C1 | C2 |
|---|---|---|
| Hơn A1 ở train | Có (+0,05) | Có (+0,08) |
| Hơn A1 ở validate | Không (−0,40) | Không (−0,02) |
| Hơn A1 ở test | Không (−0,24) | Không (−0,02) |
| DD p90 không cao hơn A1 | Không (21,9% > 17,2%) | Có (bằng) |
| Chi phí × 1,5 | thua ở validate, test | thua ở validate, test |
| **Kết luận theo luật** | **KHÔNG ĐẠT** | **KHÔNG ĐẠT** |

P5 C2 (ô gần nhất ở bản sơ bộ) lặp lại đúng hình ảnh sơ bộ: thêm 9–15 lệnh bồi mỗi kỳ. Nó hơn A1 ở train (kỳ sơ bộ không có),
nhưng thấp hơn khoảng 0,02R ở validate và test. Không có đối chứng ngẫu nhiên cho P5: luật P5 so với A1 trên cùng sổ,
không có ô p.

## Cổng thứ hai

Không ô nào đạt, nên không chạy cổng thứ hai (tỷ lệ trùng S07 M30, MAR danh mục).

## So với bản sơ bộ VPS

| Ô | Sơ bộ VPS (train / validate / test, p) | PC | Giống / khác |
|---|---|---|---|
| G1 H1 | −0,44 / −0,79 / −0,64, p 0,99 | −0,38 / −0,83 / −0,61, p 0,97 | giống |
| G1 M30 | +0,01 / −0,00 / +0,50, p 0,45 | −0,07 / −0,10 / +0,40, p 0,58 | giống (PC hơi kém) |
| G2 H1 | −0,15 / +0,26 / +0,13, p 0,33 | −0,10 / +0,12 / +0,03, p 0,27 | giống |
| G2 M30 | −0,13 / −0,12 / +0,15, p 0,67 | −0,08 / −0,11 / +0,19, p 0,32 | giống |
| G3 H1 | +0,40 / +0,06 / +0,10, p 0,050 | +0,38 / +0,05 / **−0,24**, p 0,020 | train/validate giống; test đổi dấu (8–9 lệnh) |
| G4 H1 | −0,37 / −0,03 / +0,09, p 0,76 | −0,35 / −0,04 / −0,09, p 0,65 | giống |
| G4 M30 | −0,28 / −0,07 / −0,26, p 0,59 | −0,45 / −0,11 / −0,20, p 0,81 | giống |
| G5 H1 | −0,45 / −0,07 / −0,21, p 0,97 | −0,40 / −0,13 / −0,21, p 0,96 | giống |
| G5 M30 | −0,20 / +0,25 / −0,16, p 0,15 | −0,23 / +0,07 / −0,19, p 0,31 | giống (validate PC yếu hơn) |
| P5 C2 vs A1 | validate +0,03, test −0,003 | train +0,08, validate −0,02, test −0,02 | gần hòa ở cả hai; PC có thêm train |

Hai nguồn (Lirunex XAUUSD.r và XAUUSD-VIP) cho cùng dấu ở gần như mọi ô có đủ lệnh. Khác biệt chỉ ở các ô rất ít lệnh: G3 test 8–9
lệnh, và P5 nơi khác biệt nằm trong khoảng ±0,03R. Số lệnh hơi khác do khác feed (giá, spread, giờ nến), nhưng kết luận không
đổi.

## Tổng hợp

| Mục | Kết luận theo luật |
|---|---|
| G1 vai-đầu-vai (H1, M30) | KHÔNG ĐẠT |
| G2 tam giác (H1, M30) | KHÔNG ĐẠT |
| G3 harmonic (H1) | KHÔNG ĐẠT (test âm, p 0,020, < 30 lệnh mỗi kỳ) |
| G4 Bollinger sideway (H1, M30) | KHÔNG ĐẠT |
| G5 kênh song song (H1, M30) | KHÔNG ĐẠT |
| P5 C1 / C2 | KHÔNG ĐẠT (C2 gần hòa A1, thua ở validate và test) |

Không có đề xuất đưa vào EA. Các họ mẫu hình cổ điển trong kế hoạch (trừ Elliott Wave, không có định nghĩa tự động) đã được thử
và đều không đạt.
