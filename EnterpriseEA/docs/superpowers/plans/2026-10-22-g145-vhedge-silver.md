# G145: bot VHedge G119 (luật live, nguyên văn) trên bạc XAGUSD M5 — kế hoạch đăng ký trước (22/10/2026)

## Vì sao

VHedge G119 là bot scalp đang chạy live trên vàng M5. Nó được chọn trên vàng 05/2024–12/2025 (G119/G120), tức là chỉ có bằng chứng
trên đúng một chuỗi giá. Bạc **chưa từng** được dùng để chọn hay chỉnh luật này. Nếu luật giữ nguyên văn vẫn có lãi trên bạc:
- đó là bằng chứng lợi thế không phải đặc điểm riêng của vàng;
- đồng thời là một **nâng cấp bot**: chạy thêm VHedge trên XAGUSD.

## Luật (nguyên văn bot live, `Bots/VHedgeBot.mqh` / G120 E0)

- **Nhóm V** (G116): thân nến M5 cắt EMA200; trong 6 nến sau, giá ra ngoài vùng nến V rồi một nến đóng lại trong vùng.
- **Hồ sơ G119** với ngưỡng số cố định của bot:
  - spread EMA21..200 ≤ 0,91 ATR14 tại nến V;
  - **và** (volume nến V ≥ 1,26 × trung bình 20 nến trước **hoặc** volume nến quay về ≥ 1,17 ×).
- **Quản lý**:
  - mua và bán ở giá mở sau nến quay về, stop giá mở ∓ 1,5 ATR (+0,1 ATR đệm);
  - chân bị dừng trước thì lỗ; bồi theo chiều chân còn lại, cùng stop;
  - mục tiêu 5R, hòa vốn ở +1R, đóng hết sau 288 nến;
  - kết quả theo U (khoảng giữa hai stop).

## Dữ liệu

- XAGUSD-VIP M5 đọc từ terminal bằng `copy_rates_from_pos` (chỉ đọc, một lần, lưu CSV), giờ server.
- Spread = cột spread × 0,001 (point bạc), dùng như engine vàng (spread thực từng nến). Bản chi phí × 1,5.
- So sánh (không quyết định): vàng XAUUSD-VIP M5 cùng khoảng thời gian, cùng code.

## Đạt khi (1 ô)

- ≥ 60 nhóm;
- U/nhóm > 0 ở **cả hai nửa** (chia đôi theo thời gian, mốc = ngày giữa của khoảng dữ liệu);
- U/nhóm toàn kỳ > 0 với chi phí × 1,5;
- thắng đối chứng p ≤ 0,05. Đối chứng 200 lần: mỗi nhóm thật thay bằng một "nến gần EMA200 không cắt" (G116 pseudo), cùng nửa, đi qua
  cùng hồ sơ G119 và cùng quản lý.

## Nếu đạt

Đề xuất chạy thêm VHedge trên XAGUSD:
- mặc định SHADOW, cùng Portfolio Guard;
- forward ≥ 30 nhóm trước khi LIVE;
- người dùng đồng ý mới bật.

Ghi rõ khoảng dữ liệu bạc ngắn (giới hạn 100.000 nến của terminal).

Script `research/long/g145_vhedge_silver.py`. Không chỉnh luật sau khi chạy.
