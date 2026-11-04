# G163: vào lệnh theo vùng, trigger dễ thở + bồi thuận trend khi đang lời — báo cáo (04/11/2026)

[Kế hoạch](../plans/2026-11-04-g163-loose-zone-pyramid.md)
- Nhánh a: script `research/long/g163a_zone_pyramid.py`, kết quả `results/g163a/`.
- Nhánh b: script `research/long/g163b_s07_pyramid.py`, kết quả `results/g163b/`.

## Kết luận

**KHÔNG ĐẠT ở cả hai nhánh.** Nhưng có một phát hiện có ích.

- **G163a:** entry vùng dễ thở (Z1 vùng EMA) cho được **~3 lệnh / tuần**, PF 1,29, +289 R cả kỳ ở rủi ro 0,5 %. Nhưng nó trượt 5 / 9 tiêu chí:
  - **không hơn entry ngẫu nhiên cùng chiều D1;**
  - lệnh bán âm;
  - DD 22,6 %;
  - stress 2010–2018 âm;
  - láng giềng 0 / 4.

  Lợi nhuận là trôi theo trend tăng của vàng, không phải nhờ vùng.
- **Phát hiện:** **bồi theo nấc +1R (P1) có ích thật.**
  - Trên Z1, chênh do bồi +157 R, CI 95 % [+20; +319].
  - P1 cũng nâng Z2 và Z3.
  - Ngược lại, **bồi ở pullback có xác nhận (P2) gần như không thêm gì**: +0,3 R trên Z1.
- **G163b:**
  - thay ADD của S07 bằng P2: **−86 R**;
  - thêm P2 bên cạnh ADD: +16 R, nhưng CI chứa 0 và không hơn bồi ngẫu nhiên.

  ADD hiện có của S07, vốn là bồi khi đã lời, đã làm tốt phần việc này.

## G163a — 9 tổ hợp

Rủi ro 0,5 % / lệnh gốc. Mỗi ô là tổng R / MAR / PF.

| Tổ hợp | Lệnh / tuần | Kỳ chọn 2018–22 | Kỳ kiểm 2023–26 | R từ lệnh bồi (cả kỳ) | Mua / bán R |
|---|---|---|---|---|---|
| Z1+P0 | 2,9 | +29 / 0,57 / 1,07 | +103 / 3,74 / 1,32 | — | +195 / −63 |
| **Z1+P1** | 2,9 | **+108 / 2,75 / 1,19** | **+181 / 4,58 / 1,41** | **+157** | +364 / −75 |
| Z1+P2 | 2,9 | +12 / 0,23 / 1,03 | +121 / 3,53 / 1,35 | +0,3 | +227 / −95 |
| Z2+P0 | 4,0 | −145 / −0,87 / 0,77 | −44 / −0,53 / 0,91 | — | −10 / −179 |
| Z2+P1 | 4,0 | −110 / −0,77 / 0,85 | −14 / −0,14 / 0,98 | +65 | +88 / −212 |
| Z2+P2 | 4,0 | −150 / −0,92 / 0,78 | −54 / −0,55 / 0,89 | −15 | −12 / −192 |
| Z3+P0 | 1,6 | −17 / −0,38 / 0,93 | +73 / 4,05 / 1,47 | — | +108 / −52 |
| Z3+P1 | 1,6 | −5 / −0,09 / 0,98 | +142 / 5,78 / 1,70 | +82 | +218 / −80 |
| Z3+P2 | 1,6 | −29 / −0,54 / 0,89 | +116 / 5,58 / 1,70 | +32 | +135 / −48 |

**Đọc bảng:**
- **Z2** (vùng thanh khoản: đáy ngày trước, phiên Á, swing) **âm ở mọi biến thể**. Vào lệnh ở mức thanh khoản theo chiều D1 là sai.
- **Lệnh bán âm ở mọi tổ hợp.** Mọi phần lời đến từ lệnh mua trong thời kỳ vàng tăng.

### Tổ hợp được chọn Z1+P1

