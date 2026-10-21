# G139 — setup "hybrid" 5 lớp theo bản tư vấn, các lớp làm trọng số S07, và squeeze breakout (22/10/2026)

Kế hoạch đăng ký trước: [2026-10-22-g139-hybrid-setups.md](../plans/2026-10-22-g139-hybrid-setups.md) (commit `4be8520`, trước khi chạy).

Script:
- [`g139_hybrid.py`](../../research/long/g139_hybrid.py) (phần A, C), seed 139;
- [`g139_s07_weight.py`](../../research/long/g139_s07_weight.py) (phần B).

Engine, chi phí và đối chứng như G137. Dữ liệu PC XAUUSD-VIP. Kỳ: sớm 01/2018–06/2021 (chỉ báo cáo), train 07/2021–2023,
validate 2024–06/2025, test 07/2025–06/2026, sau 07/2026 chỉ xem.

Ghi chú chạy lại: lần chạy đầu của `g139_hybrid.py` hỏng ở bước cuối (tính tỷ lệ trùng S07), do đường dẫn `data` tương đối. Đã
sửa bằng `Path(...).resolve()` và chạy lại toàn bộ. Luật không đổi, seed cố định, các số M30 giống hệt lần đầu.

## Phần A — 4 setup và thang điểm của bản tư vấn, đúng như viết

Ô: số lệnh / R trung bình / tổng R (phí harsh). p = đối chứng ngẫu nhiên, train + validate. Ngưỡng p ≤ 0,003; ≥ 40 lệnh mỗi kỳ
(M30), ≥ 30 (H1).

| Ô | Sớm | Train | Validate | Test | Sau 07/2026 | p | Kết luận theo luật |
|---|---|---|---|---|---|---|---|
| A1 trend pullback M30 | 128 / −0,367 | 97 / +0,071 | 36 / +0,069 | 23 / +0,003 | 9 / −0,693 | 0,050 | **KHÔNG ĐẠT** |
| A1 trend pullback H1 | 60 / −0,120 | 39 / −0,048 | 22 / +0,318 | 14 / −0,016 | 5 / +0,783 | 0,19 | **KHÔNG ĐẠT** |
| A2 Wyckoff spring → phá vùng M30 | 30 / −0,086 | 35 / −0,069 | 21 / −0,005 | 3 / +0,577 | — | 0,47 | **KHÔNG ĐẠT** |
| A2 Wyckoff spring → phá vùng H1 | 17 / −0,202 | 15 / +0,396 | 4 / +0,482 | 3 / +0,702 | — | 0,090 | **KHÔNG ĐẠT** |
| A3 morning/evening star ở S/R M30 | 113 / +0,121 | 100 / −0,161 | 48 / −0,366 | 44 / +0,229 | 12 / −0,546 | 0,68 | **KHÔNG ĐẠT** |
| A3 morning/evening star ở S/R H1 | 46 / −0,097 | 35 / −0,080 | 24 / −0,049 | 19 / −0,196 | 9 / −0,681 | 0,45 | **KHÔNG ĐẠT** |
| A4a wedge + phân kỳ RSI M30 | 83 / −0,138 | 83 / −0,373 | 33 / −0,031 | 22 / +0,140 | 4 / −1,022 | 0,93 | **KHÔNG ĐẠT** |
| A4a wedge + phân kỳ RSI H1 | 36 / −0,298 | 25 / −0,366 | 17 / −0,291 | 6 / +0,040 | 4 / −0,157 | 0,89 | **KHÔNG ĐẠT** |
| A4b kênh + xu hướng + volume M30 | 123 / +0,056 | 93 / −0,211 | 54 / +0,210 | 40 / −0,081 | 8 / −0,273 | 0,26 | **KHÔNG ĐẠT** |
| A4b kênh + xu hướng + volume H1 | 71 / −0,130 | 61 / −0,467 | 31 / −0,271 | 26 / −0,177 | 4 / +0,482 | 0,99 | **KHÔNG ĐẠT** |
| A5 điểm ≥ 70 M30 | 2.049 / −0,255 | 1.743 / **−0,195** | 1.028 / −0,161 | 651 / −0,009 | 191 / −0,208 | 0,57 | **KHÔNG ĐẠT** |
| A5 điểm ≥ 70 H1 | 1.059 / −0,193 | 768 / **−0,171** | 488 / −0,044 | 321 / +0,033 | 100 / +0,035 | 0,67 | **KHÔNG ĐẠT** |

