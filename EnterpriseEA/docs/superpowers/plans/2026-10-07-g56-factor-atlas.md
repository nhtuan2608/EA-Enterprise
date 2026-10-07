# G56: bản đồ yếu tố lặp lại (khung giờ, giá tròn, phiên, chuỗi nến, biên sideway, wedge, thứ trong tuần, indicator) — kế hoạch đăng ký trước

Ngày 07/10/2026. Người dùng: tìm yếu tố lặp lại thường xuyên (khung giờ, tròn giá, giao phiên, chuỗi liên tiếp có sức ép,
biên sideway, breakout wedge, thứ 6 / thứ 2 đỏ, …) phối hợp indicator, để dựng setup SCALP và SWING lặp lại qua
walk-forward; quản lý lệnh nên giãn TP / giữ xa khi phù hợp, kể cả SCALP. Chỉ dữ liệu MT5.

Ghi trước khi chạy bất kỳ con số nào của nghiên cứu này. Thử nhiều yếu tố thì sẽ có yếu tố "thắng" do may rủi; kế hoạch
này giới hạn điều đó bằng: chọn chỉ trên giai đoạn train, kiểm soát tỉ lệ phát hiện sai (Benjamini–Hochberg), rồi bắt
buộc cùng dấu ở validate và test, và cuối cùng mới dựng setup, đo walk-forward và so với vào lệnh ngẫu nhiên.

## Dữ liệu

| Khung | Symbol | Train | Validate | Test |
|---|---|---|---|---|
| H1 (SWING) | EURUSD, GBPUSD, USDJPY 2010–2025; XAUUSD, BTCUSD 2018–2025 | 2010–2016 | 2017–2020 | 2021–2025 |
| M15 (SCALP) | EURUSD, GBPUSD, USDJPY, XAUUSD (2022–2025), BTCUSD (2023–2025) | 2022–2023 | 2024 | 2025 |

Nguồn: export MT5 thô (`input/raw`, chỉ đọc) → `research/long/data` (`convert_raw.py --tf M15,M30`).

## Giai đoạn A — bản đồ yếu tố (`research/long/factor_atlas.py`)

Mỗi yếu tố là một sự kiện ở lúc đóng nến i kèm hướng giả thuyết d. Đo lợi nhuận tiến d·(close[i+k] − close[i]) / ATR14[i]
ở các tầm k (H1: 1, 4, 12, 24 nến; M15: 2, 8, 24 nến), trừ trôi giá trung bình của symbol trong giai đoạn (để giờ / thứ
không bị lẫn với xu hướng dài). Kiểm hai phía: dấu âm nghĩa là chiều ngược lại của giả thuyết.

Yếu tố (H1 và M15 như nhau trừ khi ghi khác):
1. HOUR_h — mỗi giờ UTC (24), d = mua.
2. Thứ trong tuần (H1, tầm 24): MON, FRI (d = mua); MON_AFTER_RED_FRI (thứ 2 sau thứ 6 đỏ, d = ngược thân nến thứ 6);
   FRI_FADE_WEEK (thứ 6, d = ngược chiều thứ 2→thứ 5); MON_GAP_FILL (gap đầu tuần ≥ 0,3 ATR, d = về giá đóng thứ 6).
3. Phiên: ASIA_BREAK (07–10 UTC, đóng nến vượt biên phiên Á 00–07, d = chiều phá); NY_FADE_16 (nến 16 UTC, d = ngược
   chiều 07→16); OVERLAP_MOM (12–16 UTC, d = chiều nến trước).
4. Giá tròn (FX 100 pip, JPY 1,00, XAU 10, BTC 1.000): ROUND_REJECT (chạm mức tròn rồi đóng lại phía cũ, d = bật lại);
   ROUND_BREAK (đóng vượt mức tròn, d = theo chiều phá).
