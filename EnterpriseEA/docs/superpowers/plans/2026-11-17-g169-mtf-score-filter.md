# G169: bộ lọc "Score" đa khung kiểu LFX cho lệnh lướt M5 / M15 — kế hoạch đăng ký trước (17/11/2026)

## Lý do và cách tạo giả thuyết

[G167](../reports/2026-11-17-g167-lfx-signal-forensics.md): bot LFX gắn nhãn DUYỆT / TỪ CHỐI và Score/100. Nhãn tách rất rõ:
- DUYỆT: TP1 trước SL 64 %, +0,78 R (n = 14);
- TỪ CHỐI: 17 %, −0,61 R (n = 23);
- Score ≥ 70: 75 % (n = 8).

**Tạo giả thuyết (17/11, trên 37 kèo có nhãn, 06/2026).** So bối cảnh đa khung của DUYỆT với TỪ CHỐI:

| Đặc điểm (so với chiều lệnh) | DUYỆT | TỪ CHỐI |
|---|---|---|
| EMA50 H1 dốc cùng chiều | 79 % | 17 % |
| Giá cùng phía EMA50 H4 | 71 % | 17 % |
| Giá cùng phía EMA50 H1 | 71 % | 22 % |
| Chế độ D1 cùng chiều | 57 % | 17 % |
| EMA50 H4 dốc cùng chiều | 57 % | 22 % |
| Giá cùng phía EMA50 D1 | 57 % | 22 % |
| Giá cùng phía EMA50 M15 | 50 % | 17 % |
| **RSI H4 ở vùng 60 / 40 ngược chiều** | 7 % | 57 % |
| RSI H1 ở vùng 60 / 40 ngược chiều | 14 % | 48 % |
| RSI M15 ở vùng 60 / 40 ngược chiều | 29 % | 57 % |
| Giá ở 1/3 biên 12 h phía ngược | 29 % | 52 % |

→ **Score của LFX ≈ điểm thuận xu hướng đa khung, trừ điểm khi đang ở vùng cực trị ngược chiều.**

G169 kiểm giả thuyết này trên dữ liệu dài, **không dùng tháng 06/2026**, là tháng sinh ra giả thuyết. Người dùng duyệt 17/11.

## Score (cố định, trọng số bằng nhau)

Tính ở giá đóng của nến tín hiệu, chỉ dùng nến đã đóng của mỗi khung, so với chiều lệnh d.

- **+1 mỗi điều (7 điều):**
  - EMA50 H1 dốc cùng chiều (so với 10 nến trước);
  - giá cùng phía EMA50 trên H1, H4, D1, M15 (4 điều);
  - EMA50 H4 dốc cùng chiều;
  - chế độ D1 (R1) cùng chiều.
- **−1 mỗi điều (4 điều):**
  - RSI14 H4 ngược chiều ở 60 / 40 (≥ 60 khi bán, ≤ 40 khi mua);
  - như trên với RSI14 H1;
  - như trên với RSI14 M15;
  - giá ở 1/3 biên 12 giờ phía ngược (bán ở 1/3 trên, mua ở 1/3 dưới).
- Điểm thô ∈ [−4; 7] → **Score = (thô + 4) / 11 × 100**.
- **Ba nhóm:** < 50, 50–69, **≥ 70**.

## Bộ kích hoạt cơ sở (trung tính, cho cả hai chiều)

Score là bộ lọc, nên cần một nguồn lệnh trung tính. Hai bộ kích hoạt, mỗi bộ cho cả mua và bán:

- **T1 — mỗi giờ:** ở giá đóng của nến M15 kết thúc lúc HH:00, sinh một ứng viên mua và một ứng viên bán. Hai ứng viên tính riêng, mỗi cái có Score riêng.
- **T2 — nến từ chối M15:** nến M15 có râu ngược ≥ 50 % biên, đóng theo chiều lệnh, và chạm cực trị 3 nến trước đó (đáy cho lệnh mua, đỉnh cho lệnh bán).

## Lệnh (hình học của bot LFX)

- **Vào:** giá mở nến M15 kế tiếp.
- **SL:** 1,1 × ATR14 M15 (≈ 1,8 ATR M5 của bot LFX).
- **TP:** 2 phần.
  - TP1 = 1,5 R;
  - TP2 = 2,5 R;
  - chạm TP1 thì dời SL phần còn lại về hòa vốn.
- **Hết giờ:** 24 giờ.
- **Giới hạn:** mỗi chiều tối đa 1 lệnh mở; ứng viên đến khi chiều đó đang có lệnh thì bỏ.
- **Mô phỏng:** trên nến M15, luật bi quan.
- **Chi phí:** spread, trượt giá 0,5 × spread trung vị mỗi chiều, phí 6 USD / lot, swap −30 / lot / đêm.

## Dữ liệu và kỳ

- XAUUSD MT5, M15 thật từ 07/2021 (m15v) và H1 / H4 / D1. Nối dữ liệu terminal đến 17/11/2026.
- **Kỳ chọn:** 07/2021–2023. **Kỳ kiểm:** 2024 → 17/11/2026, **bỏ 01/06–30/06/2026**.
- **Độ nhạy:** chạy lại trên M5 thật (05/2024 →) với SL 1,8 ATR M5.

## Đối chứng

- **C1 — chỉ D1:** cùng bộ kích hoạt, chỉ giữ lệnh cùng chiều chế độ D1. Đây là mốc "thuận xu hướng đơn giản" mà G163 đã thấy khó vượt.
- **C2 — Score đảo:** nhóm < 50. Câu hỏi: lọc ngược có tệ hơn không.
- **C3 — không lọc:** tất cả ứng viên.

## Đạt

Thỏa cả 7 điều, cho ít nhất một bộ kích hoạt. Hai bộ kích hoạt nên α = 0,05 / 2.

1. **Đơn điệu:** tỷ lệ chạm TP1 trước SL tăng dần qua 3 nhóm Score (< 50 < 50–69 < ≥ 70), ở **cả** kỳ chọn và kỳ kiểm.
2. **Nhóm ≥ 70:**
   - R TB > 0 ở cả hai kỳ;
   - bootstrap khối tuần trên cả kỳ: CI cận dưới > 0.
3. **Nhóm ≥ 70 hơn C1 (chỉ D1):** chênh R TB > 0 ở cả hai kỳ.
4. **Nhóm ≥ 70, hai chiều:** mua và bán đều có R TB ≥ −0,05 (bỏ chiều có < 15 lệnh).
5. Chi phí × 1,5: R TB nhóm ≥ 70 > 0.
6. Độ nhạy M5 (05/2024 →): R TB nhóm ≥ 70 > 0.
7. Tần suất nhóm ≥ 70: ≥ 1 lệnh / tuần.

**Báo cáo thêm:**
- tỷ lệ TP1, R TB, PF, DD theo nhóm Score;
- R theo năm;
- phân bố giờ (VN).

**Nếu đạt:** viết kế hoạch đưa vào EA ở chế độ **SHADOW**, gồm bot lướt M15 + Score, ghi nhật ký. Không LIVE.

## Tệp

- Script `research/long/g169_score_filter.py`, kết quả `results/g169/`.
- **Kiểm code trước:** tính tay Score của một ứng viên mẫu từ nến từng khung, và khớp với engine.

Không chỉnh trọng số, ngưỡng hay luật sau khi chạy. Sổ cái: 2 phép thử.
