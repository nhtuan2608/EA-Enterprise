# MKT02: setup theo phiên Mỹ cho chỉ số và crypto — kế hoạch đăng ký trước (11/10/2026)

## Vì sao

MKT01: bộ quy tắc S07 của vàng không chuyển được sang chỉ số Mỹ và crypto.
- Chỉ số Mỹ rẻ (spread 2–6% biên độ nến M30), nhưng kiểu "nén → bung" không có lợi thế ở đó.
- Chỉ số trong ngày bị chi phối bởi **giờ mở cửa phiên tiền mặt Mỹ** và hay **quay về** sau cú chạy.
- Crypto lớn (BTC, ETH) cũng phản ứng mạnh quanh phiên Mỹ (dòng tiền ETF).

Người dùng muốn nghiên cứu cho tất cả symbol.

## Dữ liệu và giờ

- 8 symbol, nến M15 MT5 (MKT01): NAS100, DJ30, SP500, BTCUSD, ETHUSD, SOLUSD, XRPUSD, LTCUSD.
- Giờ server của broker theo DST Mỹ (UTC+2/+3), nên **giờ New York = giờ server − 7 giờ** quanh năm.
  - Mở cửa NY 09:30 = 16:30 server.
  - Đóng cửa NY 16:00 = 23:00 server.
- Chi phí khắt khe:
  - mua vào giá ask, bán ra giá bid (và ngược lại với lệnh bán);
  - thêm trượt 0,5 × spread trung vị mỗi chiều;
  - phí hoa hồng 0. Nếu tài khoản có phí riêng, kết quả sẽ thấp hơn.
- Mỗi setup chỉ một lệnh mỗi ngày mỗi symbol. Mọi lệnh đóng chậm nhất lúc đóng cửa NY (23:00 server).

**Kỳ:**

| Kỳ | Thời gian |
|---|---|
| Chọn | 20/02/2024 – 30/06/2025 |
| Test (không dùng để chọn) | 01/07/2025 – 09/10/2026 |
| BTC ngoài mẫu thêm | 10/2022 – 02/2024 (có nến M15 trước kỳ chọn) |

**Nhóm:**
- Chỉ số: NAS100, DJ30, SP500.
- Crypto lớn: BTC, ETH.
- Altcoin (SOL, XRP, LTC): spread 65–215% biên độ nến M30, nên **chỉ báo cáo, không dùng để chọn và không xét đạt**.

## Setup

**ORB — phá biên độ mở cửa**
- Biên độ = cao/thấp của N phút đầu phiên NY.
- Tín hiệu: nến M15 đầu tiên đóng ngoài biên trong 2 giờ sau mở cửa. Vào ở giá mở nến kế tiếp.
- Biến thể:
  - N ∈ {15, 30};
  - SL ở biên đối diện (xa) hoặc giữa biên (gần);
  - thoát ở 2R hoặc giữ đến đóng cửa.
- Tổng 8 biến thể.

**GAP — lấp khoảng trống qua đêm**
- Khoảng trống = giá mở 16:30 server − giá đóng phiên NY hôm trước (23:00 server).
- Nếu |khoảng trống| ≥ k × biên độ ngày trung bình 20 ngày: vào **ngược** khoảng trống ở giá mở.
- SL = giá mở ± |khoảng trống| (cách thêm một khoảng bằng khoảng trống).
- Mục tiêu: lấp toàn bộ (về giá đóng hôm trước) hoặc lấp một nửa.
- Biến thể: k ∈ {0,3; 0,6} × mục tiêu {toàn bộ, một nửa} = 4 biến thể.

**VWR — quay về VWAP phiên**
- VWAP phiên tính từ 16:30 server, có trọng số tick volume.
- Tín hiệu từ 17:00 đến 22:00 server: nến M15 đóng cách VWAP ≥ z × ATR14 M15. Vào **ngược lại** ở giá mở nến kế.
- SL = cực trị 3 nến gần nhất ± 0,1 ATR. Mục tiêu = VWAP lúc tín hiệu.
- Biến thể: z ∈ {3, 4} × cần nến đảo chiều (đóng ngược hướng chạy) {không, có} = 4 biến thể.

## Chọn và kiểm tra

**Chọn** (mỗi setup × nhóm, gộp các symbol trong nhóm, chỉ dùng kỳ chọn):
- Biến thể đạt khi R/lệnh > 0, có ≥ 60 lệnh, và cả hai nửa của kỳ chọn đều > 0.
- Lấy biến thể có R cao nhất.

**Kiểm tra** (kỳ test). Có 6 ô (3 setup × 2 nhóm). Ô đạt khi đủ cả ba:
1. R/lệnh > 0;
2. cận dưới bootstrap 90% > 0;
3. sau trừ 0,10R vẫn > 0.

Chỉ đề xuất SHADOW khi cận dưới Bonferroni (0,10/6, tức 98,3%) cũng > 0.

**Báo cáo thêm:**
- từng symbol;
- BTC ngoài mẫu thêm (10/2022–02/2024);
- altcoin theo biến thể đã chọn của nhóm crypto;
- %/năm và DD ở 0,5%/lệnh.

## Đầu ra

`research/markets/mkt02_session.py`, báo cáo `reports/2026-10-11-mkt02-session-setups.md`.