5. Chuỗi: STREAK_n (n = 4, 5, 6 nến cùng màu, d = tiếp diễn); PRESSURE_n (n = 3, 4 nến đóng ở 25% trên/dưới của biên
   độ, biên độ ≥ 0,5 ATR, d = tiếp diễn).
6. Biên sideway: hộp 24 nến rộng ≤ 2 ATR; RANGE_BREAK (đóng ngoài hộp, d = theo chiều phá); RANGE_FADE (chạm biên,
   đóng trong hộp, d = ngược biên).
7. Wedge (30 nến, hồi quy đỉnh và đáy): RISING_WEDGE_BREAK (đáy dốc lên nhanh hơn đỉnh, đóng dưới đường đáy, d = bán);
   FALLING_WEDGE_BREAK (đối xứng, d = mua).
8. PDHL_SWEEP — vượt đỉnh/đáy ngày trước rồi đóng lại trong, d = ngược.
9. Indicator: RSI_REVERT (RSI14 cắt lại lên 30 / xuống 70, d = hồi); BB_SQUEEZE_BREAK (độ rộng BB20 dưới 10% của 120 nến,
   đóng ngoài dải, d = theo chiều phá); MACD_FLIP_TREND (histogram đổi dấu cùng phía EMA200, d = theo); ADX_PULLBACK
   (ADX > 25, EMA20 > EMA50, râu chạm EMA20 và đóng trên, d = theo xu hướng; đối xứng); NR7_BREAK (nến trước hẹp nhất
   7 nến, nến này phá, d = theo); VOL_SPIKE (H1: tick volume > 2,5× TB 24 nến, d = chiều nến).
10. MONTH_END_FIX (H1, ngày giao dịch cuối tháng, nến 15–16 UTC, d = mua, kiểm hai phía).

Thống kê: trung bình theo cụm (symbol × ngày) để không đếm lặp các sự kiện cùng ngày; t-test trên trung bình cụm; p hai
phía. Gộp các symbol (đơn vị ATR) để có đủ mẫu.

**Tiêu chí chọn (chỉ trên train):** q Benjamini–Hochberg < 0,10 trên toàn bộ phép thử của khung đó; |hiệu ứng| ≥ 0,05 ATR;
cùng dấu ở ≥ 60% symbol có ≥ 30 sự kiện.

**Tiêu chí sống sót:** validate cùng dấu với p một phía < 0,10; test cùng dấu (trung bình > 0 theo hướng đã chọn); và
sau chi phí (spread + phí, đơn vị ATR) vẫn dương ở tầm đã chọn trong validate và test.

## Giai đoạn B — dựng setup (sau khi audit A)

Chỉ dùng yếu tố sống sót, có thể phối hợp tối đa 2 yếu tố (chỉ cặp có lý do, ghi trước). Vào lệnh ở giá đóng, dừng lỗ theo
ATR hoặc cấu trúc, quản lý như Trade Manager của profile. Walk-forward: chọn tham số trên các năm trước, kiểm trên năm kế
(H1: cửa sổ 4 năm → 1 năm, 2014–2025; M15: 2022–23 → 2024, 2022–24 → 2025). So với vào lệnh ngẫu nhiên cùng giờ, cùng
chiều phân bố (p90). Đạt khi walk-forward dương sau phí ở ≥ 70% năm kiểm và vượt p90 ngẫu nhiên.

## Giai đoạn C — giãn TP / giữ xa (kể cả SCALP)

Trên setup đạt B: so TP cố định, TP rộng (2R/3R), runner (chốt một phần + trail ATR/cấu trúc), thoát theo thời gian;
chọn trên train, kiểm validate/test như trên. Chỉ nới TP khi trung bình và drawdown đều không xấu đi ngoài mẫu.

## Không làm

Không chỉnh tham số yếu tố sau khi thấy validate/test; không thêm yếu tố mới vào lần chạy này (yếu tố mới = kế hoạch mới).
Kết quả nào cũng báo cáo, kể cả khi không yếu tố nào sống sót.
