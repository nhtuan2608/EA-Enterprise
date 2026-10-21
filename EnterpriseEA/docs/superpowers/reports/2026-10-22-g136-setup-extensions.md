# G136 — năm hướng mở rộng setup: bản chính thức trên dữ liệu PC (22/10/2026)

Kế hoạch: [2026-10-21-g136-setup-extensions.md](../plans/2026-10-21-g136-setup-extensions.md), có mục "Sửa đổi P2" ghi trước khi
chạy P2. Bản sơ bộ VPS: [2026-10-21-g136-prelim-h1-vps.md](2026-10-21-g136-prelim-h1-vps.md).

Dữ liệu: `research/long/data/{m30v,m15v,h1v,h4v}/XAUUSD.csv` (XAUUSD-VIP, giờ server, 5 ngày/tuần, M15 từ 20/07/2021). Trạng
thái D1 = dấu SMA50 − SMA200 của giá đóng ngày server đã đóng trước lúc vào lệnh, trùng nến D1 broker mà EA dùng (xem
[G138 PC](2026-10-22-g138-d1-divergence-pc.md)).

Kỳ:
- sớm 01/2018–06/2021, chỉ báo cáo;
- train 07/2021–12/2023;
- validate 01/2024–06/2025;
- test 07/2025–06/2026, không còn kín;
- sau 07/2026 chỉ xem.

Quy ước chung:
- chi phí harsh G68, kèm bản × 1,5;
- đối chứng ngẫu nhiên 200 lần;
- ngưỡng một ô p ≤ 0,005 (10 ô quyết định).

Không chỉnh luật sau khi chạy.

| Script | Mục | Thay đổi so với bản sơ bộ |
|---|---|---|
| [`g136_p1p4.py`](../../research/long/g136_p1p4.py) | P1 đầy đủ, P4 M30 | sổ M30 theo mặc định G89 (nến con và bồi M15 từ 20/07/2021); kỳ sớm từ 2018 |
| [`g136_prelim_h1.py`](../../research/long/g136_prelim_h1.py) | phần H1 của P1, P4 H1 | không đổi (bảng bàn giao) |
| [`g136_p2.py`](../../research/long/g136_p2.py) | P2 (luật đã sửa) | sổ bán M30 của EA (S07S/S07ES/S07RS/S07AS, G89) làm ô quyết định; S07 G67 H1/H4 chỉ tham khảo |
| [`g136_p3.py`](../../research/long/g136_p3.py) | P3 | M30 từ 2018, M15 từ 20/07/2021 |
| [`g137_patterns.py`](../../research/long/g137_patterns.py) | P5 | xem [G137](2026-10-22-g137-pattern-families.md) |

Sổ S07 M30 (bản Python G89, cả hai chiều) có 1.266 chân, 71% cùng trạng thái D1. Rủi ro M30 là 1,5% × trọng số EA × 0,5 cho
chân ngược D1 (G134).

## P1 — S07 H1 chỉ mua cùng sóng D1, không chồng M30

Ô: số lệnh / R trung bình / tổng R (phí harsh).

| Nhóm | Sớm | Train | Validate | Test |
|---|---|---|---|---|
| **P1: mua cùng sóng, không trùng M30** | 27 / +0,602 | **16 / +0,016** | 19 / +0,165 | **7 / −0,233** |
| P1, phí × 1,5 | 27 / +0,579 | 16 / −0,001 | 19 / +0,153 | 7 / −0,239 |
| Mua cùng sóng nhưng trùng M30 (bị loại) | 57 / +0,199 | 29 / +0,041 | 51 / +0,695 | 27 / +1,646 |
| Mọi lệnh mua H1 | 114 / +0,148 | 80 / +0,183 | 70 / +0,552 | 34 / +1,259 |
| Mua cùng sóng (cả phần trùng, `g136_prelim_h1`) | 84 / +0,336 | 45 / +0,033 | 70 / +0,545 | 34 / +1,267 |
| Mua ngược sóng | 30 / −0,335 | 35 / **+0,377** | — | — |

