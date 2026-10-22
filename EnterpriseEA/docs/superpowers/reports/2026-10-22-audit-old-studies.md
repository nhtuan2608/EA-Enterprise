# Kiểm lại các nghiên cứu cũ đứng sau EA (22/10/2026)

Người dùng hỏi: các kết luận "đã thử, không đạt / đạt" có chắc không. Bước 1 là kiểm lại có chọn lọc các nghiên cứu đứng sau những
gì **đang chạy trong EA**:
- chạy lại trên dữ liệu PC hiện tại với đúng luật cũ;
- so với báo cáo gốc;
- kiểm lỗi dữ liệu và độ phụ thuộc vào vài lệnh cực lớn ("bỏ 3 lệnh lớn nhất").

Script: [`audit_g89.py`](../../research/long/audit_g89.py), còn lại chạy các script gốc (`discovery.py`, `g96_regime.py`,
`g107_portfolio.ctx_legs`).

## A. Độ toàn vẹn dữ liệu

Đếm nến theo năm ở mọi file M15/M30/H1/H4 (bộ export gốc và `research/long/data`):

| Nhóm | Dữ liệu trong ngày thật từ | Ghi chú |
|---|---|---|
| **XAUUSD M30/H1/H4** (`m30v`, `h1v`, `h4v`, export gốc) | **19/03/2018** | 2010–2017 chỉ là nến D1, spread 0 |
| XAUUSD M15 / M5 | 07/2021 / 05/2024 | |
| EURUSD, GBPUSD, USDJPY H1/H4 | 2010 | thật |
| BTCUSD H1/H4 | 2018 | |
| Các cặp còn lại, bạc, dầu, chỉ số, US10Y | 2024 | DXY từ 09/2021 |
| `bars_XAUUSD_*` (dùng ở G36–G41) | 2018 | bộ chuyển đổi đã bỏ phần nến D1 giả |

Nghiên cứu bị ảnh hưởng:
- **G89** (sổ S07 M30 từ 10/2016): 15 lệnh 2016–2017 chạy trên nến D1. Rất nhỏ so với 1.249 lệnh sau đó.
- **G140** (vô hiệu, đã ghi).
- Các kỳ "sớm" trước 03/2018 trên khung trong ngày.

T2 (G38) được chọn trên FX 2010–2016, là dữ liệu thật, nên **không bị ảnh hưởng**.

## B. S07 M30 (G89), lõi của EA

| Năm | Lệnh | R theo trọng số (báo cáo cũ → chạy lại) | Bỏ 3 lệnh lớn nhất | Mua / Bán |
|---|---|---|---|---|
| 2018 | 63 | +3,7 → +1,4 | −12,4 | −4,6 / +6,1 |
| 2019 | 131 | +13,2 → +17,1 | −3,9 | +19,8 / −2,7 |
| 2020 | 163 | +39,7 → +38,3 | +19,1 | +43,5 / −5,2 |
| 2021 | 104 | −1,4 → −4,4 | −20,1 | −16,8 / +12,4 |
| 2022 | 124 | +26,3 → +32,2 | +8,4 | +32,6 / −0,4 |
| 2023 | 138 | +43,1 → +36,4 | +12,5 | +40,1 / −3,7 |
| 2024 | 189 | +96,3 → +96,3 | +72,5 | +100,6 / −4,4 |
| 2025 | 248 | +78,1 → +78,1 | +57,9 | +84,7 / −6,6 |
| 2026 | 89 | +48,0 → +48,0 | +24,0 | +30,2 / +17,7 |

- **Tái tạo**: 2024–2026 khớp đúng từng số. 2018–2023 lệch vài R, do các bản sửa code sau G89 (lỗi giờ UTC ở G125). Chiều kết luận không
  đổi.
- **Không phụ thuộc vài lệnh**: từ 19/03/2018 có 1.249 lệnh, +343R. 10 lệnh lớn nhất chiếm 23%; bỏ chúng còn **+264R**. Khác hẳn ứng
  viên nến V (G141, 1 nhóm chiếm 40%).
- **Nhưng lợi thế phụ thuộc chu kỳ**:
  - 2018–2021 gần như hòa (+52R trong 4 năm, chủ yếu 2020);
  - bỏ 3 lệnh lớn nhất thì 2018, 2019, 2021 âm;
  - lãi đến từ **lệnh mua** 2020 và 2022–2026. Lệnh bán quanh 0 (S07S −0,27R/lệnh trên 27 lệnh).

## C. T2 (Donchian H4 60 + phía EMA200 D1), LIVE cho XAU và BTC

