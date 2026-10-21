# G140–G144 — tìm setup mới / nâng cấp bot cho swing và scalp (22/10/2026)

Mục tiêu người dùng đặt: thêm 1–2 setup (hoặc nâng cấp bot) có hiệu suất tốt cho swing và scalp. Mỗi phép thử dưới đây có kế hoạch
**đăng ký trước** (commit trước khi chạy), luật cố định, kiểm ngoài mẫu hoặc đối chứng ngẫu nhiên.

| Mã | Kế hoạch | Ứng viên | Loại | Kết luận theo luật |
|---|---|---|---|---|
| G140 | [plan](../plans/2026-10-22-g140-holdout-2010-2017.md) | nến V M30 (G118 A) và S07 H1 cùng D1, kiểm trên 2010–2017 | scalp + swing | **VÔ HIỆU** (lỗi dữ liệu, xem dưới) |
| G141 | [plan](../plans/2026-10-22-g141-v-candle-silver.md) | nến V M30 (G118 A) chuyển nguyên văn sang bạc | scalp / trong ngày | **KHÔNG ĐẠT** |
| G142 | [plan](../plans/2026-10-22-g142-s07-d1-swing.md) | S07 trên nến D1, 2011–2026 | swing | **KHÔNG ĐẠT** |
| G143 | [plan](../plans/2026-10-22-g143-session-momentum.md) | động lượng giờ đầu phiên New York / London | scalp / trong ngày | **KHÔNG ĐẠT** |
| G144 | [plan](../plans/2026-10-22-g144-ny-momentum-holdout.md) | G143 NY, nguyên văn, trên 03/2018–07/2021 chưa nhìn | scalp / trong ngày | **KHÔNG ĐẠT** |

## Phát hiện dữ liệu quan trọng (G140)

`research/long/data/{m30v,h1v,h4v}/XAUUSD.csv` và bộ export gốc (`input/raw/XAUUSD`) **chỉ có nến D1 trước 19/03/2018**:
- 2010–2017 có khoảng 260–310 nến mỗi năm, mỗi ngày một nến lúc 00:00, spread 0;
- nến M30/H1/H4 thật bắt đầu từ 19/03/2018.

Hệ quả:
- G140 (kiểm M30/H1 trên 2010–2017) vô hiệu: chỉ có 1 nhóm nến V và 20 lệnh H1, vì chạy trên nến D1.
- Những nghiên cứu cũ có kỳ trước 03/2018 trên khung trong ngày thực chất chạy trên nến D1 ở phần đó. Ví dụ: sổ G89 từ 10/2016,
  "Train 03/2018–2021" của G134 có 2 tuần đầu. Ảnh hưởng nhỏ vì số lệnh ở phần đó rất ít, nhưng cần nhớ khi đọc các bảng "10 năm".
- Nến **D1** 2010–2026 là thật. G142 dùng phần này.

## G141 — nến V M30 (G118 A) trên bạc

Luật nguyên văn (bối cảnh A, hedge G116, stop ± 2 ATR). Nến M30 bạc gộp từ M15, 03/2024–10/2026.

| | Nhóm | U/nhóm |
|---|---|---|
| **XAGUSD (quyết định)** | 56 | **−0,141** (trước 06/2025 −0,239; từ 06/2025 −0,079) |
| XAGUSD phí × 1,5 | 56 | −0,231 |
| XAUUSD cùng khoảng (so sánh) | 66 | +0,073 (2024 −0,33; 2025 +0,55; 2026 +0,21) |

- p đối chứng (bạc) 0,91. **KHÔNG ĐẠT.**
- **Phát hiện phụ**: trên vàng, nhóm ngày 29/02/2024 cho **+35,1U** một mình. Nó trùng đúng lúc vàng bắt đầu nhịp tăng tháng 3/2024
  và chiếm khoảng 40% tổng lãi 2018–2026 của ứng viên A (86,7U trên 200 nhóm). Bỏ nhóm đó đi thì 2024 là −0,33U/nhóm. Lợi thế của
  ứng viên A dựa vào đuôi cực trị, không bền.
- **Không đề xuất** hồ sơ M30 cho VHedge.

## G142 — S07 trên D1 (swing)

Nến D1: trước 19/03/2018 là nến D1 gốc (2.169 nến), sau đó gộp từ H1. S07 G67 (nén 8 nến, B6, E2X + TP 8, nghỉ 4, giữ ≤ 120 nến).

| Kỳ | Lệnh | R/lệnh | Mua | Bán |
|---|---|---|---|---|
| A 2011–2017 | 27 | **−0,125** | 11 / −0,538 | 16 / +0,159 |
| B 2018–2021 | 15 | +0,471 | 10 / +0,814 | 5 / −0,214 |
| C 2022–06/2026 | 14 | +1,506 | 13 / +1,595 | 1 / +0,350 |

