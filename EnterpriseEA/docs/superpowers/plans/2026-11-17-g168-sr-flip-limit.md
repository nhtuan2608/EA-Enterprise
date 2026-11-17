# G168: lệnh chờ tại vùng S/R (S/R flip) theo chiều D1 — tái tạo cách vào lệnh của LFX — kế hoạch đăng ký trước (17/11/2026)

## Lý do

[G167 mục 8](../reports/2026-11-17-g167-lfx-signal-forensics.md): 7 chart setup của LFX (04–17/11/2026) cùng một kiểu.

- **Entry:** lệnh **chờ đặt sẵn** (limit) tại vùng hỗ trợ / kháng cự cũ, cách giá 0,5–2,3 ATR H1. 7 / 8 vùng trùng đỉnh / đáy swing H1 trong 10 ngày; thường là
  mức vừa bị phá rồi chờ test lại.
- **Không chờ nến xác nhận.**
- **SL:** sau vùng, ~1,15–1,5 ATR H1.
- **TP:** TP1 gần (~1 R), TP2 ~2 R, TP3 ở vùng đối diện.
- **Chiều:** kèo sell khi D1 / H4 dưới EMA50; kèo buy khi H4 trên EMA50.

Kết quả 8 kèo (5 khớp, 3 thắng, ≈ +1,5 R) quá ít để kết luận. Kiểu vào lệnh này **chưa từng được test**:
- G163 Z2 vào khi nến chạm mức rồi đóng xác nhận;
- G160b (phục kích) chưa chạy.

G168 kiểm nó trên dữ liệu dài. Người dùng duyệt 17/11.

## Dữ liệu

- **XAUUSD MT5:** H1 / M30 thật 05/2018 → 11/2026 (h1v / m30v + terminal đến 17/11/2026).
- **Mô phỏng khớp lệnh và SL / TP:** nến M30, theo luật bi quan (cùng nến chạm SL và TP thì SL trước; giá mở đã vượt mức thì khớp ở giá mở).
- **Kiểm độ nhạy (không phải tiêu chí):** trên M5 từ 05/2024.
- **Kỳ chọn:** 05/2018–2022. **Kỳ kiểm:** 2023 → 17/11/2026.
- **Chi phí:** spread từng nến, trượt giá 0,5 × spread trung vị mỗi chiều, phí 6 USD / lot, swap −30 USD / lot / đêm (× 3 thứ Tư).
- Không có stress 2010–2018, vì trước 03/2018 không có nến trong ngày thật. Ghi rõ giới hạn này.

## Luật (cố định)

**Chiều:** chế độ D1 (R1, của ngày đã đóng) = +1 thì chỉ mua, −1 thì chỉ bán, 0 thì không đặt lệnh.

**Mức** (mô tả chiều bán, chiều mua đối xứng):
- swing H1 pivot 3 / 3 đã xác nhận, trong 240 nến H1 gần nhất (~10 ngày giao dịch);
- ATR = ATR14 H1 tại lúc đặt lệnh.

**Hai biến thể (cùng họ, chọn một ở kỳ chọn):**
- **F — S/R flip** (mức vừa bị phá):
  - một **đáy swing** L bị phá: nến H1 đóng dưới L − 0,3 ATR;
  - ở giá đóng của nến phá đó, đặt **sell limit tại L − 0,2 ATR** (mép dưới của vùng ± 0,2 ATR quanh L);
  - giá đóng phải cách mức đặt ≥ 0,5 ATR. Đây là lệnh phục kích, không đuổi giá.
- **R — kháng cự chưa phá:**
  - **đỉnh swing** H gần nhất nằm trên giá ≥ 0,5 ATR và ≤ 3 ATR;
  - đặt sell limit tại **H − 0,2 ATR** khi một nến H1 đóng, nếu chưa có lệnh chờ ở mức đó.

**Quản lý lệnh chờ:**
- hết hạn sau **24 giờ**;
- mỗi mức chỉ đặt một lần;
- tối đa **1 lệnh chờ và 1 lệnh mở mỗi chiều**;
- lệnh chờ bị hủy nếu chế độ D1 đổi.

**Lệnh đã khớp:**
- **SL** = giá khớp + 1,3 ATR (ATR lúc đặt lệnh);
- **chia 3 phần:**
  - TP1 = 1 R;
  - TP2 = 2 R;
  - TP3 = đáy swing H1 gần nhất bên dưới mà xa hơn 2 R; nếu không có thì 3 R;
- chạm TP1 thì dời SL phần còn lại về hòa vốn;
- hết giờ sau 72 giờ thì đóng phần còn lại ở giá đóng.

## Đối chứng

- **C1 — mức giả:**
  - cùng thời điểm và cùng khoảng cách tới giá như mức thật, nhưng dời ngẫu nhiên ± 0,5–1,5 ATR;
  - không được trùng swing H1 nào trong ± 0,3 ATR;
  - cùng mọi luật khác; chạy 200 lần.
  - Câu hỏi: **mức S/R thật có giá trị không.**
- **C2 — vào thị trường:** cùng thời điểm đặt lệnh và cùng chiều, nhưng vào ngay ở giá đóng, cùng SL / TP. Câu hỏi: **đặt chờ ở mức có hơn vào ngay không.**
- **C3 — bỏ cổng D1:** cả hai chiều. Chỉ báo cáo.

## Chọn và đạt

**Chọn:** biến thể có MAR (R / DD R) kỳ chọn cao hơn trong {F, R}. Chỉ biến thể đó được xét; biến thể kia chỉ báo cáo. α = 0,05 / 2.

**Đạt khi biến thể được chọn thỏa cả 8:**

1. Kỳ kiểm: tổng R > 0, PF ≥ 1,2, ≥ 50 lệnh khớp.
2. R TB > 0 ở cả kỳ chọn và kỳ kiểm. Bootstrap khối tuần trên cả kỳ: CI (α / 2 mỗi phía) có cận dưới > 0.
3. Tổng R cả kỳ > p95 của C1 (mức giả).
4. R TB cả kỳ > R TB của C2 (vào thị trường).
5. Lệnh mua và lệnh bán đều có R TB ≥ −0,05 (bỏ qua chiều có < 15 lệnh).
6. Chi phí × 1,5 (cả swap): tổng R cả kỳ > 0.
7. **Láng giềng:** ≥ 4 / 6 có tổng R kỳ kiểm > 0. Sáu láng giềng:
   - SL 1,0 hoặc 1,6 ATR;
   - mức đặt ± 0,1 hoặc ± 0,3 ATR;
   - hết hạn 12 hoặc 48 giờ.
8. DD R cả kỳ ≤ 15 R (≈ 15 % vốn ở rủi ro 1 % / lệnh).

**Báo cáo thêm:**
- số lệnh / tuần, tỷ lệ khớp, thời gian chờ khớp, thời gian giữ;
- R theo năm, theo giờ đặt lệnh (giờ VN);
- độ nhạy M5 (05/2024 →);
- các lệnh rule đặt quanh **8 setup LFX** 04–17/11 (rule có "thấy" cùng vùng không).

**Nếu đạt:** viết kế hoạch đưa vào EA ở chế độ **SHADOW** (lệnh chờ ảo, chỉ ghi nhật ký). Không LIVE khi chưa có forward.

## Tệp

- Script `research/long/g168_sr_flip.py`, kết quả `results/g168/`.
- **Kiểm code trước:** tính tay một lệnh mẫu (đặt, khớp, SL / TP) trên nến M30 và khớp với engine.

Không chỉnh luật sau khi chạy. Sổ cái: 2 phép thử.
