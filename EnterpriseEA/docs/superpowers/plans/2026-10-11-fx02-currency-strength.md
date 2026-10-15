# FX02: sức mạnh tiền tệ khung dài (D1, giữ nhiều ngày) — kế hoạch đăng ký trước (11/10/2026)

## Vì sao

G90–G93 và FX01 cho thấy EUR/GBP trong ngày (M15–H1) không có lợi thế vượt chi phí. Còn lại hai lối thoát:
1. **Khung dài**: chi phí nhỏ so với biên độ.
2. **Xếp hạng nhiều đồng tiền thay vì cố định một cặp**: lợi thế xoay vòng giữa cặp/kỳ (G91) thì để chiến lược tự xoay theo.

## Dữ liệu (MT5, không tải ngoài)

**Đồng tiền:** USD, EUR, GBP, JPY. Chỉ 3 cặp chính có dữ liệu từ 2010.

**6 cặp:**
- 3 cặp chính thật: EURUSD, GBPUSD, USDJPY.
- 3 cặp chéo dựng từ cặp chính, theo giá đóng D1:
  - EURJPY = EURUSD × USDJPY;
  - GBPJPY = GBPUSD × USDJPY;
  - EURGBP = EURUSD ÷ GBPUSD.
- **Kiểm tra trước**: so cặp chéo tổng hợp với cặp chéo thật (D1, 2024–2025). Tương quan lợi nhuận ngày phải ≥ 0,95, nếu không thì chỉ dùng 3 cặp chính.

**Chi phí** (tính khi vào và khi ra một lệnh):
- Cặp chính: spread trung vị của cặp + phí như G55.
- Cặp chéo: tổng chi phí hai chân, quy đổi sang giá cặp chéo. Cách tính này khắt khe hơn cặp chéo thật.
- Swap: chỉ có mức swap hiện tại của broker, không có lịch sử. Vì vậy **chọn và chấm không tính swap**; báo cáo thêm bản có swap (mức hiện tại, ×3 ngày thứ Tư; EURGBP coi bằng 0) để xem độ nhạy.

**Đơn vị R:** 2 × trung bình |thay đổi giá đóng ngày| 20 ngày của cặp, đo lúc vào. Lệnh không có SL, đóng khi tái cân bằng. R = lời/lỗ ÷ đơn vị đó. Cùng một thước đo cho mọi cặp.

**Kỳ:**

| Kỳ | Thời gian |
|---|---|
| Train | 2010–2016 |
| Validate | 2017–2020 |
| Test (không dùng để chọn) | 2021–10/2025 |

## Họ chiến lược (tái cân bằng ở giá đóng D1)

Điểm sức mạnh mỗi đồng tiền = trung bình, trên 3 cặp chứa nó, của lợi nhuận log L ngày (lấy dấu theo đồng tiền), chia cho biến động 20 ngày của cặp.

**CSM — động lượng chéo**
- Mua đồng mạnh nhất, bán đồng yếu nhất, qua cặp tương ứng. Giữ H ngày rồi xếp lại.
- L ∈ {20, 60, 120}, H ∈ {5, 20}: 6 biến thể.

**CSR — đảo chiều ngắn chéo**
- Mua đồng yếu nhất, bán đồng mạnh nhất.
- L ∈ {3, 5}, H ∈ {1, 3}: 4 biến thể.

**TSM — xu hướng từng cặp**
- Mỗi cặp trong 6 cặp giữ theo dấu lợi nhuận L ngày, xem lại sau H ngày.
- L ∈ {20, 60, 120}, H ∈ {5, 20}: 6 biến thể.

Mỗi lần giữ là một lệnh. Nếu lần xem lại sau giữ đúng cặp và chiều cũ thì vẫn tính là lệnh mới, kèm chi phí vào/ra. Cách này khắt khe hơn thực tế.

**Chọn:** riêng từng họ, như G93.
- Biến thể đạt khi R > 0 ở cả train và validate, và có ≥ 60 lệnh.
- Lấy biến thể có min(train, validate) cao nhất.

## Bộ lọc (chấm như G79, luật như G93)

| Mã | Lọc |
|---|---|
| F1 | độ phân tán cao: chênh điểm mạnh nhất − yếu nhất (với TSM là \|điểm\| của cặp) trên trung vị 250 ngày trước |
| F2 | cặp cùng phía EMA200 D1 theo chiều lệnh |
| F3 | biến động 20 ngày của cặp dưới trung vị 250 ngày trước (thị trường êm) |

## Kiểm tra cuối (test 2021–10/2025)

Có 3 ô (3 họ). Ô đạt khi đủ cả ba:
1. R/lệnh > 0;
2. cận dưới bootstrap 90% > 0;
3. sau trừ 0,10R vẫn > 0.

Chỉ đề xuất SHADOW khi cận dưới Bonferroni (0,10/3, tức 96,7%) cũng > 0.

Báo cáo thêm:
- %/năm và DD ở 0,5%/lệnh (với TSM là 0,5% chia cho 6 cặp);
- bản có swap;
- cặp được trade nhiều nhất;
- R theo năm.

## Nếu không đạt

Ghi kết luận FX trong ngày và khung dài với 4 đồng tiền. Sau đó đề xuất hướng khác ngoài setup giá: theo phiên/thời điểm, theo cấu trúc chi phí, hoặc dừng FX.

## Đầu ra

`research/fx/fx02_strength.py`, báo cáo `reports/2026-10-11-fx02-currency-strength.md`.
