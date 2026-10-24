# G157: FX và BTC — phá giả / đi tiếp và các tình huống có tên có đoán được không — kế hoạch đăng ký trước (24/10/2026)

## Vì sao

G156a2–G156c trên vàng: với thông tin trong giá, phá giả hay đi tiếp gần như tung đồng xu, và 12 tình huống có tên không báo trước hướng.
Người dùng (24/10): phải phân tích được **FX và BTCUSD**; nếu hợp lý và đúng thì vẫn trade.

Mỗi thị trường có cấu trúc riêng (FX hay quay về trong ngày, BTC chạy 24/7 và có xu hướng mạnh), nên phải đo riêng. G157 dùng **y nguyên**
cách đo của G156a2 / G156b / G156c, đổi sang H1 để có lịch sử dài.

Bước này chỉ trả lời "có đoán được hướng hơn tung đồng xu không". **Không có chi phí, không phải setup.** Phát hiện nào đạt phải qua một
kế hoạch setup riêng (có phí, kỳ chưa dùng, đối chứng ngẫu nhiên) trước khi trade.

## Thị trường, dữ liệu, kỳ

Nến **H1** (`data/h1v`, giờ server).

| Thị trường | Dữ liệu | Kỳ cho tình huống | Mỏ neo: năm chọn / năm kiểm |
|---|---|---|---|
| EURUSD, GBPUSD, USDJPY | 01/2010 → 10/2026 | 2011–2015 / 2016–2020 / 2021–06/2026 | 2013–2019 / 2020–06/2026 |
| BTCUSD | 01/2018 → 10/2026 | 2019–2021 / 2022–2023 / 2024–06/2026 | 2020–2022 / 2023–06/2026 |

Kỳ sau 07/2026 chỉ báo cáo. Lưu ý: FX 2023–2026 đã được dùng làm kỳ test ở G124, nhưng câu hỏi ở đây khác (mô tả khả năng đoán).

## Phần 1 — phá mức (như G156a2, trên H1)

- **Mức:** biên Á (01–07 giờ server), đỉnh / đáy ngày trước, đỉnh / đáy tuần trước, swing H1 (6 nến mỗi bên, hiệu lực 5 ngày).
- **Sự kiện:** nến H1 đầu tiên đóng vượt mức.
- **Đáp án:** từ giá đóng, ± 1 ATR14 H1, trong **4 nến (4 giờ)**: ĐI TIẾP / GIẢ / LƯỠNG LỰ / CẢ HAI.

## Phần 2 — mỏ neo (như G156b)

- M0–M3, cuốn chiếu theo năm, cùng gói bối cảnh.
- "Bối cảnh có giá trị" khi kỹ năng Brier trên năm kiểm > 0 với cận dưới khoảng tin cậy **98,75 %** > 0 (Bonferroni 0,05 / 4 thị trường;
  bootstrap khối tuần), và dương ở ≥ 2 / 3 số năm kiểm gần nhất.

## Phần 3 — tình huống (như G156c, 11 tình huống)

Bỏ **T7** (vàng và USD cùng chiều): với FX thì DXY gần như trùng chính cặp tiền.

Điều chỉnh:
- Mốc ± 1 ATR H1, 4 nến; chống trùng 4 nến.
- Tin USD HIGH cho cả 4 thị trường.
- T3 (tin 15:30 server, đo lúc mở cửa New York): đo ở nến H1 đóng 17:00 server.
- **T8**, chiều tin gợi ý khi USD mạnh lên:
  - EURUSD / GBPUSD: xuống;
  - USDJPY: lên;
  - BTC: xuống (giả định giống vàng, ghi rõ là giả định).

Phân loại "có giá trị dự báo" theo luật G156c:
- ≥ 100 lần phân định, ≥ 30 mỗi kỳ;
- khoảng tin cậy không chứa 0, với Bonferroni **0,05 / 44** (11 tình huống × 4 thị trường), tức CI 99,89 %;
- cùng dấu ở ≥ 2 / 3 kỳ.

## Nếu có gì đạt

Không trade ngay. Viết kế hoạch setup riêng (G158) cho đúng phát hiện đó, có:
- chi phí harsh;
- kỳ kiểm chưa dùng hoặc forward;
- đối chứng lệnh ngẫu nhiên;
- chuyển thị trường.

Không đạt thì ghi vào bộ kiến thức như với vàng.

Script `research/long/g157_markets.py`, dùng lại hàm của G156a / G156a2 / G156b / G156c, tham số hóa theo thị trường và khung. Kết quả
`research/long/results/g157/`. Kiểm lại: chạy XAUUSD M30 qua cùng đường mới phải ra y hệt G156c. Không chỉnh định nghĩa sau khi chạy.
