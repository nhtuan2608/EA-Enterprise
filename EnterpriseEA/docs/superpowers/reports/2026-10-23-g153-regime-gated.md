# G153 — chấm lại 7 ứng viên theo chế độ thị trường D1 (23/10/2026)

Kế hoạch đăng ký trước: [2026-10-23-g153-regime-gated.md](../plans/2026-10-23-g153-regime-gated.md) (commit `a3cf66a`). Script
[`g153_regime_gated.py`](../../research/long/g153_regime_gated.py). Chế độ = luật R1 của XauRegime trên D1 (close vs EMA50 và dốc EMA50 10 ngày).
"Cùng chế độ" = xu hướng D1 cùng chiều lệnh.

**Nhắc lại giới hạn**: các ứng viên đã được nhìn ở G139 / G143 / G149, nên cổng chế độ là quyết định sau khi nhìn. Phần chuyển sang BTC là phép
thử mới duy nhất.

## Kết quả (R/lệnh, chi phí harsh)

| Ứng viên | Không lọc: 2018–21 / 22–23 / 24–26 | **Cùng chế độ**: 2018–21 / 22–23 / 24–26 | Ngược chế độ | Mua / bán (cùng chế độ) | ×1,5 / bỏ 5 lệnh lớn | p đối chứng cùng chế độ | **BTC** cùng chế độ (không lọc) | Kết luận |
|---|---|---|---|---|---|---|---|---|
| **C-M30 squeeze breakout** | −0,25 / −0,18 / +0,29 | **+0,03 / −0,13 / +0,32** (123 / 67 / 163) | −0,31 | +0,23 / −0,40 | +0,10 / +0,09 | **0,005** | **+0,07** (−0,09) | KHÔNG ĐẠT (2022–23 âm, lệnh bán âm) |
| **W1 phá đỉnh/đáy tuần** | −0,02 / +0,05 / +0,15 | **+0,11 / −0,06 / +0,47** (70 / 49 / 65) | −0,14 | +0,35 / −0,14 | +0,18 / +0,06 | 0,13 | **+0,32** (+0,17) | KHÔNG ĐẠT (2022–23 âm, p) |
| C-H1 squeeze | −0,33 / −0,17 / +0,28 | −0,26 / −0,13 / +0,31 | −0,18 | +0,10 / −0,36 | −0,00 / −0,06 | 0,52 | −0,27 | KHÔNG ĐẠT |
| A1-M30 pullback | −0,36 / +0,11 / +0,04 | −0,20 / +0,07 / −0,05 | −0,18 | −0,04 / −0,17 | âm | 0,20 | −0,24 | KHÔNG ĐẠT |
| A1-H1 pullback | −0,14 / −0,06 / +0,19 | −0,00 / −0,15 / +0,09 | +0,05 | +0,13 / −0,21 | âm | 0,28 | −0,25 | KHÔNG ĐẠT |
| K3 limit hồi | −0,19 / −0,17 / −0,11 | −0,21 / −0,16 / −0,04 | −0,17 | âm | âm | 0,92 | −0,29 | KHÔNG ĐẠT |
| NY momentum | +0,24 / +0,18 / +0,07 | +0,18 / +0,04 / +0,11 (3 / 14 / 16 lệnh) | +0,24 | +0,31 / −0,36 | +0,08 / −0,13 | 0,17 | không áp | KHÔNG ĐẠT (quá ít lệnh) |

Tham chiếu: **S07 M30 theo cùng bộ nhận chế độ**

| | 2018–21 | 2022–23 | 2024–26 |
|---|---|---|---|
| cùng chế độ | 336 / **+0,21** | 212 / **+0,17** | 422 / **+0,65** |
| ngược chế độ | 37 / −0,26 | 12 / +0,17 | 44 / −0,15 |

## Đọc kết quả

1. **Cổng chế độ D1 có giá trị thật.** Nó làm 4 / 7 ứng viên tốt hơn ở ≥ 2 / 3 kỳ. Với S07, lệnh cùng chế độ dương ở cả 3 kỳ, còn lệnh ngược chế độ
   âm ở 2 / 3 kỳ. Đây là cùng hướng với trọng số D1 × 0,5 đã có trong EA.
2. **Hai ứng viên đáng chú ý dưới chuẩn mới**, dù không đạt đủ 6 tiêu chí:
   - **C-M30 squeeze breakout (cùng chế độ)** là ứng viên duy nhất **thắng lệnh ngẫu nhiên trong cùng chế độ** (p 0,005). Nghĩa là nó có giá trị
     **ngoài phần ăn theo xu hướng**. Nó cũng bền với chi phí × 1,5, bỏ 5 lệnh lớn vẫn dương, và **dương trên BTC** (+0,07R trên 312 lệnh, trong
     khi không lọc là −0,09). Điểm yếu: 2022–23 −0,13R (67 lệnh) và lệnh bán âm.
   - **W1 phá đỉnh / đáy tuần (cùng chế độ)**: lãi lớn hơn (+0,47R ở 2024–26, BTC +0,32R), nhưng chưa thắng ngẫu nhiên cùng chế độ (p 0,13). Phần
     lớn lãi có thể chỉ là ăn theo xu hướng.
3. Lệnh bán của mọi ứng viên đều âm kể cả khi có cổng chế độ. Trên vàng 2018–2026, xu hướng giảm D1 ngắn và hay bị đảo, nên lệnh bán theo xu hướng
   khó có lãi.

## Kết luận

Theo luật đăng ký: **không ô nào ĐẠT**.

Đề xuất (người dùng quyết định): chạy **SHADOW** hai ứng viên trong bots host để thu dữ liệu forward, có cổng chế độ D1, không ảnh hưởng lệnh thật:
- C-M30 squeeze breakout;
- W1 phá đỉnh / đáy tuần.

Sau ≥ 30 lệnh mỗi ứng viên thì xét lại. Cần sửa EA (thêm hai module bot SHADOW), nên chỉ làm khi người dùng đồng ý.
