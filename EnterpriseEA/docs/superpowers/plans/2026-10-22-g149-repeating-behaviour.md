# G149: bản đồ hành vi lặp lại của giá → điểm vào / điểm chốt cho scalp và swing — kế hoạch đăng ký trước (22/10/2026)

## Vì sao

Người dùng (22/10) muốn **tư duy ngược**: không tìm "tín hiệu thắng" mà tìm hành vi giá lặp lại để đặt điểm vào và điểm chốt an toàn, lặp
lại tốt, cho cả scalp và swing.

G148 cho thấy điều kiện lọc kiểu indicator đổi dấu theo năm. Thứ gần ổn định nhất đều là **hành vi giá**:
- quét đỉnh / đáy hôm qua rồi quay về;
- vùng sát EMA200 D1 xấu;
- biến động cao tốt hơn.

## Dữ liệu và kỳ

XAUUSD M30 `data/m30v`, từ 01/05/2018. D1 và tuần dựng từ nến M30 theo ngày server. Chi phí harsh G68 (bản × 1,5).

| Kỳ | Khoảng |
|---|---|
| chọn | 05/2018 – 12/2021 |
| validate | 2022 – 2023 |
| test | 01/2024 – 06/2026 |
| sau | 07/2026+ (chỉ xem) |

## Phần 1 — quy luật (mô tả; báo theo từng năm và từng chiều; không quyết định)

| Mã | Quy luật đo |
|---|---|
| Q1 | % số ngày chạm đỉnh hôm qua, chạm đáy hôm qua, chạm cả hai |
| Q2 | khi đã thủng đỉnh / đáy hôm qua, % ngày đóng cửa quay lại trong biên hôm qua |
| Q3 | % ngày phá biên phiên Á (00–09 server) sau 09:00; khi đã phá, % quay lại trong biên trước 22:30 |
| Q4 | khi giá cách VWAP ngày ≥ 1,5 ATR (10–20 giờ server), % chạm lại VWAP trước 22:30, so với % đi thêm 1 ATR theo hướng đang cách |
| Q5 | sau nhịp đi 20 nến ≥ 3 ATR tạo đỉnh / đáy mới: phân bố độ hồi (tính theo phần của nhịp) trước khi phá lại đỉnh / đáy đó |
| Q6 | khi lệnh vào ngẫu nhiên đã đi +1 ATR: % tới +2 ATR trước khi quay về giá vào |
| Q7 | giờ hình thành đỉnh và đáy ngày (phân bố theo giờ server) |
| Q8 | % tuần phá đỉnh / đáy tuần trước; khi đã phá, % tuần đóng cửa giữ được hướng phá |

## Phần 2 — 6 ô lệnh (ô quyết định)

Mọi ô đều cả mua và bán (đối xứng), mỗi chiều mỗi ngày (tuần) nhiều nhất một lệnh. Mỗi ô có tối đa 2 lựa chọn tham số, **chọn trên kỳ
chọn** theo R/lệnh, rồi giữ nguyên.

**Scalp / trong ngày**

| Ô | Luật (mua; bán đối xứng) | Lựa chọn |
|---|---|---|
| **K1 quét đáy hôm qua rồi quay về** | Trong 01–21 giờ server, giá hôm nay đã thủng đáy hôm qua, rồi một nến M30 đóng lại trên đáy hôm qua → mua ở giá mở nến sau. SL = đáy hôm nay − 0,1 ATR (0,3–3 ATR). Đóng hết lúc 22:30 | TP = giữa biên hôm qua / đỉnh hôm qua |
| **K2 phá biên phiên Á rồi quay về** | Biên Á (00–09) ≥ 0,5 ATR. Sau 09:00 giá thủng đáy Á, rồi một nến đóng lại trên đáy Á → mua ở giá mở nến sau. SL = thấp nhất từ lúc thủng − 0,1 ATR (0,3–3 ATR). Đóng 22:30 | TP = giữa biên Á / đỉnh Á |
| **K3 hồi trong nhịp mạnh (limit)** | Nhịp: giá đi 20 nến ≥ 3 ATR và vừa lập đỉnh 20 nến mới. Đặt limit mua ở đỉnh − f × (đỉnh − đáy 20 nến). SL = đỉnh − 0,786 × nhịp. TP = đỉnh nhịp (giá quay lại đỉnh). Hủy sau 16 nến hoặc khi giá lập đỉnh mới trước khi khớp | f = 0,382 / 0,5 |
| **K4 giá xa VWAP ngày** | 10–20 giờ server, close cách VWAP ngày ≥ 1,5 ATR (lần đầu trong ngày mỗi phía). Vào ở giá mở nến sau. Đóng 22:30 | **ngược về VWAP** (TP = VWAP, SL = 1 ATR thêm về phía đang cách) / **theo hướng** (TP 1,5 ATR, SL 1 ATR) |

**Swing (tuần)**

| Ô | Luật (mua; bán đối xứng) | Lựa chọn |
|---|---|---|
| **W1 phá đỉnh tuần trước** | Thứ Hai – Thứ Năm, giá chạm đỉnh tuần trước + spread → mua (lệnh chờ). SL = giữa biên tuần trước. Đóng 21:30 Thứ Sáu | TP = không / đỉnh tuần trước + 1 × biên tuần trước |
| **W2 quét đỉnh tuần trước rồi quay về** | Giá vượt đỉnh tuần trước không quá 0,5 ATR20 D1, rồi một ngày (D1) đóng lại dưới đỉnh đó → bán ở giá mở ngày sau. SL = đỉnh tuần này + 0,1 ATR D1. Đóng 21:30 Thứ Sáu | TP = giữa biên tuần trước / đáy tuần trước |

(W2 viết theo chiều bán ở đỉnh; mua ở đáy tuần trước đối xứng.)

## Đạt khi (từng ô; 6 ô → p ≤ 0,008)

1. R/lệnh > 0 ở validate và test; ≥ 40 lệnh mỗi kỳ (W1, W2: ≥ 20);
2. mua > 0 và bán > 0 (gộp validate + test);
3. tháng vàng không tăng > 0;
4. đối chứng ngẫu nhiên p ≤ 0,008 (cùng số lệnh, chiều, giờ server, kỳ; vào ở nến ngẫu nhiên; cùng khoảng SL / TP theo ATR và cùng giờ đóng);
5. chi phí × 1,5 > 0 (gộp validate + test);
6. bỏ 5 lệnh lớn nhất vẫn > 0;
7. cửa sổ 6 tháng tệ nhất ≥ −15R.

Báo thêm (không quyết định), cho mỗi ô:
- tỷ lệ thắng;
- **tỷ lệ chạm TP** (độ lặp lại);
- trung bình lãi / lỗ;
- kết quả khi bỏ lệnh ở vùng sát EMA200 D1 (0–1 ATR D1) và khi ATR thấp (hai gợi ý của G148).

## Nếu đạt

Đề xuất setup (scalp hoặc swing), mặc định SHADOW, forward ≥ 30 lệnh (swing ≥ 10), người dùng đồng ý mới đưa vào EA.

Script `research/long/g149_repeating.py`. Không chỉnh luật sau khi chạy.
