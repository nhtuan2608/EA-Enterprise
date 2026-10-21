# G143: động lượng trong phiên của vàng (giờ đầu phiên New York, giờ đầu phiên London) — kế hoạch đăng ký trước (22/10/2026)

## Vì sao

Setup trong ngày mới cho mục "scalp". MKT02 (chỉ số, crypto) ghi nhận: khi giá đi xa trong phiên Mỹ thì **tiếp tục** chạy, nhưng chưa
kiểm, và chưa từng chạy trên vàng. Cơ chế:
- dữ liệu Mỹ ra lúc 08:30 New York;
- dòng lệnh lớn được chia nhỏ trong phiên;
- vị thế dồn về giờ chốt giá COMEX (13:30 New York).

Tài liệu "intraday momentum" (nửa giờ đầu dự báo nửa giờ cuối) cũng ghi nhận hiện tượng này trên nhiều thị trường.

G138 xác nhận giờ server = giờ New York + 7 quanh năm (NFP 08:30 New York = 15:30 server).

## Hai ô (ngưỡng p ≤ 0,025)

| Ô | Cửa sổ đo (giờ server) | Vào | Ra |
|---|---|---|---|
| **NY** | 15:30 → 16:30 (4 nến M15, gồm giờ ra tin 08:30 New York) | giá mở nến 16:30 | giá đóng nến 20:15 (= 20:30 server, giờ chốt COMEX) |
| **LDN** | 10:00 → 11:00 (giờ đầu phiên London) | giá mở nến 11:00 | giá đóng nến 15:00 (= 15:15 server, trước tin Mỹ) |

**Tín hiệu**:
- di chuyển = close nến cuối cửa sổ − open nến đầu cửa sổ;
- vào khi |di chuyển| ≥ 0,4 × ATR20 D1 (tính trên các ngày server đã đóng trước hôm đó);
- chiều = chiều di chuyển; cả mua và bán;
- cần đủ 4 nến M15 của cửa sổ, nếu thiếu thì bỏ ngày đó.

**SL**: giá mở nến đầu cửa sổ (toàn bộ di chuyển quay lại). 1R = khoảng cách vào → SL. Không có TP; đóng theo giờ. SL chạm thì tính SL
(engine `g137_patterns.run_trade`, chi phí harsh G68, bản × 1,5).

## Dữ liệu và kỳ

`data/m15v/XAUUSD.csv` (20/07/2021 → 10/2026).

| Kỳ | Khoảng |
|---|---|
| train | 07/2021–12/2023 |
| validate | 01/2024–06/2025 |
| test | 07/2025–06/2026 |
| sau | 07/2026+ (chỉ xem) |

## Đạt khi (từng ô)

- R/lệnh > 0 ở train, validate và test;
- ≥ 40 lệnh mỗi kỳ;
- R/lệnh gộp train + validate > 0 với chi phí × 1,5;
- thắng đối chứng p ≤ 0,025. Đối chứng 200 lần: mỗi lệnh thay bằng một ngày ngẫu nhiên **cùng kỳ**, **cùng chiều**, vào và ra đúng giờ đó,
  SL cùng khoảng cách tính theo ATR20 D1.

Đối chứng này tách phần "biết hướng di chuyển đầu phiên" khỏi phần "trôi giá theo giờ / theo xu hướng chung".

Báo thêm (không quyết định): mua / bán, theo năm, ngưỡng 0,25 và 0,6 ATR (độ nhạy, không dùng để chọn).

## Nếu đạt

Đề xuất setup trong ngày riêng (bot mới hoặc chế độ trong bots host), mặc định SHADOW, rủi ro thấp, forward ≥ 30 lệnh.

Script `research/long/g143_session_momentum.py`. Không chỉnh luật sau khi chạy.