| Symbol | Lệnh | R/lệnh (G38 → chạy lại) | Bỏ 3 lệnh lớn nhất | Năm âm |
|---|---|---|---|---|
| XAUUSD (2018–2025) | 122 | +0,44 → **+0,445** | +0,21 | 2021 (−0,15), 2022 (−0,29) |
| BTCUSD (2018–2025) | 121 | +0,84 → **+0,858** | +0,52 | không |
| EURUSD / GBPUSD / USDJPY (2010–2025) | 264 / 265 / 265 | −0,04 / +0,06 / +0,13 → **−0,038 / +0,063 / +0,130** | −0,13 / −0,04 / +0,02 | nhiều |

Tái tạo khớp. Quyết định chỉ LIVE trên XAU và BTC có căn cứ. Trên vàng, phần lãi vẫn nghiêng về các năm tăng.

## D. XauRegime (G96), bot XRT

| | Train 2010–17 | Validate 2018–21 | Test 2022–06/2026 | 07/2026+ |
|---|---|---|---|---|
| Sharpe (báo cáo → chạy lại) | 0,56 → **0,56** | 0,77 → **0,77** | 1,26 → **1,26** | −0,67 |

- Tái tạo khớp, dùng file D1 thật nên không bị lỗi dữ liệu.
- **Cần nói rõ: G96 KHÔNG ĐẠT theo luật của chính nó** (p hoán vị 0,21 validate / 0,12 test). Bot XRT đang chạy dựa trên một kết quả
  chưa đạt. Nó chỉ mua, nên lãi chủ yếu nhờ vàng tăng; Sharpe 07/2026+ là −0,67.

## E. CtxLimit (MKT04 "vàng L" + cổng S07, như bot)

| Năm | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| Lệnh / R | 97 / +0,02 | 49 / **−0,29** | 39 / +0,09 | 36 / +0,11 | 71 / **−0,06** | 101 / **+0,54** | 21 / +0,40 |

- 2020–09/2025: +0,075R/lệnh (366 lệnh). 10/2025+: +0,55R (48 lệnh). Bỏ 3 lệnh lớn nhất: +0,12R. 94% lệnh mua.
- Khớp cảnh báo của báo cáo gốc: lợi thế mỏng, tập trung vào 2025.

## F. Đã kiểm trong các phiên trước, không chạy lại ở đây

- **G134 trọng số D1 × 0,5**: tái tạo đúng từng số (G138 PC), đạt ở cả 3 cách tính D1.
- **VHedge G119** (bot scalp): các quý 2026 trên vàng, ngoài mẫu, vẫn dương (+0,43 / +0,38 / +1,40U), kể cả khi bỏ 2 nhóm lớn nhất (G145).

## Kết luận

| Thành phần EA | Tái tạo được | Lỗi dữ liệu | Phụ thuộc vài lệnh | Phụ thuộc chu kỳ vàng tăng |
|---|---|---|---|---|
| S07 M30 | có (2024–26 khớp tuyệt đối) | nhỏ (15 lệnh 2017) | không | **có** (2018–21 ≈ hòa, lãi từ lệnh mua) |
| D1 × 0,5 | có | không | không | — |
| T2 XAU/BTC | có | không | XAU vừa phải, BTC không | XAU có (2021–22 âm) |
| XRT | có | không | — | **có**, và **G96 chưa đạt luật của nó** |
| CtxLimit | có | không | vừa phải | **có** (lãi tập trung 2025) |
| VHedge | có (ngoài mẫu 2026 dương) | không | không | dữ liệu chỉ 2024–2026 |

1. **Các nghiên cứu cũ tái tạo được.** Không tìm thấy lỗi nhìn trước mới. Lỗi dữ liệu trước 03/2018 chỉ ảnh hưởng một phần nhỏ.
2. **Kết luận "chưa có setup mới nào đạt" vẫn đứng.** Nhưng phải đọc đúng: đó là "chưa tìm thấy", không phải "không tồn tại".
3. **Mới so với trước**: gần như mọi bot đang chạy cũng **kiếm phần lớn lợi nhuận từ lệnh mua trong chu kỳ vàng tăng**. Nếu vàng chuyển
   sang đi ngang hoặc giảm nhiều năm như 2013–2018, kỳ vọng nên thấp hơn nhiều so với kết quả 2022–2026. XRT (chỉ mua, G96 chưa đạt) và
   CtxLimit (94% mua) chịu rủi ro này nhiều nhất.
4. Gợi ý vận hành (người dùng quyết định): giữ rủi ro mỗi bot ở mức chịu được trong một năm đi ngang; theo dõi `/botlog` theo tháng; nếu
   XRT hoặc CtxLimit âm 2–3 tháng liên tiếp khi vàng không còn tăng thì cân nhắc chuyển về SHADOW.