- 70% lệnh mua H1 cùng sóng trùng một chân S07 M30 cùng chiều đang mở. Phần lời của H1 nằm gần hết trong phần trùng đó.
- p ngẫu nhiên (train + validate) của P1 sau khi loại trùng: **0,45**.

Danh mục (vốn 10.000, lãi kép). Ô: %/năm / DD / **MAR**; cột cuối là DD p90 của cửa sổ một năm, 07/2021–06/2026:

| Sổ | Train | Validate | Test | DD p90 1 năm |
|---|---|---|---|---|
| M30 một mình | +26,8% / 14,0% / **1,92** | +237,6% / 17,0% / **13,97** | +203,4% / 12,9% / **15,74** | 17,0% |
| M30 + H1 0,50% | +26,9% / 14,8% / **1,81** | +240,5% / 17,8% / **13,51** | +201,0% / 13,4% / **15,04** | 17,8% |
| M30 + H1 0,75% | +26,9% / 15,3% / **1,76** | +241,9% / 18,2% / **13,29** | +199,7% / 13,6% / **14,70** | 18,2% |

| Tiêu chí P1 | 0,50% | 0,75% |
|---|---|---|
| R của H1 > 0 ở train, validate, test | Không (test −0,23) | Không |
| ≥ 40 lệnh mỗi kỳ | Không (16 / 19 / 7) | Không |
| p ≤ 0,005 | Không (0,45) | Không |
| MAR danh mục ≥ M30 một mình ở cả ba kỳ | Không (thấp hơn ở cả ba) | Không |
| DD p90 không vượt M30 quá 3 điểm % | Có (+0,8) | Có (+1,2) |

**Kết luận theo luật P1: KHÔNG ĐẠT.**

## P2 — họ lệnh bán S07 chỉ khi D1 death cross (luật đã sửa)

**Ô quyết định: sổ bán M30 của EA** (bản Python G89 của S07S / S07ES / S07RS / S07AS). Sổ có 135 chân bán trong 10/2016–09/2026,
khớp đúng số của báo cáo G89. Mỗi chân tính là một lệnh (R theo SL ban đầu, phí harsh).

Đối chứng ngẫu nhiên chỉ dùng ngày death 2018–2023: với mỗi chân DX lấy một nến M30 cùng giờ server, bán ở giá mở nến sau,
cùng khoảng stop theo ATR M30, thoát như chân gốc G89. Lệnh bồi trong sổ thật thoát kiểu E2X trên khung của nó, nên đối
chứng chỉ gần đúng với các chân bồi.

| Nhóm | Sổ bán M30 (EA) |
|---|---|
| D0: mọi chân bán 01/2018–12/2023 | 53 / +0,193 / +10,2 |
| **DX: bán ngày death 2018–2023** | **9** / +0,540 / +4,9 |
| DX, phí × 1,5 | 9 / +0,524 |
| DX nửa đầu (01/2018–06/2021) | **0 chân** |
| DX nửa sau (07/2021–2023) | 9 / +0,540 |
| DX theo loại | S07S 0; S07ES 3 / +1,008; S07RS 2 / −0,150; S07AS 4 / +0,534 |
| p ngẫu nhiên (chỉ ngày death) | **0,020** |
| Bán ngày golden 01/2018–06/2026 | 110 / +0,114 / +12,5 |
| Bán ngày golden 2024–06/2026 | 66 / +0,108 / +7,1 |
| Forward 26/06/2026 → hết dữ liệu (22/09/2026), bán ngày death | 8 / −0,270 / −2,2 |
| Forward kín từ 21/10/2026 | chưa có (dữ liệu PC tới 09/10/2026) |

| Tiêu chí DX | Kết quả |
|---|---|
| Phần chọn R/lệnh > 0 | Có (+0,54) |
| ≥ 60 lệnh | **Không (9)** |
| Cao hơn D0 | Có (+0,54 > +0,19) |
| Hai nửa không âm | **Không đo được**: nửa đầu không có chân nào |
| p ≤ 0,005 | **Không (0,020)** |
| Phí × 1,5 vẫn dương | Có |
| Forward ≥ 30 lệnh, R > 0 | **Không** (8 chân, −0,27) |