Chi phí × 1,5 (train / validate / test) chỉ làm các ô kém thêm 0,01–0,05R; không ô nào đổi kết luận. Chi tiết trong
`results/g139/hybrid.json`.

Nhóm điểm 50–69 (báo cáo, theo bản tư vấn là "medium"): M30 −0,265 / −0,114 / +0,040; H1 −0,187 / −0,060 / +0,080. Nhóm này
cũng âm ở train và validate.

**Nhận xét**
- **Thang điểm cộng tay (A5) là phần kém nhất.** Mỗi năm có hàng trăm lệnh ≥ 70 điểm, âm khoảng −0,2R ở train. Lý do: các lớp
  (EMA xếp thứ tự, ADX ≥ 25, volume > trung bình, mẫu nến) bật cùng nhau **sau** một nhịp đã chạy xa. Điểm cao đo "đã chạy",
  không đo "sắp chạy".
- **A1 (pullback đủ 5 lớp)** dương rất nhẹ ở cả ba kỳ M30 (+0,07 / +0,07 / +0,00), p 0,05, nhưng sau chi phí × 1,5 test âm và
  kỳ sớm −0,37R. Phần dương nằm ở **lệnh mua** (M30 train +0,32; H1 +0,37 / +0,24 / +0,12), còn lệnh bán âm. Đây là xu hướng tăng
  của vàng, cùng hiện tượng ở S07. Tách riêng chiều mua là chọn sau khi nhìn và trái quy tắc giữ cả hai chiều, nên **không** dùng.
- **A2 Wyckoff đứng riêng** rất hiếm (3–35 lệnh mỗi kỳ). H1 dương ở 3 kỳ nhưng chỉ 15 / 4 / 3 lệnh; M30 âm.
- **A3, A4a, A4b**: mẫu nến, wedge, kênh dù đã thêm bối cảnh, volume và RSI vẫn âm hoặc đổi dấu theo kỳ. Kết quả giống G56, G86,
  G136 P3, G137.

## Phần B — các lớp xác nhận làm trọng số rủi ro cho S07 M30

Sổ S07 M30 (G89, cả hai chiều), 730 chân gốc. Ngưỡng = trung vị điểm (tối đa 70) của chân gốc trong train = **40**.

| Kỳ | Điểm cao (≥ 40): chân / R | Điểm thấp: chân / R |
|---|---|---|
| Train | 119 / +0,352 | 63 / +0,344 |
| Validate | 99 / +0,501 | 81 / +0,418 |
| Test | 50 / +1,026 | 48 / +0,076 |

Chênh lệch R ở train + validate +0,03, p hoán vị **0,45**.

Danh mục (vốn 10.000, lãi kép). Ô: %/năm / DD / **MAR**:

| Sổ | Train | Validate | Test | DD p90 1 năm |
|---|---|---|---|---|
| Mốc: EA hiện tại (D1 × 0,5) | +26,8% / 14,0% / **1,92** | +237,6% / 17,0% / **13,97** | +203,4% / 12,9% / **15,74** | 17,0% |
| Điểm thấp × 0,5 | +26,3% / 12,4% / **2,13** | +191,6% / 14,3% / **13,40** | +189,8% / 11,3% / **16,85** | 14,3% |

| Tiêu chí | Kết quả |
|---|---|
| R điểm cao > điểm thấp ở cả ba kỳ | Có, nhưng train chỉ hơn 0,008R |
| p ≤ 0,01 | **Không (0,45)** |
| MAR ≥ mốc ở cả ba kỳ | **Không** (validate 13,40 < 13,97) |
| DD p90 không cao hơn mốc | Có (14,3% < 17,0%) |

