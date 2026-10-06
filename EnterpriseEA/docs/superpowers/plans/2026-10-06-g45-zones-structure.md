# G45: vùng giá, cấu trúc thị trường và mô hình đảo chiều — kế hoạch (06/10/2026)

Yêu cầu người dùng (06/10): hệ thống đã có supply/demand dạng hợp lưu, flip zone (S02), quét thanh khoản (S04)…; **cái gì chưa có thì đưa vào thử hết**. Chỉ dữ liệu MT5.

## Đã có (không làm lại)

Vùng hợp lưu đỉnh/đáy ngày/phiên/tuần/swing (`Market/ConfluenceLevels.mqh`), flip zone = phá + retest (S02, âm 2010–2025), phá giả/quét (S04), co hẹp → bung (S06B), phá kênh (T2), S01 phiên Á, S03 PDH/PDL, S05 hồi theo xu hướng (prototype, G23).

## Thử mới (H1, 5 symbol 2010–2025; mỗi họ ≤ ~16 bộ tham số)

| Mã | Khái niệm | Vào lệnh | Dừng / thoát |
|---|---|---|---|
| Z1 | Supply/Demand base → impulse (DBR/RBD) | vùng base (1–3 nến, biên ≤ k·ATR) trước nến bung ≥ m·ATR; **lệnh chờ ở mép gần** khi giá quay lại lần đầu | sau mép xa + 0,1 ATR; 2R / 3R / trail |
| Z2 | Order block + BOS | nến ngược chiều cuối cùng trước cú phá đỉnh/đáy swing đã xác nhận; lệnh chờ ở mép gần của OB | sau mép xa; 2R / 3R |
| Z3 | Fair value gap | khoảng trống 3 nến (đáy nến i > đỉnh nến i−2) sau nến bung; lệnh chờ ở mép gần / giữa gap | dưới gap 0,5 ATR; 2R / 3R |
| Z4 | Quét thanh khoản + CHoCH | quét đáy/đỉnh swing rồi đóng lại trong, sau đó đóng vượt đỉnh/đáy của nến quét | dưới đáy quét; 2R / 3R |
| Z5 | Fibonacci OTE | chân sóng ≥ k·ATR theo xu hướng D1; lệnh chờ ở 61,8% hoặc 70,5% | dưới 100%; về 0% hoặc 2R |
| Z6 | Phân kỳ RSI (phát hiện đảo chiều) | đáy swing thấp hơn nhưng RSI14 cao hơn; vào khi xác nhận swing | dưới đáy; 2R / 3R |
| Z7 | Hai đáy / hai đỉnh | hai đáy swing cách ≤ tol·ATR, ≥ 8 nến; vào khi đóng vượt neckline | dưới đáy thấp hơn; 2R / đo chiều cao |

Mỗi họ có biến thể **lọc theo xu hướng D1** (EMA200) và không lọc. Swing = fractal 3 nến, chỉ dùng sau khi đã xác nhận (không nhìn trước). Lệnh chờ: khớp khi giá (cộng spread cho lệnh mua) chạm mức; nếu nến khớp cũng chạm dừng lỗ thì tính thua cả lệnh (bảo thủ).

## Đối chứng (như G38)

Chọn trên 2010–2016; phải dương ở 2017–2020 và 2021–2025; thắng vào lệnh ngẫu nhiên cùng khoảng dừng ATR và cùng cách thoát (p < 0,05/7 cho đa kiểm định); láng giềng ≥ 60% dương 3 kỳ; ngoài mẫu 16 symbol H1 2024–2026; phí ×2 + trượt 0,1R.

## Dùng làm bộ lọc

Khái niệm nào có thông tin dù không thành setup thì thử làm **bộ lọc** cho T2 / S06B / S04 (vd. bỏ T2 mua khi vùng supply tươi nằm trong 2 ATR phía trên), đối chứng bằng bỏ ngẫu nhiên cùng tỷ lệ.

## Đầu ra

`research/long/g45_zones.py`, báo cáo `reports/2026-10-06-g45-zones-structure.md`; setup đạt → engine SHADOW (người dùng chốt trước khi LIVE).
