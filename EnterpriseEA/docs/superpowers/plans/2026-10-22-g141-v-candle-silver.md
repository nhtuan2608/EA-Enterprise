# G141: ứng viên nến V M30 (G118 A) chuyển nguyên văn sang bạc XAGUSD — kế hoạch đăng ký trước (22/10/2026)

## Vì sao

G140 định kiểm ngoài mẫu trên 2010–2017. Khi chạy thì phát hiện `research/long/data/{m30v,h1v,h4v}` **và** bộ export gốc chỉ có nến
**D1** trước 19/03/2018 (khoảng 260 nến mỗi năm, spread 0), nên không có kỳ ngoài mẫu trong ngày nào trước 2018 (xem báo cáo G140).

Phép thử độc lập còn lại: chạy ứng viên A trên một chuỗi giá **chưa từng dùng để chọn luật**. Bạc XAGUSD là kim loại gần vàng nhất.
Họ nến V (G116–G119, G134, G136) chưa bao giờ chạy trên bạc. (S07 trên bạc đã thử ở G67, âm; không thử lại.)

## Luật (đóng băng, như G118 A / G140 V)

- Nến V M30 quay về EMA200 (G116: thân nến cắt EMA200; trong 6 nến sau, giá ra khỏi vùng nến V rồi một nến đóng lại trong vùng).
- Bối cảnh A tại nến V:
  - EMA21/55/100 xòe ngược chiều nến V;
  - ADX14 < 25;
  - dốc EMA200 48 nến ngược chiều nến V.
- Quản lý: hedge G116, stop ± 2 ATR (A2), bồi, thoát X3. Kết quả theo U.

## Dữ liệu

- `research/long/data/bars_XAGUSD_M15.csv` (XAGUSD, giờ server, 02/2024–10/2026), gộp thành nến M30 theo khối 30 phút giờ server.
- Spread = cột spread × 0,001 (point bạc), tối thiểu bằng trung vị. Bản chi phí × 1,5.
- So sánh (không quyết định): vàng cùng khoảng thời gian, cùng cách gộp từ M15 (`data/m15v`).

## Đạt khi (1 ô)

- ≥ 40 nhóm;
- U/nhóm > 0 ở **cả hai nửa**: trước / từ 01/06/2025;
- U/nhóm toàn kỳ > 0 với chi phí × 1,5;
- thắng ngẫu nhiên p ≤ 0,05. Đối chứng 200 lần: mỗi nhóm thay bằng một nến cùng nửa, cùng chiều, có cùng bối cảnh A và chạm EMA200
  trong 3 nến trước, hedge A2 như nhóm thật.

## Ý nghĩa

- **Đạt**: lợi thế của ứng viên A không chỉ là đặc điểm riêng của chuỗi giá vàng 2018–2026. Khi đó đề xuất thêm hồ sơ **M30** cho bot
  VHedge, mặc định SHADOW, forward ≥ 30 nhóm.
- **Không đạt**: ứng viên A vẫn chỉ có bằng chứng trên chính dữ liệu đã dùng để chọn nó. Không đề xuất đưa vào EA.

Script: `research/long/g141_v_silver.py`. Báo cáo chung với G140.