**Kết luận theo luật P2 (DX): KHÔNG ĐẠT.** Sổ bán M30 của EA quá thưa trong ngày death cross 2018–2023: 9 chân, tất cả ở nửa sau.

Vì DX không đạt, theo kế hoạch xét DS như khuyến nghị vận hành. Dữ liệu **không ủng hộ** DS: chân bán ngày golden
(phần DS sẽ bỏ) dương +0,11R trên 110 chân, kể cả 2024–06/2026 (+0,11R / 66 chân). Chuyển chúng sang SHADOW sẽ bỏ đi phần dương.

**Tham khảo (không quyết định)**: S07 bán G67 trên H1 / H4, cùng script với bản sơ bộ VPS.

| Nhóm | H1 | H4 |
|---|---|---|
| D0 bán 2018–2023 | 201 / −0,064 | 68 / −0,062 |
| DX bán ngày death 2018–2023 | 76 / −0,070 | 25 / −0,117 |
| DX nửa đầu / nửa sau | 45 / +0,024 ; 31 / −0,207 | 21 / −0,109 ; 4 / −0,161 |
| p ngẫu nhiên | 0,29 | 0,50 |
| Bán ngày golden 2018–2026 | 171 / −0,039 | 57 / −0,091 |
| Forward 26/06–20/10/2026 (đã xem) | 21 / −0,036 | 5 / −0,148 |
| Mua ngày death 2018–2023 | 69 / +0,003 | 22 / +0,547 |

H1 / H4 cũng không đạt, giống bản sơ bộ: bán ngày death không tốt hơn mọi lệnh bán.

**S07AS đứng độc lập** (`InpS07AsStandalone`, báo cáo, xấp xỉ). Lấy tín hiệu bồi bán H1/H4 có ribbon xếp thứ tự, vào ngày death
cross, khi không có chân bán nào của sổ M30 đang mở, mỗi lần một lệnh. Không mô phỏng sentiment.

| Khoảng | Lệnh / R |
|---|---|
| 2018–2023 | 49 / **−0,178** / −8,7 |
| 2024–06/2026 | 0 (không có ngày death) |
| từ 26/06/2026 | 9 / −0,090 / −0,8 |
| theo khung 2018–2026 | H1 59 / −0,258; H4 10 / −0,031 |

Phần này không phải ô quyết định và là bản xấp xỉ. Dù vậy, nó **không ủng hộ** để `InpS07AsStandalone` bật trên sổ thật:
- 2018–2023 âm (−0,18R trên 49 lệnh);
- từ khi D1 death cross 26/06/2026 cũng âm (9 lệnh);
- trên EA mặc định đang `false`, nên giữ `false` hoặc chỉ SHADOW.

## P3 — VHedge M30 / M15 với morning / evening star

Script giữ nguyên cách làm của bản sơ bộ:
- bối cảnh G118 A;
- V = nến V G116/G118; MS theo định nghĩa trong kế hoạch, có chạm EMA200 trong 3 nến trước;
- quản lý hedge G116, stop ± 2 ATR, đơn vị U;
- đối chứng ngẫu nhiên 200 lần trên mọi nến cùng bối cảnh.

Ô: số nhóm / U trung bình / tổng U.

| Khung | Tín hiệu | Sớm | Train | Validate | Test | Sau 07/2026 |
|---|---|---|---|---|---|---|
| M30 | V | 69 / +0,049 | 70 / +0,636 / +44,5 | 50 / +0,729 / +36,5 | 11 / +0,208 / +2,3 | 10 / +0,102 |
| M30 | **MS** | 6 / −0,492 | **9** / +0,225 | **5** / −0,259 | **7** / +0,812 | 3 / +0,500 |
| M30 | V∪MS | 73 / +0,041 | 74 / +0,608 / +45,0 | 54 / +0,633 / **+34,2** | 16 / +0,436 / +7,0 | 10 / +0,102 |
| M15 | V | — | 154 / +0,133 / +20,5 | 100 / +0,075 / +7,5 | 62 / +0,092 / +5,7 | 19 / −0,281 |
| M15 | **MS** | — | **17** / +0,013 | **13** / +0,021 | **7** / +0,071 | 1 / +1,996 |
| M15 | V∪MS | — | 162 / +0,113 / **+18,4** | 107 / +0,061 / **+6,5** | 68 / +0,083 / +5,7 | 20 / −0,167 |

