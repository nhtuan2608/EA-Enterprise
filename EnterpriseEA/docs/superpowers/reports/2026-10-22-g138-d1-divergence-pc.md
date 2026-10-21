# G138 — đối chiếu D1 trên dữ liệu PC (XAUUSD-VIP), 22/10/2026

Tiếp nối [bản sơ bộ VPS](2026-10-21-g138-d1-divergence-prelim.md). Chỉ nghiên cứu: không sửa EA, terminal chỉ đọc bằng
`copy_rates_from_pos`. Dữ liệu: `research/long/data/{m30v,m15v,h1v,h4v}/XAUUSD.csv` (XAUUSD-VIP, có sẵn `h4v`, không phải dựng).

Script và kết quả:
- [`g138_pc_checks.py`](../../research/long/g138_pc_checks.py) → `results/g138/pc_checks.json` (câu 1, 2)
- [`g138_d1_sensitivity.py`](../../research/long/g138_d1_sensitivity.py), không sửa → `results/g138/d1_sensitivity_pc.json` (câu 3)
- [`g138_g134_part1.py`](../../research/long/g138_g134_part1.py) → `results/g138/g134_part1_pc.json` (câu 4)

## Trả lời 4 câu hỏi

**1. Dữ liệu PC có bao nhiêu ngày server mỗi tuần? — 5.** `m30v`: Thứ Hai–Thứ Sáu khoảng 20.000 nến mỗi ngày, Thứ Bảy 0, Chủ
nhật 99 nến, cả 99 đều ở 10/2010–09/2012 (feed cũ). Từ 2013 trở đi trung bình 4,92–4,97 ngày/tuần (dưới 5 vì ngày lễ). `h1v`
giống hệt; `m15v` (từ 07/2021) không có nến Chủ nhật nào.

Độ lệch giờ mà `g67_dmi_ema.load` giả định (server = UTC+2, UTC+3 khi Mỹ theo giờ mùa hè, tức nửa đêm server = giờ đóng cửa
New York) khớp với mốc NFP. Theo luật đó, NFP (08:30 New York) luôn rơi vào 15:30 giờ server. Trên các thứ Sáu đầu tháng từ
2018, nến có biên độ lớn nhất trong 13:00–18:00 server mở lúc 15:30 ở 52/99 ngày (M30), 33/61 (M15), 15:00 ở 60/99 (H1). Không
có tháng nào lệch đều sang 14:30 hay 16:30 quanh các tuần đổi giờ (tháng 3, tháng 11). Các ngày còn lại là ngày NFP không
rơi vào thứ Sáu đầu tháng, hoặc ngày có tin lớn hơn (ISM 10:00 New York = 17:00 server).

**2. Nến D1 XAUUSD-VIP trong terminal PC có nến Chủ nhật không? — Không.** 400 nến D1 (04/2025–10/2026, VTMarkets-Demo):
Thứ Hai 81, Thứ Ba 81, Thứ Tư 81, Thứ Năm 78, Thứ Sáu 79, Thứ Bảy 0, Chủ nhật 0. Trung bình 4,95 nến/tuần. Như vậy nến D1 broker
của EA trên PC trùng biến thể "server 00:00", giống Lirunex.

**3. PC có lặp lại "server 50/200 yếu, 42/167 mạnh" không? — Có, gần như y hệt VPS.**

Tỷ lệ lệnh đổi trạng thái D1 so với "server 00:00": gộp Chủ nhật 0–0,5%, trễ thêm 1 ngày 0,4–0,6%, UTC 00:00 / UTC 12:00 /
SMA 42/167 4,5–8,2%.

Chênh R (cùng D1 − ngược D1), 07/2021–06/2026, mua và bán gộp, p hoán vị một phía (2.000 lần):

| Sổ (PC) | Lệnh | server 00:00 (như EA) | UTC 00:00 | gộp Chủ nhật | SMA 42/167 | trễ 1 ngày |
|---|---|---|---|---|---|---|
| S07 M30 sổ G89 | 1.142 | +0,21 (p 0,14) | +0,42 (p **0,006**) | +0,17 (p 0,17) | +0,42 (p **0,005**) | +0,22 (p 0,10) |
| S07 G67 M30 | 965 | +0,40 (p 0,015) | +0,45 (p **0,009**) | +0,39 (p 0,015) | +0,45 (p **0,005**) | +0,41 (p **0,010**) |
| S07 G67 H1 | 585 | +0,33 (p 0,10) | +0,53 (p 0,015) | +0,31 (p 0,11) | +0,54 (p 0,012) | +0,33 (p 0,10) |
| S07 G67 H4 | 218 | +0,39 (p 0,21) | +0,92 (p 0,022) | +0,39 (p 0,21) | +0,92 (p 0,021) | +0,39 (p 0,21) |

So với VPS: cùng dấu ở mọi ô, cùng thứ tự các biến thể. "Gộp Chủ nhật" và "trễ 1 ngày" gần như bằng "server 00:00", còn UTC
và 42/167 đi cùng nhau. Số lệnh PC nhiều hơn vì dữ liệu dài hơn và khác feed.

Lệnh mua, train 07/2021–2023 (chỗ vênh). Ô: số chân / R cùng D1 so với số chân / R ngược D1:

| Sổ (PC) | server 00:00 (như EA) | SMA 42/167 |
|---|---|---|
| S07 M30 sổ G89 | 162 / +0,106 vs 131 / **+0,371** | 166 / **+0,265** vs 127 / +0,172 |
| S07 G67 M30 | 78 / +0,229 vs 58 / **+0,398** | 77 / **+0,339** vs 59 / +0,251 |
| S07 G67 H1 | 45 / +0,032 vs 35 / **+0,377** | 46 / **+0,280** vs 34 / +0,052 |
| S07 G67 H4 | 15 / −0,594 vs 10 / **+0,938** | 15 / **+0,265** vs 10 / −0,351 |

Các kỳ khác giống VPS: 06/2019–06/2021 mua ngược D1 âm (sổ G89: 34 chân −0,176); validate và test không có mua ngược D1; bán
ngược D1 ở validate âm (sổ G89 26 chân −0,358).

**Điều này bác bỏ giải thích ở bản sơ bộ.** Bản sơ bộ đoán G134/G135 trên PC thực chất ứng với SMA khoảng 42/167 vì dữ liệu PC
có 6 ngày/tuần. Thực tế dữ liệu PC có 5 ngày/tuần như Lirunex, và G134 (`d1_state`) đã tính đúng theo ngày server 50/200. Vì
vậy hai nguồn không vênh nhau. Cả hai cùng cho thấy cùng một điều: ở 07/2021–2023, dấu của bộ lọc với lệnh mua phụ thuộc
độ dài SMA.

**4. G134 phần 1 (× 0,5) có còn được ủng hộ khi D1 tính như EA không? — Có.** Biến thể (a) tái tạo đúng từng số của bảng
G134. Sổ S07 G89 có 1.266 chân, 1,5% × trọng số EA, lãi kép, vốn 10.000. Ô: %/năm / DD / **MAR** / số chân:

| D1 | Lệnh ngược D1 | Train 03/2018–2021 | Validate 2022–2025 | 2026 |
|---|---|---|---|---|
| (a) như G134 = nến D1 broker, 50/200 | × 1,0 | +16,7% / 32,5% / **0,52** / 461 | +122,5% / 19,2% / **6,39** / 699 | +134,0% / 9,6% / **13,89** / 89 |
| | × 0,5 | +24,1% / 23,9% / **1,01** / 461 | +111,1% / 17,0% / **6,53** / 699 | +95,7% / 6,3% / **15,24** / 89 |
| | × 0 | +31,4% / 22,8% / **1,38** / 301 | +98,0% / 17,5% / **5,61** / 549 | +59,9% / 9,7% / **6,15** / 44 |
| (b) gộp Chủ nhật vào thứ Hai | cả 3 dòng | giống hệt (a): không có nến Chủ nhật nào sau 2012, 0% chân đổi trạng thái | | |
| (c) SMA 42/167 | × 1,0 | **0,52** | **6,39** | **13,89** |
| | × 0,5 | +25,8% / 23,9% / **1,08** | +117,0% / 17,7% / **6,60** | +95,7% / 6,3% / **15,24** |
| | × 0 | +35,1% / 22,8% / **1,54** | +110,0% / 17,2% / **6,38** | +59,9% / 9,7% / **6,15** |

R mỗi chân, cùng / ngược D1, cách (a): train +0,320 (301) / −0,175 (160); validate +0,476 (549) / +0,283 (150); 2026
+0,699 (44) / +0,541 (45). Cách (c) đổi nhãn 5,1% số chân, cùng chiều, rõ hơn một chút ở validate (ngược D1 +0,169).

Luật chọn trước của G134 ("giữ × 0,5 nếu MAR không thấp hơn gốc ở kỳ nào") **đạt ở cả ba cách tính**. Riêng kỳ validate,
lợi thế nhỏ (6,53 so với 6,39) và đổi lấy %/năm thấp hơn (111% so với 122%). × 0,5 chủ yếu cắt sụt giảm; nó không làm sổ lãi
hơn ở 2022–2026.

## Kết luận

- **Luật D1 mà EA đang chạy (nến D1 broker, SMA 50/200, 5 nến/tuần) vẫn được dữ liệu PC ủng hộ theo đúng luật G134.** × 0,5 cho
  lệnh ngược D1 có MAR không thấp hơn gốc ở cả ba kỳ, với cả ba cách tính D1. Không cần đổi gì trong EA.
- Bản sơ bộ đúng ở điểm "bộ lọc không vững ở 07/2021–2023 với lệnh mua". PC cho kết quả y hệt. Ở đó, lệnh mua ngược D1
  (server 50/200) còn tốt hơn lệnh mua cùng D1. Lợi ích của × 0,5 trên sổ G89 đến từ 2018–2021 (ngược D1 −0,18R) và từ việc
  giảm DD, không đến từ 2021–2023.
- Không chọn lại tham số (không chuyển sang 42/167): đó là chọn sau khi nhìn. Mức tin cậy của bộ lọc D1 giữ như bản sơ bộ
  đề xuất: thấp–vừa. Nó là luật cắt rủi ro chứ không phải nguồn lợi nhuận.
- Về S07AS đứng độc lập (chỉ bán khi D1 death cross): việc này không nằm trong phạm vi G134 phần 1, chưa kiểm lại ở đây. Bán
  ngược D1 ở validate âm trên cả hai nguồn (sổ G89 PC −0,36R, 26 chân), không mâu thuẫn với điều kiện đó.
