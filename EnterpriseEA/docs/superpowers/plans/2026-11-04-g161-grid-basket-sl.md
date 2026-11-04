# G161: lưới bồi lệnh có SL tổng cho cả rổ, kèm cắt cặp P1 — kế hoạch đăng ký trước (04/11/2026)

Người dùng (04/11) đồng ý chuyển từ lưới không SL sang **lưới có giới hạn lỗ cho cả rổ, kèm P1**. Bối cảnh:
- [G158](../reports/2026-11-04-g158-hedge-recovery.md), [G159a](../reports/2026-11-04-g159a-mechanism-modules.md) và
  [G160a](../reports/2026-11-04-g160a-clue-screen.md) cho thấy lưới không SL luôn cháy trong stress 2010–2018;
- P1 (cắt cặp liên tục) là module duy nhất có ích.

Câu hỏi của G161: **khi đã chặn đuôi lỗ, lưới (bồi lệnh + cắt cặp) còn lợi thế không**, và lợi thế đó có hơn một lệnh đơn có cùng mức lỗ tối đa
không?

## 1. Cơ chế (cố định)

- **Entry:** E4 của G158 (pullback theo trend có volume xác nhận), H1. Lệnh đầu 0,10 lot, khớp ở giá mở nến kế tiếp.
- **Lưới:** bồi cùng chiều mỗi bước S = step × ATR14 D1 (tính lúc mở rổ), lot = 0,10 × mult^n, tối đa `levels` lệnh.
- **P1** luôn bật: ở mỗi nến đóng, nếu (lệnh lời nhất + lệnh lỗ nhất) có tổng ≥ 0 thì đóng cả hai; lặp tới khi không còn cặp.
- **Mục tiêu rổ:** như G158. Tổng thả nổi ≥ 0,5 × S × lot gốc × 100 thì đóng rổ, giữ một lệnh chạy, lệnh chạy chốt TP 3S (X1).
- **SL tổng (mới):** thả nổi của rổ ≤ −L × số dư lúc mở rổ thì **đóng toàn bộ rổ**.
  - Kiểm theo giá bất lợi trong nến, khớp ở mức chạm trừ trượt giá.
  - Nếu giá mở nến đã vượt mức thì khớp ở giá mở (gap).
- **Không cần SL riêng cho lệnh chạy:** lệnh chạy chỉ xuất hiện sau khi rổ đã đạt mục tiêu, và mỗi lần nó quay ngược S thì rổ khởi động lại (như G158).
  Mức lỗ tối đa vẫn giới hạn bởi SL tổng.
- **Mô hình tài khoản như G158:** 10.000 USD, 1:500, stop-out 50 %, swap −30 / lot / đêm, phí 6 USD / lot, trượt giá 0,5 × spread trung vị.

## 2. Lưới tham số (24 cấu hình)

| Tham số | Giá trị |
|---|---|
| mult | 1,0; 1,5 |
| levels | 4; 6 |
| step | 0,5; 1,0 ATR D1 |
| L (SL tổng, % số dư lúc mở rổ) | 2 %; 4 %; 6 % |

## 3. Đối chứng

- **C1 — lệnh đơn cùng rủi ro:** cùng entry E4, một lệnh, không bồi. SL ở khoảng cách sao cho lỗ = L × số dư (cùng L), TP = 3 × SL. Chạy cho cả
  24 cấu hình, ghép theo cùng step / L. Câu hỏi: **lưới có hơn một lệnh đơn có cùng mức lỗ tối đa không**.
- **C2 — entry ngẫu nhiên:** 50 lần, cùng số entry, cùng cơ chế, 05/2018–10/2026. Câu hỏi: lợi thế đến từ entry hay từ cơ chế.
- **C3 — tắt P1:** chỉ cho cấu hình được chọn. Câu hỏi: P1 có đóng góp không.

## 4. Chọn và kiểm (chọn một lần)

**Kỳ:**
- chọn 05/2018–2022;
- kiểm 2023–10/2026;
- stress D1 2010–02/2018 (bi quan, chỉ đo cơ chế).

**Chọn:** trong các cấu hình có 0 cháy và lãi > 0 ở kỳ chọn, lấy cấu hình có **MAR (lãi ròng / DD lớn nhất) cao nhất** ở kỳ chọn. Chỉ cấu hình này
được xét đạt / trượt. 23 cấu hình còn lại chỉ báo cáo.

**Đạt khi cấu hình được chọn thỏa cả 8:**

1. **Kỳ kiểm:** 0 cháy, lãi ròng > 0, profit factor theo rổ ≥ 1,1.
2. **DD lớn nhất < 30 %** cả kỳ, theo giá bất lợi trong nến. Đây là giới hạn tài khoản đang dùng.
3. **Xác suất cháy 12 tháng = 0**, và **xác suất DD 12 tháng ≥ 30 % ≤ 5 %** (mở tài khoản mỗi tháng 2018–2025).
4. **Swap −60 và chi phí × 1,5:** lãi ròng cả kỳ > 0.
5. **Stress D1 2010–2018:** 20 lần × 60 entry ngẫu nhiên. 0 lần cháy, và DD trung vị < 30 %.
6. **Hơn lệnh đơn (C1):** MAR kỳ kiểm của lưới > MAR kỳ kiểm của lệnh đơn cùng step / L.
7. **Hơn ngẫu nhiên (C2):** lãi ròng cả kỳ > phân vị 95 % của entry ngẫu nhiên.
8. **Láng giềng:** ≥ 2 / 3 cấu hình láng giềng thỏa 1 và 2. Láng giềng là đổi một tham số sang giá trị bên cạnh: L ± một nấc, step, levels, mult.

## 5. Output

**Mỗi cấu hình, mỗi kỳ:**
- số rổ;
- tỷ lệ rổ thắng;
- lãi TB rổ thắng / lỗ TB rổ thua;
- **kỳ vọng theo R** (R = L × số dư lúc mở rổ);
- số lần chạm SL tổng;
- lý do kết thúc rổ (mục tiêu / cặp / lệnh chạy / SL / cháy);
- lot tối đa;
- DD;
- MAR;
- swap / lãi gộp;
- ES 5 % rổ.

**Nếu đạt:** viết kế hoạch đưa vào EA ở chế độ SHADOW (chỉ ghi nhật ký) trước, như SQZ / W1. Không chạy thật khi chưa có kết quả forward.

Script `research/long/g161_grid_sl.py`, dùng lại engine `g159a_modules.simulate` (thêm tham số SL tổng; khi L = vô hạn và P1 tắt, kết quả phải
khớp G158 E4 để kiểm code). Kết quả ghi vào `research/long/results/g161/`. Không chỉnh luật sau khi chạy. 24 + 1 phép thử ghi vào sổ cái.