- p ngẫu nhiên (train + validate): MS **0,50** (M30), **0,39** (M15); V 0,015 (M30), 0,080 (M15).
- MS: 30 nhóm trên M30 (14 mua / 16 bán), 38 trên M15. 13 / 16 nhóm MS trùng một nhóm V.
- Phí × 1,5: MS M30 validate −0,77; MS M15 train và validate thành âm (−0,03 / −0,07). Không ô nào đổi kết luận.

| Tiêu chí P3 | M30 | M15 |
|---|---|---|
| MS dương ở train, validate, test | Không (validate −0,26) | Có (nhưng ≈ 0: +0,01 / +0,02 / +0,07) |
| ≥ 30 nhóm MS mỗi kỳ | Không (9 / 5 / 7) | Không (17 / 13 / 7) |
| MS thắng ngẫu nhiên p ≤ 0,005 | Không (0,50) | Không (0,39) |
| V∪MS tổng U cao hơn V ở cả ba kỳ | Không (validate 34,2 < 36,5) | Không (train 18,4 < 20,5; validate 6,5 < 7,5) |

**Kết luận theo luật P3 (M30, M15): KHÔNG ĐẠT.**

Ghi chú phụ, không phải ô quyết định: nến V M30 (G118 A) trên dữ liệu PC dương ở mọi kỳ (+0,64 / +0,73 / +0,21U, p 0,015). Test
chỉ 11 nhóm, sau 07/2026 +0,10U trên 10 nhóm.

## P4 — nhãn Wyckoff spring / upthrust

Chân gốc S07 M30 (sổ G89) và sổ mua H1 cùng sóng. Ô: số lệnh / R trung bình.

| Sổ | Kỳ | Có nhãn | Không nhãn | Chênh (R) |
|---|---|---|---|---|
| **Mua M30** (ô quyết định) | Sớm | 53 / +0,398 | 177 / +0,033 | +0,37 |
| | Train | 40 / +0,188 | 125 / +0,410 | **−0,22** |
| | Validate | 43 / −0,048 | 120 / +0,769 | **−0,82** |
| | Test | 25 / +0,787 | 51 / +0,482 | +0,31 |
| **Mua H1** cùng sóng (ô quyết định) | Train | 9 / −0,413 | 36 / +0,145 | −0,56 |
| | Validate | 7 / −0,319 | 63 / +0,641 | −0,96 |
| | Test | 7 / +2,501 | 27 / +0,948 | +1,55 |
| Bán M30 (báo cáo) | Train / Validate / Test | 4 / 3 / 8 lệnh | | +0,81 / −0,20 / −0,08 |

- p hoán vị: mua M30 **0,91**, mua H1 0,53, bán M30 0,32.
- Tỷ lệ có nhãn: M30 27%, H1 15%.
- Sổ H1 ở đây gồm cả lệnh trùng M30 (`g136_prelim_h1`). Sổ P1 sau khi loại trùng chỉ có 16 / 19 / 7 lệnh mỗi kỳ, không thể đủ 25
  lệnh có nhãn.

**Kết luận theo luật P4 (M30 và H1): KHÔNG ĐẠT.** Chênh lệch đổi dấu giữa các kỳ, H1 thiếu lệnh có nhãn, p xa ngưỡng.

## P5 — phá kênh hồi làm điểm bồi S07A

