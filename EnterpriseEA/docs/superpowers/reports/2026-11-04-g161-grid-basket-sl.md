# G161: lưới có SL tổng kèm P1 — báo cáo (04/11/2026)

[Kế hoạch](../plans/2026-11-04-g161-grid-basket-sl.md) · script `research/long/g161_grid_sl.py` · kết quả `research/long/results/g161/summary.json`

## Kết luận

**KHÔNG ĐẠT** (6 / 8). SL tổng giải quyết được chuyện cháy: 0 cháy ở mọi kỳ, kể cả stress 2010–2018. Nhưng lưới **không có lợi thế**:
- **kém hơn một lệnh đơn cùng mức lỗ tối đa** (tiêu chí 6);
- **không hơn entry ngẫu nhiên** (tiêu chí 7);
- **P1 làm kết quả tệ hơn** khi đã có SL tổng.

**Kiểm code:** không SL và tắt P1 thì kết quả khớp G158 E4.

**Sửa lỗi trong lúc chạy** (không đổi luật):
- lần chạy đầu, nhánh lệnh đơn C1 không tính DD, nên báo DD = 0;
- đã sửa và chạy lại. Cấu hình được chọn và mọi số của lưới không đổi; chỉ DD / MAR của C1 thay đổi.

## Cấu hình được chọn

Chọn theo MAR ở kỳ chọn: **mult 1,0, levels 4, step 0,5 ATR D1, SL tổng 6 %**.

| | Kỳ chọn 05/2018–2022 | Kỳ kiểm 2023–10/2026 | Cả kỳ |
|---|---|---|---|
| Lãi ròng (vốn 10.000) | +2.087 | +943 | +3.094 |
| DD lớn nhất | 17,6 % | 23,9 % | 22,1 % |
| MAR | 1,19 | 0,39 | 1,40 |
| PF theo rổ | 1,39 | 1,14 | 1,25 |
| Số rổ / tỷ lệ thắng | 51 / — | 27 / 66,7 % | 78 / 70,5 % |
| Kỳ vọng theo R | +0,07 | +0,08 | +0,07 |
| Lot mở tối đa | | 0,3 | 0,4 |

Lý do kết thúc rổ (cả kỳ):
- lệnh chạy 32;
- cặp P1 17;
- SL 16;
- mục tiêu 13.

Rổ thắng TB +280, rổ thua TB −535.

## Tiêu chí

| # | Tiêu chí | Kết quả | |
|---|---|---|---|
| 1 | Kỳ kiểm 0 cháy, lãi > 0, PF ≥ 1,1 | 0 cháy, +943, PF 1,14 | đạt |
| 2 | DD < 30 % | 22,1 % | đạt |
| 3 | Cháy 12 tháng = 0; DD 12 tháng ≥ 30 % ≤ 5 % | 0; 0 | đạt |
| 4 | Swap −60, chi phí × 1,5: lãi > 0 | +1.367 | đạt |
| 5 | Stress D1 2010–2018: 0 cháy, DD trung vị < 30 % | 0 / 20 cháy, DD trung vị 29 %, lãi trung vị +3.619 | đạt (sát) |
| 6 | MAR kỳ kiểm > lệnh đơn C1 (SL 6 %, TP 3R) | 0,39 so với **4,41** (C1: +9.615, DD 21,8 %, PF 1,95) | **trượt** |
| 7 | Lãi cả kỳ > p95 entry ngẫu nhiên | +3.094 so với p95 **+7.706** (trung vị −1.396, DD trung vị 47 %) | **trượt** |
| 8 | Láng giềng ≥ 2 / 3 | 3 / 4 | đạt |

## Đối chứng

**C1 — lệnh đơn cùng entry E4, cùng mức lỗ tối đa, TP 3R.**

| SL | Kỳ chọn: lãi / DD / PF | Kỳ kiểm: lãi / DD / PF |
|---|---|---|
| 2 % | −1.033 / 23 % / 0,79 | +2.302 / 16 % / 1,61 |
| 4 % | +2.235 / 33 % / 1,29 | +3.705 / 28 % / 1,49 |
| 6 % | −1.968 / 47 % / 0,72 | +9.615 / 22 % / 1,95 |

Lệnh đơn cũng **không ổn định giữa hai kỳ**. Cả lưới lẫn lệnh đơn đều thắng ở 2023–2026 (vàng tăng mạnh) và gần hòa vốn ở 2018–2022. Cái
"lợi thế" phần lớn đến từ xu hướng tăng của kỳ kiểm, không phải từ entry hay cơ chế.

**C3 — tắt P1** (cùng cấu hình):
- cả kỳ +4.279, DD 20,1 %;
- MAR kỳ chọn 1,75, so với 1,19 khi bật P1.

Khi đã có SL tổng, P1 cắt mất các lệnh lời đáng lẽ kéo cả rổ về mục tiêu. Nó chỉ có ích khi rổ không có SL (G159a).

## Quan sát thêm

- **levels 4 và 6 cho kết quả giống hệt:** SL tổng luôn chạm trước lệnh bồi thứ 5. Lưới thực chất chỉ có tối đa 4 lệnh.
- **Kết quả đảo giữa hai kỳ:**
  - SL 2 % xếp gần chót ở kỳ chọn nhưng tốt nhất ở kỳ kiểm (MAR 2,9);
  - SL 6 % thì ngược lại.

  Thứ hạng không giữ được giữa hai kỳ, dấu hiệu của nhiễu.
- **Stress 2010–2018 không cháy, lãi trung vị dương với entry ngẫu nhiên:** nhờ SL tổng, cơ chế đã an toàn. Nhưng an toàn không có nghĩa là có
  lợi thế (tiêu chí 7).

## Hệ quả

1. **Lưới có SL tổng: an toàn nhưng không có lợi thế** so với một lệnh đơn có cùng rủi ro. Bồi lệnh chỉ thêm phí, swap và độ phức tạp.
2. **Hướng bồi lệnh / hedge trên vàng (G158–G161) đóng hẳn**, cả dạng có SL lẫn không SL.
   - Phần còn dùng được: tư duy SL theo % vốn cho cả nhóm lệnh. Đây là thứ VHedge / S07 đã làm.
3. **E4 (pullback có volume xác nhận) không vững làm entry.** Với lệnh đơn, kết quả âm ở 2018–2022 và dương ở 2023–2026. Không nên dùng nó làm setup
   riêng.
4. **Ghi vào sổ cái:** 24 + 1 phép thử; cấu hình được chọn trượt.
