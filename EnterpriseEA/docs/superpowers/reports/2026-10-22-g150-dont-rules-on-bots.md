# G150 — quy luật "đừng làm" làm bộ lọc cho bot đang chạy (22/10/2026)

Kế hoạch đăng ký trước: [2026-10-22-g150-dont-rules-on-bots.md](../plans/2026-10-22-g150-dont-rules-on-bots.md). Script
[`g150_dont_rules.py`](../../research/long/g150_dont_rules.py). Δ = R/lệnh của lệnh dính quy luật − lệnh không dính.

## S07 M30 (1.266 chân, 05/2018 → 2026)

| Quy luật | Tỷ lệ dính | Δ 2018–21 / 2022–23 / 2024–26 | Theo năm | Kết luận |
|---|---|---|---|---|
| D1 ATR thấp | 24% | −0,57 / −0,11 / −0,11 | 2018 +0,98, 2021 +0,08 dương | không thành ứng viên (chỉ 2/4 năm âm) |
| D2 sát EMA200 D1 | 11% | +0,14 / +0,64 / — | | ngược giả thuyết: S07 vào sát EMA200 D1 lại **tốt hơn** |
| D3 giờ 01 / 15–17 | 24% | **+0,29 / +0,48 / +0,24** | | ngược giả thuyết: S07 vào lúc mở cửa Mỹ **tốt hơn** |
| D4 đuổi phá biên Á | 11% | +0,28 / −0,24 / +0,04 | đổi dấu | không thành ứng viên |
| D5 bắt về VWAP | 0,2% | — | | S07 gần như không bao giờ vào kiểu này |

→ **Không quy luật nào lọc được S07.** Hai quy luật còn cho thấy điều ngược lại: S07 là lệnh đà sau nén, nên những thời điểm "nguy hiểm"
với lệnh ngẫu nhiên (mở cửa Mỹ, sát EMA200 D1) lại là lúc đà bung ra.

## T2 XAU (122 lệnh, H4)

| Quy luật | Tỷ lệ dính | Δ 2018–21 / 2022–23 / 2024–26 | MAR mốc → biến thể (3 kỳ) | p | Kết luận |
|---|---|---|---|---|---|
| D2 sát EMA200 D1 | 13% | −1,72 / +0,04 / — | 0,70→1,17; 0,37→0,35; = | 0,037 | KHÔNG ĐẠT (2022–23 dương) |
| **D3 vào ở nến H4 đóng 16:00 server** | 22% | **−1,57 / −0,68 / −0,68** | 0,70→1,12; 0,37→0,51; 2,61→2,85 | **0,012** | **KHÔNG ĐẠT, nhưng gần nhất** (âm 7/8 năm, MAR tốt hơn ở cả 3 kỳ; p chưa tới 0,005) |
| D4 đuổi phá biên Á | 12% | −1,54 / −0,57 / −0,66 | 0,70→0,77; 0,37→0,51; 2,61→2,45 | 0,091 | KHÔNG ĐẠT |
| D1 / D5 | 5% / 0% | | | | không thành ứng viên |

Với T2, nến H4 đóng lúc 00 / 04 / 08 / 12 / 16 / 20 giờ server, nên D3 chỉ trùng **nến 12:00–16:00**. Nến này chứa giờ ra tin Mỹ 15:30. Lệnh
phá Donchian H4 kích hoạt bởi cú giật lúc tin Mỹ hay bị kéo ngược: −1,6 / −0,7 / −0,7R so với các lệnh khác. Điều này khớp với Q7 (đỉnh /
đáy ngày hay hình thành 15–17 giờ). **Có cơ chế hợp lý và ổn định, nhưng chỉ 27 lệnh dính, p 0,012, chưa qua ngưỡng 0,005 của 10 ô.**

## VHedge G119 (báo cáo, 323 nhóm 2024–2026)

ATR thấp +0,23U, giờ 01 / 15–17 +0,18U (tốt hơn). Không dùng được làm bộ lọc tránh.

## Kết luận

1. Không quy luật "đừng làm" nào đạt luật làm bộ lọc cho bot. **Quy luật tránh của lệnh ngẫu nhiên không chuyển được sang bot có lợi thế**:
   S07 và VHedge lại tốt hơn đúng ở những chỗ lệnh ngẫu nhiên tệ.
2. Ứng viên duy nhất đáng theo dõi: **T2 bỏ (hoặc giảm rủi ro) lệnh phá vỡ từ nến H4 đóng 16:00 server** (nến chứa tin Mỹ). Âm 7/8 năm, MAR
   tốt hơn cả ba kỳ, p 0,012. Đề xuất ghi nhãn giờ nến tín hiệu vào nhật ký lệnh T2 và kiểm lại bằng dữ liệu forward. Không đổi EA khi
   chưa có thêm bằng chứng và chưa có đồng ý của người dùng.
