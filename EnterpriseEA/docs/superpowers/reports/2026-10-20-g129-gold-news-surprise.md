# G129: vàng sau tin USD bất ngờ — kết quả

Kế hoạch: `plans/2026-10-20-g129-gold-news-surprise.md`. XAUUSD M30 từ 03/2018, tin USD HIGH có thực tế và dự báo (bỏ tồn kho dầu EIA). Chi phí khắt khe: trượt mỗi chiều max(0,5 × spread trung vị; spread nến vào) + $6/lot. Ô: số lệnh / R mỗi lệnh.

Kiểm tra đồng hồ: NFP lúc 12:30/13:30 UTC 100% (201 tin); nến M30 chứa NFP / cùng giờ thứ Sáu khác = 2.61 (93 nến).

Số thời điểm tin (sau gộp, bỏ trung tính): 1799.

## Biến thể (train 03/2018–2021, validate 2022–2025)

| Tín hiệu | \|z\| ≥ | Thoát | Train | Validate | Mua (train · val) | Bán (train · val) | Đối chứng validate | p | Chọn? |
|---|---|---|---|---|---|---|---|---|---|
| S | mọi | X1 | 694 / -0.227 | 727 / -0.208 | 303 / -0.222 · 365 / -0.179 | 391 / -0.231 · 362 / -0.237 | xáo dấu -0.199 | 0.580 |  |
| S | mọi | X2 | 694 / -0.253 | 727 / -0.176 | 303 / -0.260 · 365 / -0.170 | 391 / -0.248 · 362 / -0.183 | xáo dấu -0.125 | 0.786 |  |
| S | 1 | X1 | 305 / -0.189 | 155 / -0.220 | 131 / -0.212 · 86 / -0.208 | 174 / -0.172 · 69 / -0.235 | xáo dấu -0.192 | 0.644 |  |
| S | 1 | X2 | 305 / -0.292 | 155 / -0.175 | 131 / -0.298 · 86 / -0.209 | 174 / -0.287 · 69 / -0.131 | xáo dấu -0.111 | 0.642 |  |
| C | mọi | X1 | 166 / -0.087 | 210 / -0.088 | 74 / -0.145 · 108 / -0.054 | 92 / -0.041 · 102 / -0.124 | xáo dấu -0.073 | 0.596 |  |
| C | mọi | X2 | 166 / -0.071 | 210 / -0.083 | 74 / -0.189 · 108 / -0.070 | 92 / +0.024 · 102 / -0.096 | xáo dấu -0.081 | 0.494 |  |
| C | 1 | X1 | 79 / -0.158 | 48 / -0.012 | 35 / -0.264 · 29 / -0.000 | 44 / -0.073 · 19 / -0.029 | xáo dấu -0.058 | 0.400 |  |
| C | 1 | X2 | 79 / -0.217 | 48 / +0.042 | 35 / -0.439 · 29 / +0.125 | 44 / -0.041 · 19 / -0.084 | xáo dấu -0.064 | 0.294 |  |
| B | — | X1 | 232 / -0.132 | 286 / -0.077 | 120 / -0.190 · 140 / -0.046 | 112 / -0.070 · 146 / -0.106 | không tin -0.010 (552) | 0.852 |  |
| B | — | X2 | 232 / -0.124 | 286 / -0.085 | 120 / -0.214 · 140 / -0.020 | 112 / -0.029 · 146 / -0.148 | không tin +0.047 (552) | 0.960 |  |

## Cùng / ngược phía EMA200 H4 (mô tả)

| Biến thể | Kỳ | Cùng phía | Ngược phía |
|---|---|---|---|
| S 0.0 X1 | train | 335 / -0.303 | 359 / -0.156 |
| S 0.0 X1 | validate | 350 / -0.241 | 377 / -0.178 |

## Test 2026 (mở một lần)

Không có biến thể nào được chọn → **2026 vẫn niêm phong**.

## Kết luận

**G129 không đạt.** Cả 10 biến thể đều âm ở train hoặc validate, và không tốt hơn đối chứng (p 0,29–0,96). 2026 vẫn niêm phong.

- **Thị trường phản ánh tin ngay trong nến tin.**
  - Nến M30 chứa tin đi cùng chiều bất ngờ 54% (train) / 56% (validate), trung bình +0,17 / +0,42 ATR.
  - Sau khi nến đó đóng, **dấu bất ngờ không còn thông tin**: vào theo bất ngờ (S) cho −0,18 đến −0,29R, ngang mức đối chứng xáo trộn dấu (−0,11 đến −0,20).
- **Có xác nhận (C)** đỡ hơn (khoảng −0,08R), nhưng vẫn âm và không hơn đối chứng. Chỉ |z| ≥ 1 với X2 trên validate là +0,04 (48 lệnh), còn train −0,22.
- **Theo nến tin lớn (B)** còn tệ hơn cùng luật ở cùng giờ những ngày không có tin (−0,08 so với −0,01 / +0,05). Spread rộng sau tin làm mất thêm.
- **Lọc phía EMA200 H4 không giúp**: lệnh cùng phía còn tệ hơn ngược phía.
- Giống FX01 với EUR/GBP: **giao dịch theo số liệu tin sau khi nến tin đóng không có lợi thế**. News Guard hiện tại của EA (đứng ngoài quanh tin) là cách đúng.