p đối chứng 0,13. **KHÔNG ĐẠT.** Kỳ A âm (vàng đi ngang và giảm 2011–2017). Phần dương chỉ có trong chu kỳ tăng 2018–2026, gần như
toàn lệnh mua. Lại cùng một hình ảnh: lợi thế bám theo chu kỳ tăng của vàng.

## G143 — động lượng trong phiên (M15, 07/2021–2026)

| Ô | Train | Validate | Test | p đối chứng | Kết luận |
|---|---|---|---|---|---|
| NY (15:30 → 16:30, vào 16:30, ra 20:30 server) | 66 / +0,195 | 28 / −0,011 | 10 / +0,279 | **0,010** | KHÔNG ĐẠT (validate ≈ 0, < 40 lệnh/kỳ) |
| London (10:00 → 11:00, vào 11:00, ra 15:15) | 7 / −0,195 | 2 / −0,499 | 3 / +0,867 | 0,91 | KHÔNG ĐẠT |

Ô NY thắng đối chứng "cùng ngày, cùng chiều" ở train + validate, nên được kiểm tiếp ngoài mẫu ở G144.

## G144 — NY ngoài mẫu (M30, 03/2018–07/2021, chưa từng nhìn)

| Kỳ | Lệnh | R/lệnh |
|---|---|---|
| 03/2018–12/2019 | 28 | −0,137 |
| 01/2020–07/2021 | 28 | −0,176 |
| **Ngoài mẫu gộp** | 56 | **−0,156** (phí × 1,5: −0,174) |
| 07/2021–2023 / validate / test (cùng luật, M30) | 67 / 28 / 10 | +0,197 / −0,011 / +0,279 |

- p đối chứng ngoài mẫu 0,88. **KHÔNG ĐẠT.**
- Bản M30 cho lại đúng số của G143 (M15) trên 07/2021+, nên code nhất quán. Động lượng phiên NY chỉ là hiện tượng của 2021–2023.
- Theo năm: 2018–2020 âm, 2021–2023 dương, 2024–2026 quanh 0.

## Kết luận chung

**Không có setup mới hay nâng cấp nào qua được luật đăng ký trước** trong G140–G144. Cùng với G136, G137, G139, mọi hướng còn lại
trong dữ liệu MT5 hiện có đều đã được kiểm.

Ba quan sát nhất quán:
1. **Mọi "lợi thế" mới trên vàng chỉ xuất hiện trong chu kỳ tăng 2018–2026 hoặc trong một giai đoạn con.** Khi có dữ liệu ngoài kỳ đó
   hoặc thị trường khác, chúng mất:
   - S07 D1 âm ở 2011–2017;
   - nến V âm trên bạc;
   - NY momentum âm ở 2018–2021.
2. **Một vài kết quả lớn đến từ đuôi cực trị.** Ví dụ nhóm +35U của ứng viên A. Bảng R trung bình che mất điều này. Từ nay nên báo kèm
   kết quả khi bỏ 1–2 nhóm/lệnh lớn nhất.
3. **Dữ liệu trong ngày chỉ có từ 03/2018**, toàn bộ nằm trong một chu kỳ vàng tăng mạnh. Không còn kỳ kín nào để xác nhận setup
   trong ngày. Chỉ còn dữ liệu forward.

## Đề xuất thay cho setup mới

- **Không thêm setup vào EA.** Các bot đang chạy (S07, VHedge G119, XauRegime, CtxLimit) là những gì có bằng chứng tốt nhất hiện có.
  Ngay cả chúng cũng có phần lớn lợi nhuận trong chu kỳ tăng, nên giữ rủi ro ở mức có thể chịu được nếu chu kỳ đổi.
- **Theo dõi forward** bằng nhật ký bot (`logs/bots-*.jsonl`, `/botlog`) và so với nghiên cứu. Nếu cần một ứng viên để chạy SHADOW
  thuần thu thập dữ liệu (không có căn cứ để LIVE), NY momentum (G143) là ứng viên duy nhất từng thắng đối chứng. Nhưng nó đã thua
  ngoài mẫu, nên chỉ nên chạy nếu muốn thêm dữ liệu.
- **Nếu muốn nghiên cứu tiếp**, cần **nguồn dữ liệu mới**: nến M30/H1 vàng trước 2018 từ broker khác, hoặc tick lịch sử dài hơn. Đây
  là điều kiện để có kỳ kiểm mà chu kỳ thị trường khác 2018–2026. Theo memory, nghiên cứu chỉ dùng dữ liệu MT5. Nếu người dùng có
  terminal / broker khác lưu lịch sử M30 từ 2010, đó là bước có giá trị nhất.
