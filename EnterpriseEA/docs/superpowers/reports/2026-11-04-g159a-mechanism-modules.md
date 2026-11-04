# G159a: module cơ chế trên nền E4 — báo cáo (04/11/2026)

[Kế hoạch](../plans/2026-11-04-g159a-mechanism-modules.md) · script `research/long/g159a_modules.py` · kết quả `research/long/results/g159a/summary.json`

## Kết luận

**KHÔNG ĐẠT.** Không cấu hình nào trong 37 cấu hình qua được. Điều kiện chặn là **stress D1 2010–2018**: cấu hình tốt nhất vẫn cháy ở 6–8 / 20 lần chạy. Ở
cùng phép đo, nền cháy 6 / 20.

**Kiểm code:** khi tắt mọi module, kết quả kỳ chọn khớp đúng G158 E4 (lãi 13.703, DD 0,528, 0 cháy).

| | Kết quả |
|---|---|
| Module có ích nhất | **P1** (cắt cặp liên tục): DD 52,8 → 49,4 %, láng giềng 2 / 4 → 3 / 4, đạt 6 / 8 tiêu chí |
| Hơi có ích | **F1** (không bồi ngược D1): kỳ chọn +1.600, kỳ kiểm không đổi; không giảm DD |
| Có hại | **H1 / H2** (khóa hedge): lãi giảm, ES tệ đi 30 lần, stress nhiều cháy hơn (9–14 / 20). H2 làm thả nổi tệ nhất −29.000 |
| Có hại | **F6** (trần lot 1,0): DD tăng lên 75 %, xuất hiện cháy 12 tháng (8,7 %). Ít lot hơn thì giá phải quay về xa hơn mới đạt mục tiêu |
| Không tác dụng | **F5** (ký quỹ ≥ 300 % mới bồi): không lần nào chặn, kết quả y hệt nền |

## Bảng chính

Cả kỳ = 05/2018–10/2026. Stress = số lần chạy cháy trên 20 (D1 2010–2018, mỗi lần 60 entry ngẫu nhiên). Tiêu chí trượt đánh số như kế hoạch:
- 3 = DD;
- 5 = stress;
- 6 = láng giềng;
- 7 = ES;
- 2 = cháy 12 tháng.

| Module | Lãi ròng cả kỳ | DD | Thả nổi tệ nhất | Lot tối đa | Stress | Láng giềng | ES 5 % rổ | Đạt / 8 | Trượt |
|---|---|---|---|---|---|---|---|---|---|
| nền | 29.390 | 0,528 | −5.775 | 4,93 | 6 | 2/4 | −31 | 5 | 3, 5, 6 |
| F1 | 30.992 | 0,528 | −5.775 | 4,93 | 7 | 2/4 | −31 | 5 | 3, 5, 6 |
| P1 | 25.112 | 0,494 | −5.775 | 4,93 | 6 | 3/4 | −126 | 6 | 5, 7 |
| F1+P1 | 26.714 | 0,494 | −5.775 | 4,93 | 7 | 3/4 | −126 | 6 | 5, 7 |
| F1+F6+P1 | 24.164 | **0,415** | −6.738 | 0,94 | 8 | 3/4 | −393 | 6 | 5, 7 |
| H2+P1 | 18.746 | 0,379 | −9.402 | 2,74 | 8 | 2/4 | −911 | 5 | 5, 6, 7 |
| H1 | 24.212 | 0,528 | −5.775 | 4,93 | 12 | 1/4 | −1.070 | 4 | 3, 5, 6, 7 |
| H2 | 15.986 | 0,609 | −29.063 | 1,73 | 9 | 1/4 | −1.027 | 4 | 3, 5, 6, 7 |
| F6 | 25.671 | 0,748 | −12.727 | 0,94 | 10 | 3/4 | −750 | 4 | 2, 3, 5, 7 |
| F1+H2 | −643 | 1,0 | −29.063 | 1,73 | 8 | 1/4 | −4.526 | 0 | tất cả (cháy ở kỳ kiểm) |

Đủ 37 dòng trong `summary.json`. Mọi tổ hợp có F5 cho kết quả giống hệt tổ hợp không có F5.

## Đối chứng entry ngẫu nhiên

Không cấu hình nào đạt. Theo kế hoạch, đối chứng chạy cho cấu hình có lãi cả kỳ cao nhất là F1: 50 lần, cùng số entry, cùng module, 05/2018–10/2026.
- **100 % lần chạy có cháy.** Lãi ròng trung vị −27.256; phân vị 95 % là −6.966.
- E4 (+30.992) cao hơn phân vị 95 % của ngẫu nhiên.

Lưu ý: E4 được chọn trên kỳ 2018–2022 (G158), nên phép so sánh cả kỳ có một phần là trong mẫu.

## Đọc kết quả

1. **Nguyên nhân cháy là đường giá, không phải cơ chế.** Ở 2011–2015 vàng giảm một mạch. Cả bồi lệnh, khóa lẫn cắt cặp đều không cứu được
   1/3 số lần chạy. Các module chỉ đổi *cách* thua (sâu hơn hay lâu hơn), không đổi *việc* thua.
2. **Khóa hedge làm tệ hơn.** Lệnh hedge đóng băng thả nổi nhưng vẫn trả swap hai chân. Khi mở khóa, rổ gốc vẫn lỗ sâu và phải bồi tiếp ở giá
   tệ hơn. H2 (phá cấu trúc H4) hay mở khóa / khóa lại liên tục trong biên rộng.
3. **P1 giảm tải thật.** Nó giảm DD và tăng độ vững với láng giềng. Cái giá là ES tệ hơn, vì một số cặp đóng ở tổng âm nhẹ do phí và chênh giá.
   Đây là module đáng giữ cho vòng sau.
4. **Trần lot là ý hay về rủi ro, nhưng hỏng với cơ chế này.** Lưới kiểu martingale cần lot lớn để giá trung bình kịp về gần giá. Cắt lot
   làm rổ phải chờ lâu hơn, nên nhiều rổ chết hơn.

## Hệ quả cho các vòng sau

- **Cơ chế tốt nhất mang sang G160c / G159b:** P1 (có thể thêm F1). H1 / H2 / F6 / F5 đóng ở dạng đã định nghĩa.
- Stress 2010–2018 cho thấy cần **một cổng không cho mở rổ trong xu hướng một chiều dài**. Đó đúng là câu hỏi của **G160a phần A** (cổng đi ngang
  K1–K5), đã đăng ký trước.
- G159b (X8 thoát theo swap, X5–X9) chỉ còn ý nghĩa nếu một cổng K vượt được stress. Nếu không có cổng nào vượt, hướng bồi lệnh không SL trên
  vàng nên đóng.