Chạy trong G137 ([báo cáo](2026-10-22-g137-pattern-families.md#p5--phá-kênh-hồi-làm-điểm-bồi-s07a-luật-g136-ngân-sách-g136)), sổ
M30 G89 với M15 từ 20/07/2021, có kỳ train và chi phí × 1,5. R mỗi lệnh gốc (train / validate / test):

| Biến thể | Train | Validate | Test | DD p90 1 năm |
|---|---|---|---|---|
| A1 (hiện tại) | +0,378 | +0,862 | +0,960 | 17,2% |
| C1 | +0,425 | +0,464 | +0,722 | 21,9% |
| C2 | +0,456 | +0,838 | +0,943 | 17,2% |

**Kết luận theo luật P5 (C1, C2): KHÔNG ĐẠT.** C2 hơn A1 ở train nhưng thua khoảng 0,02R ở validate và test.

## So với bản sơ bộ VPS

| Mục | Sơ bộ VPS (Lirunex) | PC (XAUUSD-VIP) | Giống / khác, vì sao |
|---|---|---|---|
| P1 H1 không trùng M30 | 17 / 17 / 7 lệnh, −0,32 / +0,28 / −0,08, p 0,56; 71% trùng M30 | 16 / 19 / 7 lệnh, +0,02 / +0,17 / −0,23, p 0,45; 70% trùng | giống: H1 tốt chỉ khi trùng M30 |
| P1 MAR danh mục | thấp hơn M30 ở validate, test | thấp hơn M30 ở cả ba kỳ | giống. Mức %/năm của M30 khác nhiều (train VPS +354%, PC +27%) vì sổ VPS trước 09/2022 không có nến con M15 và có sai khác feed. Chỉ so tương đối trong cùng nguồn |
| P2 | S07 G67 H1/H4: DX ≈ 0R, không đạt | sổ bán M30 của EA: DX 9 chân +0,54R, p 0,02; G67 H1/H4 giống VPS | ô quyết định mới (sổ M30) không có trên VPS; không đạt vì quá ít chân. Bán ngày golden dương ở cả hai nguồn, nên DS không được ủng hộ |
| P3 MS | M30 9 / 6 / 7, M15 12 / 12 / 8 nhóm, p 0,53 / 0,78 | M30 9 / 5 / 7, M15 17 / 13 / 7 nhóm, p 0,50 / 0,39 | giống; M15 PC có thêm 07/2021–08/2022 |
| P4 | mua M30 chênh +0,12 / −0,93 / +0,66, p 0,76 | −0,22 / −0,82 / +0,31, p 0,91 | giống: validate âm mạnh ở cả hai |
| P5 | C2 hơn A1 ở validate +0,03, thua test −0,003 | C2 hơn ở train +0,08, thua validate và test ~0,02 | gần hòa ở cả hai, không đạt |

Tóm lại, hai nguồn dữ liệu cho cùng kết luận ở mọi mục. Khác biệt lớn nhất nằm ở mức tuyệt đối của sổ M30, do bản VPS dựng
không có nến con M15 trước 09/2022. Khác biệt này không đổi chiều so sánh nào.

## Tổng hợp

| Mục | Kết luận theo luật |
|---|---|
| P1 (H1 cùng sóng, không trùng M30; 0,50% / 0,75%) | KHÔNG ĐẠT |
| P2 (bán chỉ khi death cross, sổ bán M30 của EA) | KHÔNG ĐẠT (9 chân, p 0,020); DS không được ủng hộ |
| P3 (VHedge + morning/evening star, M30 / M15) | KHÔNG ĐẠT |
| P4 (spring/upthrust, mua M30 / mua H1) | KHÔNG ĐẠT |
| P5 (phá kênh hồi làm điểm bồi, C1 / C2) | KHÔNG ĐẠT |

Không có đề xuất đưa vào EA. Một ghi chú vận hành (không phải ô quyết định): bản xấp xỉ S07AS đứng độc lập âm ở 2018–2023 và
từ 26/06/2026, nên `InpS07AsStandalone` nên giữ `false` (mặc định) cho tới khi có phép thử riêng.
