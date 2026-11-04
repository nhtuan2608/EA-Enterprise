# G165: bot hedge liên thị trường XAU / XAG — báo cáo thăm dò (04/11/2026)

[Kế hoạch](../plans/2026-11-04-g165-xau-xag-pair-hedge.md) (có sửa đổi trước khi chạy).
- Script `research/long/g165_xau_xag_pair.py`, kiểm dữ liệu `research/long/ingest_merge.py`.
- Kết quả `research/long/results/g165/` (`summary.json`, `ingest_validation.json`).

## Kết luận

**KHÔNG đáng lấy thêm dữ liệu dài.** Cấu hình được chọn đạt 2 / 6 điều kiện; **cả 8 cấu hình đều âm ở kỳ chọn 2016–2021**.

Lý do gốc nằm ở chênh lệch vàng / bạc: nó **hồi quy quá chậm** so với khung giữ lệnh của một bot.
- Half-life là **68–101 ngày**, trong khi z-score tính trên 10–20 ngày và giữ tối đa 10 ngày.
- Khi chênh lệch lệch xa 2 ĐLC theo cửa sổ 10–20 ngày, nó thường **tiếp tục trôi**, không quay về.
- Đánh ngược lại (theo đà) cũng thua (−20,6 R). Như vậy không có hướng nào kiếm được tiền sau chi phí.

Bot **trung tính với vàng thật** (ρ = −0,12), đúng như mục tiêu hedge, nhưng không có lợi nhuận.

## Dữ liệu (đã kiểm trước khi chạy)

| Chuỗi | Nguồn | Khớp với MT5 |
|---|---|---|
| XAU 2010–2025 (ingest) | giống MT5 raw | chênh giá đóng TB 0,014 %, tương quan lợi suất ngày 0,997 |
| XAG 06/2016 → 06/2026 (ingest) | **không phải spot MT5**: khớp nhất với giá MT5 lúc ~18:00 UTC, lệch trung vị 0,25 % (nhiều khả năng là giá settlement hợp đồng tương lai) | tương quan lợi suất ngày với D1 MT5 chỉ 0,87, do khác giờ chốt |

**Dữ liệu dùng để chạy:** 2.603 ngày, lấy mẫu lúc 18:00 UTC.
- XAU: MT5 H1 từ 19/03/2018; trước đó là D1 MT5, lệch giờ 3–4 tiếng (431 ngày).
- XAG: ingest đến 25/06/2026, sau đó MT5.
- Chi phí: spread và **swap thật** hiện tại của broker.

## 8 cấu hình

| Cấu hình | Kỳ chọn 2016–21: n / R / PF | Kỳ kiểm 2022–26: n / R / PF | Mua / bán chênh lệch R (cả kỳ) |
|---|---|---|---|
| M1 N10 k2,0 | 81 / −50,6 / 0,36 | 63 / +10,4 / 1,50 | −19,2 / −21,0 |
| **M1 N10 k2,5** (chọn) | 22 / −2,3 / 0,82 | 18 / −0,2 / 0,97 | −0,5 / −2,0 |
| M1 N20 k2,0 | 64 / −35,3 / 0,28 | 52 / +2,2 / 1,09 | −4,8 / −28,3 |
| M1 N20 k2,5 | 33 / −12,7 / 0,46 | 24 / +6,2 / 2,03 | −0,4 / −6,1 |
| M2 N10 k2,0 | 72 / −43,2 / 0,35 | 66 / −23,0 / 0,56 | −19,7 / −46,5 |
| M2 N10 k2,5 | 23 / −13,7 / 0,39 | 9 / −2,4 / 0,48 | −10,5 / −5,7 |
| M2 N20 k2,0 | 64 / −26,7 / 0,44 | 56 / −27,7 / 0,45 | −22,8 / −31,6 |
| M2 N20 k2,5 | 27 / −12,2 / 0,49 | 28 / −12,1 / 0,37 | −5,6 / −18,7 |

β hồi quy trượt (M2) còn tệ hơn tỷ lệ thuần (M1).

### Cấu hình được chọn: M1 N10 k2,5

Chọn theo MAR kỳ chọn ít âm nhất trong các cấu hình có ≥ 15 rổ.

| # | Điều kiện | Kết quả | |
|---|---|---|---|
| 1 | Kỳ kiểm R > 0, PF ≥ 1,2, ≥ 15 rổ | −0,2 R, PF 0,97, 18 rổ | trượt |
| 2 | Mua và bán chênh lệch ≥ 0 | −0,5 / −2,0 | trượt |
| 3 | Hơn p90 ngẫu nhiên | −2,5 so với p90 −0,4 (p50 −11,5) | trượt |
| 4 | Hơn bản đánh theo đà | −2,5 so với −20,6 | đạt |
| 5 | \|ρ\| với vàng < 0,3 | −0,12 | đạt |
| 6 | Chi phí × 1,5 vẫn R > 0 | −10,0 | trượt |

Cả kỳ: 40 rổ, tỷ lệ thắng 52,5 %, R TB −0,06, chi phí TB 0,29 R / rổ (≈ 50 % lãi gộp dương).

**Độ nhạy (không phải tiêu chí):**

| Đoạn | Rổ | Tổng R | PF |
|---|---|---|---|
| Trước 19/03/2018 (lệch giờ) | 4 | −3,2 | — |
| Từ 19/03/2018 (cùng giờ) | 36 | +0,7 | 1,05 |
| 02/2024–11/2026, **cả hai chân MT5 spot** | 9 | −3,7 | 0,47 |
| Cùng đoạn, dữ liệu gộp | 10 | −1,5 | 0,75 |

Nguồn XAG khác không phải lý do thất bại: dùng hai chân MT5 spot còn tệ hơn.

## Hệ quả

1. **Bot hedge XAU / XAG kiểu hồi quy z-score ngắn hạn: đóng.**
   - Chênh lệch có trung tính nhưng hồi quy theo tháng, không theo tuần.
   - Nếu làm theo nhịp half-life (cửa sổ 60–120 ngày, giữ hàng tháng), mỗi năm chỉ được vài rổ, và swap hai chân sẽ ăn phần lớn lợi nhuận. Muốn thử
     bản đó thì cần kế hoạch mới, kèm dữ liệu dài từ 2010.
2. **Gộp dữ liệu ingest:** XAU khớp MT5 nên dùng được. XAG là nguồn khác (giá ~18:00 UTC), chỉ nên dùng cho nghiên cứu D1, có ghi chú.
3. **Ghi vào sổ cái:** 8 cấu hình thăm dò, 0 đạt.
