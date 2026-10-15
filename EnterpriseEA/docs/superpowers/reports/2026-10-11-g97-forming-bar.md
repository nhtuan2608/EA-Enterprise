# G97 (xem nhanh): đoán nến H1 đang chạy từ trạng thái M15 đã khóa chiều

Ngày 11/10/2026. Ý tưởng của người dùng lấy từ chart 12/03/2026. Script: `research/long/g97_forming_bar.py`. Chỉ dùng train 07/2021–2023; validate và test vẫn để kín.

**Luật bán (mua đối xứng), xét ở mỗi nến M15 đóng bên trong một nến H1:**

| Mã | Điều kiện |
|---|---|
| C1 | M15: giá < EMA21 < EMA55 < EMA100 < EMA200 |
| C2 | M15: DI− − DI+ ≥ 10 |
| C3 | M15: ADX đang tăng |
| C4 | Nến H1 đã đóng gần nhất nằm dưới EMA200 H1 |
| C5 | Giá ở nửa dưới của nến M30 đang chạy |
| C6 | Nến H1 đang chạy có râu trên ≥ 25% biên độ (tùy chọn) |

**Cách đo:**
- Dự đoán: nến H1 đóng thấp hơn giá vào.
- Lệnh: vào ở giá mở nến M15 kế tiếp; stop trên đỉnh nến H1 đang chạy + 0,1 ATR; thoát ở giờ tròn khi nến H1 đóng.
- Mỗi nến H1 tối đa một lệnh; spread theo từng nến.

## Ví dụ 12/03/2026 (giờ VN)

- C1 (dải EMA M15 xếp đủ thứ tự) chỉ đúng từ **22:15**, vì EMA21 cần thời gian mới cắt xuống dưới các EMA kia.
- C4 chỉ đúng từ 21:15 (nến H1 đóng lúc 21:00 mới nằm dưới EMA200 H1).
- Luật đủ điều kiện lần đầu lúc 22:15, giá 5.124,7. Lúc đó phần lớn chặng đầu (5.185 → 5.125) đã chạy xong, và nến H1 đó đóng 5.132,3, tức **thua** ở giờ tròn.
- Thứ thực sự bật sớm lúc 20:30–21:00 là DI tách xa + ADX tăng + nửa dưới M30 + giá dưới các EMA, nhưng dải EMA **chưa** xếp thứ tự.

## Train 07/2021–2023 (XAUUSD M15)

| Chiều | Luật | Số lệnh | H1 đóng tiếp chiều | R/lệnh |
|---|---|---|---|---|
| Bán | mọi nến bên trong H1 (đối chứng) | 14.505 | 49,8% | −0,23 |
| Bán | C1..C5 (luật người dùng) | 1.322 | **45,9%** | −0,12 |
| Bán | C1..C6 (+ râu H1) | 642 | 46,0% | −0,14 |
| Bán | dưới 4 EMA chưa xếp thứ tự + C2 + C3 + C5 (bản sớm) | 957 | 45,8% | −0,09 |
| Mua | đối chứng | 14.506 | 49,9% | −0,15 |
| Mua | C1..C5 | 1.380 | 48,8% | −0,04 |
| Mua | bản sớm | 923 | 47,9% | −0,10 |

## Kết luận

Trạng thái M15 **không** đoán được nến H1 đang chạy sẽ đóng theo chiều nào: tỉ lệ đúng 46–50%, ngang tung đồng xu, thậm chí hơi thấp hơn. R/lệnh nhích lên so với đối chứng chỉ vì stop xa hơn nên spread chiếm ít R hơn, vẫn âm. Kết quả khớp với G95 F1: hướng giá vài chục phút gần như ngẫu nhiên.

Thứ làm nên lãi ở 12/03 là **cầm lệnh qua nhiều giờ** (chặng giảm 5.185 → 5.010 → 4.100), không phải đoán đúng nến giờ tròn. Không mở validate/test.