Cả kỳ: 1.303 lệnh, tỷ lệ thắng 20,5 %, R TB +0,22, PF 1,29, +289 R (lệnh gốc +132, lệnh bồi +157), DD 45 R = 22,6 % vốn.

| # | Tiêu chí | Kết quả | |
|---|---|---|---|
| 1 | Kỳ kiểm R > 0, PF ≥ 1,2 | +181 R, PF 1,41 | đạt |
| 2 | ≥ 2 lệnh / tuần ở hai kỳ | 2,9 / 3,0 | đạt |
| 3 | DD ≤ 15 %, P(DD 12 tháng ≥ 15 %) ≤ 5 % | 22,6 %; **58,7 %** | trượt |
| 4 | Hơn p95 Z-rand (entry ngẫu nhiên cùng chiều D1, cùng P1) | +289 so với p95 **+333** (p50 +103) | trượt |
| 5 | Bồi có ích | CI [+20; +319] | đạt |
| 6 | Mua và bán ≥ 0 | bán **−75** | trượt |
| 7 | Chi phí × 1,5, swap −60 | +158 R | đạt |
| 8 | Láng giềng ≥ 2 / 3 | **0 / 4** (đệm SL 0,2 / 0,5, bồi ở +0,75 / +1,5 R) | trượt |
| 9 | Stress D1 2010–2018 | −2,7 R, DD 15,7 % | trượt |

**Ý nghĩa:**
- Lợi nhuận của Z1 nằm trong phân phối của **vào ngẫu nhiên theo D1 + P1**. Phần "có ích" là **chiều D1 và bồi P1**, không phải vùng EMA.
- Ở rủi ro 0,5 %, cứ 10 năm thì khoảng 6 năm có DD ≥ 15 %. Quá cao cho một setup "thoáng".

## G163b — bồi P2 trên S07

| Biến thể | Tổng R cả kỳ | Chênh so với B0 | CI 97,5 % | Kỳ chọn | Kỳ kiểm | DD R | Bồi ngẫu nhiên p50 / p95 | Mua / bán |
|---|---|---|---|---|---|---|---|---|
| **B0** S07 (gồm ADD) | **316,2** | — | — | 76,1 | 240,1 | 17,9 | — | — |
| B-P2: thay ADD bằng P2 | 230,0 | **−86,2** | [−197; +33] | 57,8 | 172,2 | 16,0 | 223 / 261 | −86 / −0,1 |
| B-P2+: giữ ADD + thêm P2 | 332,3 | +16,0 | [−25; +76] | 79,7 | 252,6 | 18,9 | 317 / 350 | +15 / +0,9 |

- Có 125 lần bồi P2 khi thay ADD, và 61 lần khi thêm cạnh ADD.
- **B-P2+** hơn B0 ở cả hai kỳ và cả hai chiều. Nhưng CI chứa 0, và kết quả nằm ngay quanh trung vị của bồi ngẫu nhiên (+317). Nến xác nhận
  không cho giá trị riêng. Trượt tiêu chí 1 và 4.

## Hệ quả

1. **Bồi khi đang lời theo nấc +1R** là thành phần duy nhất có ích trong toàn bộ G158–G163. Bồi theo nến xác nhận thì không có ích.
   - S07 đã có ADD kiểu này, nên **không đổi gì trên S07**.
   - Nếu sau này dựng một setup mới, nên lắp sẵn module bồi +1R.
2. **Entry vùng dễ thở chưa có lợi thế** so với vào ngẫu nhiên cùng chiều D1. Muốn một setup thoáng thật sự, phần cần đo kỹ là **chế độ D1 + quản lý
   (BE, trail, bồi +1R)**, chứ không phải chọn vùng.
   - Khó ở đây: lệnh bán âm và stress 2010–2018 âm.
   - Ngay cả bản thuần D1 + P1 cũng phải qua được hai điểm này mới dùng được.
3. **Ghi vào sổ cái:** 9 + 2 phép thử; 0 đạt.
