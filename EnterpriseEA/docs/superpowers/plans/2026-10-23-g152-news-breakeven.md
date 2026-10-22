# G152: quy tắc hòa vốn trước tin (News Guard) trên sổ S07 — kế hoạch đăng ký trước (23/10/2026)

## Vì sao

G151 (so engine Python với tester MT5) cho thấy:
- trên 363 lệnh S07 khớp trong 02/2024 – 10/2026, khoảng 60R chênh đến từ quy tắc News Guard **dời SL về giá vào 15 phút trước tin USD khi lệnh
  đã lời ≥ 0,3R**;
- quy tắc này biến khoảng 19 lệnh +8R thành 0R.

EA live đang áp quy tắc này cho S07. G152 đo tác động thật trên toàn sổ S07, có các biến thể, để biết nên giữ, thu hẹp hay bỏ.

## Sổ và dữ liệu

- Sổ S07 M30 bản Python G89 (cả hai chiều, gốc / vào sớm / vào lại / bồi), 05/2018 → 06/2026; rủi ro như EA (1,5% × trọng số EA × 0,5 nếu
  ngược D1).
- Đường đi giá: nến M30 `data/m30v` (giờ server).
- Lịch tin: MT5 calendar (`research/calendar`, giờ server), USD mức HIGH.

## Biến thể

| Mã | Quy tắc |
|---|---|
| **V0** | không hòa vốn trước tin (= sổ nghiên cứu) |
| **V1** | **như EA hiện tại**: mọi tin USD HIGH, trừ danh sách bỏ qua của EA (Initial Jobless Claims, EIA Crude Oil, Lagarde Speech, CB Consumer Confidence, Durable Goods, Home Sales, S&P Global Services PMI, Note Auction, Money Stock). 15 phút trước tin, nếu lệnh đang lời ≥ 0,3R thì SL về giá vào (+ spread cho lệnh mua) |
| V2 | như V1 nhưng chỉ với **tin lớn**: Nonfarm Payrolls, CPI (mọi dòng CPI), Core PCE, Fed Interest Rate Decision, FOMC Press Conference |
| V3 | như V1 nhưng ngưỡng lời ≥ 2R (chỉ bảo vệ lệnh đã lời lớn) |

**Cách mô phỏng**:
- Với mỗi lệnh, tìm tin đầu tiên τ sao cho giá vào < τ − 15 phút < giá ra.
- Lãi tạm tính bằng giá đóng nến M30 cuối cùng đã đóng trước τ − 15 phút.
- Nếu đủ ngưỡng, SL về giá vào kể từ nến M30 bắt đầu ≥ τ − 15 phút.
- Nếu giá chạm giá vào trước lúc lệnh ra theo sổ gốc thì lệnh đóng ở giá vào; nếu không thì giữ kết quả gốc.
- Chi phí lệnh giữ như sổ gốc (cùng phần chi phí harsh).

## Kỳ

| Kỳ | Khoảng |
|---|---|
| chọn | 05/2018 – 2021 |
| kiểm | 2022 – 2023 |
| kiểm | 01/2024 – 06/2026 |

## Đạt khi

Câu hỏi chính (**1 ô**): **bỏ quy tắc (V0) có tốt hơn quy tắc hiện tại (V1) không?**

V0 "đạt", nghĩa là đề xuất bỏ hòa vốn trước tin cho S07, khi cùng đúng:
1. tổng R của V0 > V1 ở cả ba kỳ;
2. MAR (mô phỏng vốn G134) V0 ≥ V1 ở cả ba kỳ;
3. DD p90 một năm của V0 không cao hơn V1 quá 3 điểm %;
4. bootstrap ghép cặp theo lệnh (chênh R V0 − V1, 2.000 lần, gộp ba kỳ) p ≤ 0,05.

V2 và V3 chỉ báo cáo, không quyết định. Nếu V0 không đạt nhưng V2 hoặc V3 tốt hơn V1 ở cả ba kỳ, ghi làm gợi ý cho bước sau.

Báo thêm:
- số lệnh bị dời SL;
- trong số đó, bao nhiêu lệnh được cứu (gốc âm thành 0) và bao nhiêu lệnh bị cắt lãi (gốc dương lớn thành 0);
- kết quả theo năm.

## Nếu đạt

Đề xuất đổi mặc định quy tắc hòa vốn trước tin cho S07 (input riêng). Người dùng đồng ý mới đổi; không nạp EA trong G152.

Script `research/long/g152_news_breakeven.py`. Không chỉnh luật sau khi chạy.