**Kết luận theo luật phần B: KHÔNG ĐẠT.** Ở train, điểm xác nhận không tách được chân tốt và chân xấu. Chênh lệch lớn chỉ có ở
test, một kỳ, 98 chân. DD giảm vì rủi ro tổng giảm, không phải vì chọn đúng chân. Kết quả giống G82 (nhãn ribbon) và G79 (rà bộ
lọc): S07 đã chứa sẵn phần thông tin mà các lớp này mang.

## Phần C — Bollinger squeeze breakout theo D1

| Ô | Sớm | Train | Validate | Test | Sau 07/2026 | p | Kết luận theo luật |
|---|---|---|---|---|---|---|---|
| C squeeze M30 | 199 / −0,138 | 150 / **−0,314** | 124 / +0,158 | 69 / +0,534 | 17 / +0,156 | 0,79 | **KHÔNG ĐẠT** |
| C squeeze H1 | 112 / −0,257 | 82 / **−0,231** | 66 / +0,158 | 46 / +0,459 | 8 / +0,488 | 0,80 | **KHÔNG ĐẠT** |

- 39–41% lệnh trùng một chân S07 M30 cùng chiều đang mở.
- Phần không trùng (M30): −0,39 / +0,46 / +0,25R. Phần không trùng (H1): −0,37 / +0,04 / +0,31R.
- Dương chỉ từ 2024, khi vàng tăng một chiều (validate và test gần như toàn lệnh mua). 2018–2023 âm rõ ở cả hai khung. Đây là lợi
  thế của **thị trường**, không phải của setup: đối chứng ngẫu nhiên cùng chiều cũng ăn được (p 0,8).

## Tổng hợp

| Phần | Ô | Kết luận theo luật |
|---|---|---|
| A1–A5 (4 setup + thang điểm của bản tư vấn) | 10 | KHÔNG ĐẠT cả 10 |
| B (lớp xác nhận làm trọng số S07) | 1 | KHÔNG ĐẠT |
| C (squeeze breakout theo D1) | 2 | KHÔNG ĐẠT |

Không có đề xuất đưa vào EA.

## Ghi chú cho agent khác (nếu muốn sửa hoặc code tiếp)

1. **Đừng code khung "5 lớp + điểm ≥ 70" thành setup vào lệnh.** Trên vàng 2018–2026 nó âm ở train và validate với cả M30 và H1,
   hàng nghìn lệnh. Nếu vẫn muốn hiển thị điểm này trên dashboard, chỉ để **mô tả bối cảnh**, không gắn vào lệnh hay rủi ro.
2. **Không cần thêm lớp xác nhận vào S07.** Ở train, điểm xác nhận không tách được chân tốt và xấu (p 0,45). Trọng số D1 × 0,5
   (G134, đã kiểm lại ở G138) là lớp duy nhất có căn cứ.
3. **Những gì còn đáng làm**, dựa trên toàn bộ G23–G139:
   - **Forward các ứng viên đã có, không dựng setup mới**: nến V M30 (G118 A, dương mọi kỳ trên PC, p 0,015 ở G136 P3) chạy
     SHADOW để có số lệnh forward; VHedge G119 và các bot đang chạy demo.
   - **Quản lý vốn và danh mục** giữa các lợi thế đã chứng minh (S07, VHedge, XRT, CtxLimit). Ví dụ: trần rủi ro mở chung,
     phân bổ theo DD. Các phần này đổi MAR nhiều hơn mọi bộ lọc vào lệnh đã thử.
   - **Đối chiếu live với nghiên cứu** bằng nhật ký bot (`logs/bots-*.jsonl`) khi đủ lệnh, để phát hiện sớm khi lợi thế yếu đi.
4. Nếu muốn mở lại một họ mẫu hình, cần kế hoạch riêng nêu rõ điểm khác với G56, G86, G136, G137, G139, và ghi luật trước khi chạy.
