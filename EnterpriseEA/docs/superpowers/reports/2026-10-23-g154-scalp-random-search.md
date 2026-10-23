# G154 — máy dò tiến hóa tìm setup scalp vàng M15 (23/10/2026)

Kế hoạch đăng ký trước: [2026-10-23-g154-scalp-random-search.md](../plans/2026-10-23-g154-scalp-random-search.md) (commit `87e8e5a`). Script
[`g154_scalp_search.py`](../../research/long/g154_scalp_search.py), kết quả `research/long/results/g154/search.json`.

**Kết luận: KHÔNG ĐẠT.** Máy dò chỉ vượt mức "may" ở sát ngưỡng. Mọi tổ hợp tốt nhất đều thua lệnh vào ngẫu nhiên cùng giờ, cùng chiều, và
đều âm trên BTC lẫn bạc.

## Kiểm tra trước khi chạy

Bộ tính kết quả lệnh (vector hóa) khớp tuyệt đối với `gp.run_trade` + `harsh` G68 trên 300 lệnh thử: 0 sai lệch, cả R lẫn nến thoát.

## G0 — cuộc dò có tìm được gì hơn may?

| | |
|---|---|
| tổ hợp đã chấm (thật) | 4.699 |
| điểm tốt nhất thật (t-stat R harsh, bỏ 5 lệnh lớn) | **1,32** |
| 50 lần null (dịch kết quả 92 × m nến) | từ −0,32 tới 1,71; phân vị 95 % = **1,27** |
| p (null ≥ thật) | 0,039 |

Qua G0 nhưng chỉ sát ngưỡng: 2 / 50 lần null cho điểm cao hơn. Điểm 1,32 bản thân nó cũng thấp: t-stat 1,3 trong kỳ tìm nghĩa là R trung bình
chỉ nhỉnh hơn 0 một chút so với độ dao động.

## Top tổ hợp (kỳ kiểm 2024 – 06/2026, chi phí harsh)

Máy dò hội tụ về một họ: **3 nến đà cùng chiều + chế độ D1 cùng chiều + ATR14/ATR100 > 1,2** (biến động đang mở rộng), SL 1,5 ATR,
giữ tối đa 32 nến.

| Tổ hợp | Kỳ tìm | **Kỳ kiểm** | × 1,5 | Mua / bán (kiểm) | Quý dương | p đối chứng | BTC | Bạc | Kỳ sau |
|---|---|---|---|---|---|---|---|---|---|
| + giờ 19–22, TP 3R | 189 / +0,19 | **196 / +0,13** | +0,11 | 179 / +0,12 · 17 / +0,29 | 70 % | 0,21 | −0,09 | −0,31 | 14 / −0,65 |
| + giờ 19–22, TP 2R | 192 / +0,16 | 198 / +0,08 | +0,06 | 180 / +0,07 · 18 / +0,23 | 70 % | 0,29 | −0,09 | −0,32 | 14 / −0,59 |
| + bỏ thứ Hai, TP 2R | 442 / +0,06 | 435 / +0,06 | +0,04 | 390 / +0,06 · 45 / +0,09 | 60 % | 0,07 | −0,13 | −0,29 | 36 / −0,02 |
| + EMA200 cùng phía, TP 2R | 370 / +0,05 | 390 / +0,04 | +0,02 | 349 / +0,04 · 41 / +0,05 | 60 % | 0,12 | −0,06 | −0,21 | 26 / +0,02 |
| không thêm lọc, TP 2R | 500 / +0,03 | 524 / +0,05 | +0,03 | 473 / +0,05 · 51 / +0,05 | 50 % | 0,07 | −0,12 | −0,24 | 42 / +0,03 |
| phá 8 nến + D1 không ngược + trong Asia | 166 / +0,11 | 110 / −0,06 | −0,08 | 94 / −0,01 · 16 / −0,39 | 60 % | 0,55 | −0,12 | −0,67 | 9 / +0,83 |

(Đủ 20 dòng trong `search.json`.) Không tổ hợp nào qua **tiêu chí 5** (thắng lệnh ngẫu nhiên, p ≤ 0,0025; tốt nhất 0,065) hay **tiêu chí 6**
(chuyển thị trường).

## Đọc kết quả

1. **Lãi nhỏ trong kỳ kiểm là lãi "ăn theo xu hướng", không phải của setup.** Khoảng 90 % lệnh là lệnh mua (D1 cùng chiều trong chu kỳ vàng
   tăng). Lệnh mua ngẫu nhiên cùng giờ cho kết quả gần như nhau (p 0,07–0,3). Đây cũng là điều G146–G153 đã thấy.
2. **Không chuyển được sang thị trường khác.** BTC âm ở mọi tổ hợp, bạc âm −0,2 tới −0,7R. Một setup scalp có cơ chế thật thường ít nhất
   không lỗ nặng ở thị trường cùng loại.
3. **Kỳ sau (07–10/2026) âm** với các tổ hợp tốt nhất (−0,6R trên 14 lệnh). Ít lệnh, chỉ báo cáo.
4. Máy dò ưa SL rộng (1,5 ATR) và giữ lâu (32 nến M15 = 8 giờ). Đó là xu hướng ngắn hạn chứ không còn là scalp. Với SL 0,5 ATR, spread và
   commission ăn hết lợi thế: không tổ hợp SL hẹp nào lọt top 20.

## Kết luận

Theo luật đăng ký: **không có setup scalp nào đạt.**

Gộp với G125 và G146–G153: trên vàng M15 2021–2026, với chi phí thực tế, các luật kỹ thuật ghép từ nến, chỉ báo, giờ, VWAP, biên phiên và
chế độ không có lợi thế scalp vượt được lệnh ngẫu nhiên cùng điều kiện. Phần lãi duy nhất lặp lại là đi theo xu hướng D1. Phần đó S07 đã
khai thác, với trọng số D1 × 0,5.

Không đề xuất SHADOW.
