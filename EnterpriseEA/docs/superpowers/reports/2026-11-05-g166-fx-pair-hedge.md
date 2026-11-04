# G166 — BẢN SƠ BỘ: bot hedge cặp FX (EURGBP / EURJPY / GBPJPY tổng hợp từ ba cặp USD) (05/11/2026)

> **Bản sơ bộ trên dữ liệu ingest QTL** (H1, giờ UTC), không phải dữ liệu MT5 của broker. Không có spread theo nến, nên chi phí và swap là mức cố
> định đăng ký trước.

[Kế hoạch](../plans/2026-11-05-g166-fx-pair-hedge.md) (commit `9f84cc6`, đăng ký trước khi chạy).
- Script: [`research/long/g166_fx_pair_hedge.py`](../../research/long/g166_fx_pair_hedge.py).
- Kết quả: `research/long/results/g166/summary.json`.

## Kết luận

**KHÔNG ĐẠT ở cả ba chéo.**

- **X1 EURGBP:** trượt ngay ở bước chọn. Không cấu hình nào có MAR > 0 ở kỳ chọn 2010–2017 (với ≥ 30 rổ). Cả 32 cấu hình đều âm ở kỳ chọn.
- **X2 EURJPY:** đạt 1 / 6 tiêu chí. Tổng R hai kỳ kiểm gần như 0 (+0,04), p ngẫu nhiên 0,51, chi phí bi quan thì âm.
- **X3 GBPJPY:** đạt 4 / 6 tiêu chí, là chéo gần đạt nhất. Nhưng kỳ kiểm 2 gần 0 (PF 1,02), p ngẫu nhiên 0,07, so với ngưỡng 0,0167.

Lý do gốc **giống G165**: chênh lệch giữa các đồng tiền **hồi quy quá chậm** so với khung giữ lệnh của một bot.

| Chéo | Half-life ở kỳ chọn (D1) | Half-life ở kỳ chọn (H4) |
|---|---|---|
| EURGBP | 185 ngày | 1.158 nến (≈ 190 ngày) |
| EURJPY | 265 ngày | 1.754 nến |
| GBPJPY | 388 ngày | 2.521 nến |

Trong khi đó, z-score tính trên 20–60 nến và giữ tối đa 3 × N nến. Phần lãi nhỏ có được chủ yếu đến từ việc trung bình trượt đuổi theo giá, không phải
từ việc chênh lệch quay về.

**Hướng hedge hai chân FX kiểu hồi quy z-score ngắn hạn: đóng.** Cùng với G158–G165, mọi dạng hedge trong khả năng dữ liệu hiện có đều đã thử.

## Dữ liệu

- 99.565 nến H1 chung của cả ba mã, từ 04/01/2010 đến 02/10/2026.
- Lỗ 10/2025 → 26/06/2026 (GBPUSD, USDJPY thiếu) được phát hiện như một lỗ > 120 giờ. Có **1 rổ** bị đóng do lỗ này.
- Kỳ kiểm 2 vì thế là 2022 → khoảng 10/2025. Phần 26/06–02/10/2026 chỉ để xem.

**Sửa lỗi trong lúc chạy (không đổi luật).** Lần chạy đầu đọc giờ sai đơn vị: pandas 3 lưu thời gian theo micro giây, script chia cho 10⁹ như với
nano giây. Hậu quả:
- swap gần như bằng 0;
- không phát hiện được lỗ dữ liệu.

Đã sửa (`as_unit("s")`) và chạy lại toàn bộ 96 cấu hình. Mọi số trong báo cáo là của lần chạy sau khi sửa. Ở lần chạy lỗi, X1 có lọt qua bước chọn và X2 /
X3 trông đẹp hơn. Swap thật chiếm 0,14–0,24 R mỗi rổ, đủ để xóa phần lãi đó.

## Cấu hình được chọn

Ô: số rổ / tổng R / PF / DD (R).

