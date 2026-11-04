# G159a: sửa cơ chế bồi lệnh trên nền E4 — không bồi ngược D1, khóa hedge, ký quỹ tối thiểu, trần lot, cắt cặp — kế hoạch đăng ký trước (04/11/2026)

Theo [khung G159](2026-11-04-g159-hedge-refine-framework.md), thứ tự 1–2. Nền là cấu hình gần đạt nhất của [G158](../reports/2026-11-04-g158-hedge-recovery.md):
- **entry E4** (pullback theo trend có volume xác nhận);
- lưới bồi cùng chiều × 1,5, bước 0,5 ATR D1, tối đa 10 lệnh;
- lệnh chạy TP 3S.

E4 trượt ở ba chỗ:
- DD 53 %;
- stress 2010–2018 (35 % lần chạy cháy);
- láng giềng 2 / 4.

Mô hình tài khoản, dữ liệu, kỳ như G158 (H1 thật; chọn 05/2018–2022, kiểm 2023–10/2026; stress D1 2010–2018 bi quan).

## Module (định nghĩa cố định)

| Mã | Module | Quy tắc |
|---|---|---|
| F1 | **Không bồi ngược D1** | khi chế độ D1 (R1) = ngược chiều rổ: không mở lệnh bồi (chỉ giữ). Chế độ trung tính hoặc cùng chiều thì bồi như nền |
| H1 | **Khóa khi D1 đổi chiều** | chế độ D1 chuyển sang ngược chiều rổ thì mở một lệnh hedge ngược chiều, lot = tổng lot rổ (thả nổi đứng yên). **Mở khóa** (đóng lệnh hedge, ở giá đóng H1) khi chế độ D1 hết ngược chiều, hoặc lệnh hedge lời ≥ 1 × S |
| H2 | **Khóa khi cấu trúc H4 gãy** | H4 đóng qua swing H4 gần nhất (pivot 3 / 3, đáy với rổ mua, đỉnh với rổ bán) tính từ lúc mở rổ thì khóa như H1. **Mở khóa** khi H4 đóng quay lại qua mức đó, hoặc lệnh hedge lời ≥ 1 × S |
| F5 | **Ký quỹ tối thiểu để bồi** | mức ký quỹ < 300 % thì không bồi thêm |
| F6 | **Trần lot** | tổng lot mở của rổ ≤ 1,0 (10 × lot gốc); lệnh bồi vượt trần thì bỏ |
| P1 | **Cắt cặp liên tục** | ở mỗi nến đóng: (lệnh lời nhất + lệnh lỗ nhất) có tổng ≥ 0 thì đóng cả hai. Lặp tới khi không còn cặp |

**Khi đang khóa:**
- không bồi;
- tổng rổ (gồm lệnh hedge) ≥ mục tiêu thì đóng hết, không giữ lệnh chạy.

Không có SL ở bất kỳ module nào.

## Cấu hình chạy

- **Nền** (không module): phải tái tạo y hệt kết quả G158 E4 trên kỳ chọn (kiểm code).
- **Từng module riêng:** 6 cấu hình.
- **Tổ hợp:** mọi cặp và bộ ba của 6 module, trừ những tổ hợp có cả H1 lẫn H2 (hai kiểu khóa loại trừ nhau): 14 cặp + 16 bộ ba.

Tổng 37 cấu hình (gồm nền).

## Đạt khi (như (B) của G158, thêm 2 điều)

1. Kỳ chọn và kỳ kiểm đều **0 lần cháy**, lãi ròng > 0.
2. **Xác suất cháy trong 12 tháng = 0** (mở tài khoản mỗi tháng 2018–2025).
3. **Sụt vốn lớn nhất < 50 %**, theo giá bất lợi trong nến, cả kỳ.
4. Swap −60 và chi phí × 1,5: vẫn 0 cháy, lãi > 0.
5. **Stress D1 2010–2018**: entry ngẫu nhiên, 20 lần, mỗi lần 60 entry. **0 lần cháy** ở mọi lần chạy.
6. **Láng giềng:** ≥ 2 / 3 cấu hình đổi bước (0,5 ↔ 1,0), số lệnh tối đa (10 ↔ 6) hoặc hệ số (1,5 ↔ 1 / 2) cũng thỏa 1 và 2.
7. **Mới — expected shortfall:** trung bình 5 % rổ tệ nhất không tệ hơn nền.
8. **Mới — swap:** tổng swap ≤ 30 % tổng lãi gộp của các rổ có lời.

Cấu hình đạt được so tiếp với **50 lần entry ngẫu nhiên** cùng module (như (A) của G158), để biết phần lãi có đến từ entry E4 không.

**Thứ tự báo cáo:** mọi cấu hình đều được báo cáo. Cấu hình đạt (nếu có) xếp theo lãi ròng cả kỳ.

Script `research/long/g159a_modules.py`, kết quả `research/long/results/g159a/`. Không chỉnh luật sau khi chạy.
