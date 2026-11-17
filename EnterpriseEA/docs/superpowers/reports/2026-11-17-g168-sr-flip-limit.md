# G168: lệnh chờ tại vùng S/R theo chiều D1 (kiểu LFX) — báo cáo (17/11/2026)

[Kế hoạch](../plans/2026-11-17-g168-sr-flip-limit.md) · script `research/long/g168_sr_flip.py` · kết quả `research/long/results/g168/summary.json`

## Kết luận

**KHÔNG ĐẠT: 0 / 8.** Cả hai biến thể âm ở cả hai kỳ. Điều đáng chú ý nhất: **lệnh chờ ở mức S/R thật còn tệ hơn ở mức giả** cùng khoảng cách.
- Mức thật: −44,3 R cả kỳ.
- Mức giả: trung vị −4,4 R, p95 +16,1 R.

Vùng đỉnh / đáy swing H1 là nơi giá **hay xuyên qua** (quét stop) hơn là nơi giá dừng lại. Điều này khớp với G160a: pivot ngày không phải chỗ dừng.

Đặt chờ cũng **không hơn vào ngay** ở giá thị trường (C2). Không có setup mới từ hướng này.

**Kiểm code:** lệnh F đầu tiên (đặt 02/05/2018 17:00 server, khớp 18:00 ở 1307,08) chạm SL; tính tay trên nến M30 cũng chạm SL trước.

## Hai biến thể

05/2018 → 17/11/2026, nến M30, chi phí đầy đủ, 3 phần TP 1 R / 2 R / swing đối diện + BE sau TP1.

| Biến thể | Kỳ | Lệnh (/ tuần) | Thắng | R TB | Tổng R | PF | DD R | Mua / bán R TB |
|---|---|---|---|---|---|---|---|---|
| **F — S/R flip** (mức vừa bị phá) | chọn 2018–22 | 316 (1,3) | 53 % | −0,057 | −17,9 | 0,88 | 35,0 | +0,01 / −0,13 |
| | kiểm 2023–26 | 260 (1,3) | 50 % | −0,101 | −26,3 | 0,80 | 35,6 | −0,05 / −0,23 |
| **R — kháng cự / hỗ trợ chưa phá** | chọn | 945 (3,9) | 48 % | −0,118 | −111,6 | 0,78 | 116,1 | −0,08 / −0,16 |
| | kiểm | 779 (3,9) | 52 % | −0,024 | −19,0 | 0,95 | 53,1 | −0,03 / −0,02 |

**Được chọn:** F, MAR kỳ chọn ít âm hơn. Chờ khớp TB 4 giờ, giữ TB ~9 giờ.

**Lý do thoát (F, kỳ kiểm):**
- SL 129;
- BE 91;
- TP3 35;
- hết giờ 5.

## Tiêu chí (F)

| # | Tiêu chí | Kết quả | |
|---|---|---|---|
| 1 | Kỳ kiểm R > 0, PF ≥ 1,2, ≥ 50 lệnh | −26,3 R, PF 0,80 | trượt |
| 2 | R TB > 0 hai kỳ, CI > 0 | −0,06 / −0,10; CI [−0,18; +0,02] | trượt |
| 3 | Hơn p95 mức giả | −44,3 so với p95 +16,1 (p50 −4,4) | trượt |
| 4 | Hơn vào thị trường (C2) | R TB −0,077 so với −0,034 | trượt |
| 5 | Mua và bán ≥ −0,05 | bán −0,17 | trượt |
| 6 | Chi phí × 1,5 vẫn > 0 | −65,6 | trượt |
| 7 | Láng giềng ≥ 4 / 6 | 0 / 6 (kỳ kiểm −3 … −25,5 R) | trượt |
| 8 | DD ≤ 15 R | 63 R | trượt |

## Đọc thêm

- **Theo năm (F):**

  | Năm | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
  |---|---|---|---|---|---|---|---|---|---|
  | Tổng R | −18,8 | −8,6 | −1,4 | +3,9 | +7,1 | −22,7 | +0,8 | −4,9 | +0,5 |

  Không ổn định.
- **Bỏ cổng D1 (C3):** −149 R. Cổng D1 có giúp, nhưng không đủ.
- **Độ nhạy M5** (06/2024 →): −8,4 R so với −9,4 R trên M30. Kết quả không do độ thô của nến M30.
- **Cửa sổ 04–17/11/2026:** rule đặt 3 lệnh sell (4104,7; 4071,5; 3866,3), đều đóng BE với +0,3 R. Không trùng chính xác vùng của LFX. LFX chọn vùng bằng mắt, có
  yếu tố ngoài luật (vùng giá "đẹp", chọn lọc).

## Hệ quả

1. **Đặt lệnh chờ ở đỉnh / đáy swing H1, kể cả theo chiều D1, không có lợi thế** trên vàng 2018–2026. Mức thật còn tệ hơn mức ngẫu nhiên.
2. Kết quả 8 kèo LFX (3 thắng / 2 thua) nằm trong biến động ngẫu nhiên của một hệ có kỳ vọng âm nhẹ. Không có bằng chứng phương pháp đó tạo lợi thế bền.
3. **Hướng "phục kích ở vùng thanh khoản" (G160b) coi như đã trả lời: không.**
4. **Ghi vào sổ cái:** 2 phép thử, 0 đạt.