| Chéo | Cấu hình | Chọn 2010–17 | Kiểm 1 2018–21 | Kiểm 2 2022–25 | Xem 06–10/2026 |
|---|---|---|---|---|---|
| X1 EURGBP | không có (trượt ở bước chọn) | tốt nhất theo R: D1 M1 N60 k2,0 X0, 29 / −6,3 / 0,71 / 13,2 | | | |
| X2 EURJPY | D1, M1, N20, k2,5, X0 | 30 / +5,0 / 1,26 / 8,9 | 15 / **−3,8** / 0,67 / 6,8 | 15 / +3,8 / 1,31 / 6,0 | 3 / −0,6 |
| X3 GBPJPY | D1, M2, N60, k2,0, X0 | 47 / +2,4 / 1,07 / 12,6 | 30 / +11,4 / 2,17 / 3,7 | 26 / **+0,4 / 1,02** / 6,9 | 3 / +2,5 |

## Tiêu chí

| # | Điều kiện | X2 EURJPY | X3 GBPJPY |
|---|---|---|---|
| 1 | Kiểm 1 và kiểm 2 đều R > 0, PF ≥ 1,2, ≥ 20 rổ | trượt (kiểm 1 âm, 15 rổ) | trượt (kiểm 2 PF 1,02) |
| 2 | p ngẫu nhiên ≤ 0,0167 | trượt: 0,51 (thật +0,04; ngẫu nhiên p50 +0,13, p95 +7,8) | trượt: 0,070 (thật +11,8; p50 +2,8, p95 +12,5) |
| 3 | Mua và bán chênh lệch đều ≥ 0 | trượt (+8,5 / −8,5) | đạt (+6,8 / +5,0) |
| 4 | Chi phí bi quan vẫn > 0 | trượt (−8,3) | đạt (+3,5) |
| 5 | DD kỳ kiểm ≤ 1,5 × DD kỳ chọn | đạt | đạt |
| 6 | ≥ 2 / 3 láng giềng có R kỳ kiểm > 0 | trượt (0 / 3) | đạt (2 / 3) |
| | **Tổng** | **1 / 6** | **4 / 6** |

## Đọc thêm (không phải tiêu chí)

- **Đánh theo đà** (cùng lúc vào, cùng thời gian giữ, chiều ngược lại) âm ở mọi kỳ, cả ba chéo. Như G165: không chiều nào kiếm được tiền sau chi phí.
- **Tương quan với vàng:**
  - EURJPY −0,28;
  - GBPJPY +0,41, chưa đủ trung tính để làm hedge cho danh mục vàng;
  - EURGBP gần 0 (chỉ đo được ở lần chạy lỗi, vì sau khi sửa thì EURGBP không còn cấu hình được chọn).
- **Toàn lưới 96 cấu hình:** chỉ 5 cấu hình dương ở kỳ chọn (3 X2, 2 X3), và chỉ 1 cấu hình dương ở cả ba kỳ.
- **Tính chất của luật (đã đăng ký, không đổi):** z tính trên cửa sổ trượt N nến nên không vượt quá khoảng (N − 1) / √N.
  - Với N = 20 thì z tối đa khoảng 4,25, nên SL rổ ở |z| ≥ k + 1,5 hầu như không bao giờ chạm (X2: 0 lần SL).
  - Phần lỗ đến từ việc trung bình trượt đuổi theo giá: rổ được tính là "về giữa" ở một mức giá tệ hơn lúc vào.

## Hệ quả

1. **Không có bot hedge cặp FX nào để đưa vào EA.** Không đề xuất SHADOW.
2. **Không cần lấy dữ liệu MT5 của broker để kiểm lại.** Kể cả trong lần chạy có lỗi làm chi phí nhẹ đi, không chéo nào đạt.
3. **Nếu muốn thử lại theo đúng nhịp half-life** (cửa sổ 120–250 ngày, giữ hàng tháng):
   - mỗi năm chỉ được vài rổ;
   - swap hai chân trong nhiều tháng sẽ ăn phần lớn lợi nhuận.

   Đây là một chiến lược đầu tư vĩ mô, không phải bot. Muốn làm thì phải viết kế hoạch riêng.
4. **Ghi vào sổ cái:** 96 cấu hình, 3 chéo được xét, 0 đạt.
