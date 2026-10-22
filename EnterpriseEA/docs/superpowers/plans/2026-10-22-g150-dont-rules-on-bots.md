# G150: các quy luật "đừng làm" (G147–G149) làm bộ lọc cho các bot đang chạy — kế hoạch đăng ký trước (22/10/2026)

## Vì sao

G147–G149 không tìm ra điểm vào mới. Nhưng tìm ra vài quy luật **ổn định 8–9 năm** về chỗ nên tránh. Người dùng (22/10): chưa nạp EA, tiếp
tục nghiên cứu và lọc. Câu hỏi của G150: các quy luật đó có **giảm lệnh thua cho bot đang chạy** mà không giảm lợi nhuận tương ứng không?

## Quy luật kiểm (tính tại nến M30 cuối cùng đã đóng trước lúc vào lệnh)

| Mã | Quy luật "đừng làm" | Nguồn |
|---|---|---|
| D1 | ATR14 M30 < 0,8 × trung bình 100 nến (thị trường lặng) | G147, G148 |
| D2 | giá cách EMA200 D1 ≤ 1 ATR20 D1 (sát EMA200 D1) | G148 (7/8 ô) |
| D3 | vào lệnh trong giờ server 01, 15, 16, 17 (giờ đỉnh / đáy ngày hay hình thành) | G149 Q7 |
| D4 | vào theo chiều phá biên phiên Á trong 09–14 giờ server, khi giá đang ngoài biên Á phía đó (đuổi cú phá biên Á) | G149 Q3 |
| D5 | vào **ngược** hướng giá đang cách VWAP ngày ≥ 1,5 ATR (bắt giá quay về VWAP) | G149 Q4 |

## Sổ lệnh

- **S07 M30** — sổ G89 (bản Python của S07Tester, cả hai chiều, gồm vào sớm / vào lại / bồi), 05/2018 → 06/2026. Rủi ro như EA hiện tại:
  1,5% × trọng số EA × 0,5 nếu ngược D1 (G134).
- **T2 XAU** — Donchian H4 60 + phía EMA200 D1 (G38, bộ `n 60, stop 2, trail 3, d1`), 2018 → 10/2025 (hết dữ liệu `bars_`).
- **VHedge G119** — nhóm hedge vàng M5 (05/2024 → 10/2026). Không có kỳ chọn riêng (dữ liệu chỉ từ 2024), nên **chỉ báo cáo**.

## Cách chọn và kiểm (S07, T2)

| Kỳ | Khoảng | Dùng để |
|---|---|---|
| chọn | 05/2018 – 12/2021 | chọn |
| kiểm | 2022 – 2023 và 01/2024 – 06/2026 | kiểm |

1. Với mỗi quy luật Dk và mỗi sổ: Δ = R/lệnh của lệnh dính Dk − R/lệnh của lệnh không dính. Tính theo **năm** của kỳ chọn (2018*, 2019,
   2020, 2021), gộp hai chiều.
2. **Ứng viên lọc** nếu Δ < 0 ở ≥ 3 / 4 năm, Δ gộp kỳ chọn ≤ −0,10R, và Dk chiếm 5–40% số lệnh.
3. Với mỗi ứng viên, biến thể = lệnh dính Dk chỉ dùng **× 0,5 rủi ro** (như G134; không bỏ hẳn).
4. **Đạt** (mỗi sổ × quy luật là một ô; tối đa 10 ô, nên p ≤ 0,005):
   - Δ < 0 ở cả 2022–2023 và 2024–06/2026;
   - MAR của biến thể ≥ mốc ở cả ba kỳ (chọn, 2022–23, 2024–26), tính bằng mô phỏng vốn G134 (lãi kép, vốn 10.000);
   - hoán vị nhãn Dk (2.000 lần, gộp ba kỳ): p ≤ 0,005.

Báo thêm: tỷ lệ lệnh dính từng quy luật, Δ theo năm cho cả 5 quy luật và 3 sổ, kể cả những quy luật không thành ứng viên.

## Nếu đạt

Đề xuất thêm hệ số rủi ro × 0,5 cho lệnh của bot dính quy luật đó, input riêng, **mặc định tắt**. Người dùng đồng ý mới bật. Không nạp lên EA
trong G150.

Script `research/long/g150_dont_rules.py`. Không chỉnh luật sau khi chạy.
