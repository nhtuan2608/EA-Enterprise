# G82: Rủi ro theo nhãn "dải EMA xếp thứ tự" cho lệnh mua S07 — kết quả

Kế hoạch: `plans/2026-10-10-g82-ribbon-label-risk.md`. Sổ mua S07 (gốc M30 + bồi S07A, tối đa 3 lệnh mở), XAUUSD, chi phí khắt khe G68. Nhãn: EMA21 > EMA55 > EMA100 và giá > EMA21 ở nến tín hiệu M30.

## Phần 1 — nhãn trên tập con lệnh gốc

| Kỳ | Có nhãn: n / R | Không nhãn: n / R |
|---|---|---|
| 09/2018–07/2021 | 122 / +0.261 | 74 / -0.010 |
| Train 2021–2023 | 78 / +0.434 | 58 / +0.092 |
| Validate 2024–06/2025 | 72 / +0.574 | 58 / +0.547 |
| Test 07/2025–06/2026 | 47 / +0.922 | 19 / +0.463 |

Gộp 2018–06/2026: có nhãn 319 lệnh / +0.471R, không nhãn 209 / +0.216R; tốt hơn ở 4/4 kỳ; hoán vị p = 0.102. Cả cụm (gốc + bồi): có nhãn +0.65R/cụm, không nhãn +0.52.

**Phần 1: nhãn KHÔNG đạt.**

## Phần 2 — mức rủi ro

### Sổ đầy đủ (gốc + bồi)

| Mức | Giai đoạn | %/năm | DD lớn nhất | DD p90 1 năm | Chạm 20% | Chạm 30% | 1 năm xấu (p10) | %/năm ÷ DD p90 |
|---|---|---|---|---|---|---|---|---|
| K0 1.50% / 1.50% | 09/2018–06/2026 | +75% | 43% | 30% | 29% | 12% | -5% | 2.47 |
| K0 1.50% / 1.50% | 07/2021–06/2026 | +115% | 23% | 18% | 3% | 0% | +6% | 6.31 |
| K1 1.50% / 1.00% | 09/2018–06/2026 | +70% | 39% | 27% | 29% | 8% | -5% | 2.59 |
| K1 1.50% / 1.00% | 07/2021–06/2026 | +106% | 23% | 18% | 3% | 0% | +5% | 5.99 |
| K3 1.50% / 0.75% | 09/2018–06/2026 | +68% | 38% | 27% | 28% | 8% | -4% | 2.55 |
| K3 1.50% / 0.75% | 07/2021–06/2026 | +102% | 23% | 18% | 3% | 0% | +5% | 5.60 |
| K2 2.00% / 1.50% | 09/2018–06/2026 | +89% | 45% | 30% | 31% | 13% | -2% | 2.91 |
| K2 2.00% / 1.50% | 07/2021–06/2026 | +138% | 26% | 19% | 5% | 0% | +11% | 7.29 |

### Chỉ lệnh gốc

| Mức | Giai đoạn | %/năm | DD lớn nhất | DD p90 1 năm | Chạm 20% | Chạm 30% | 1 năm xấu (p10) | %/năm ÷ DD p90 |
|---|---|---|---|---|---|---|---|---|
| K0 1.50% / 1.50% | 09/2018–06/2026 | +41% | 23% | 16% | 1% | 0% | +6% | 2.57 |
| K0 1.50% / 1.50% | 07/2021–06/2026 | +60% | 11% | 11% | 0% | 0% | +26% | 5.46 |
| K1 1.50% / 1.00% | 09/2018–06/2026 | +38% | 21% | 13% | 1% | 0% | +6% | 2.87 |
| K1 1.50% / 1.00% | 07/2021–06/2026 | +54% | 10% | 10% | 0% | 0% | +23% | 5.35 |
| K3 1.50% / 0.75% | 09/2018–06/2026 | +36% | 20% | 13% | 0% | 0% | +4% | 2.90 |
| K3 1.50% / 0.75% | 07/2021–06/2026 | +50% | 10% | 10% | 0% | 0% | +21% | 5.28 |
| K2 2.00% / 1.50% | 09/2018–06/2026 | +53% | 27% | 18% | 2% | 0% | +8% | 2.95 |
| K2 2.00% / 1.50% | 07/2021–06/2026 | +77% | 13% | 13% | 0% | 0% | +31% | 5.71 |


**Kết luận theo luật: giữ K0 (1,5% mọi lệnh).**

## Kết luận

- **Theo tiêu chí: giữ 1,5% cho mọi lệnh (K0).**
- **Phần 1 trượt vì điều kiện thống kê, không phải vì chiều:**
  - Lệnh có nhãn tốt hơn ở **cả 4 kỳ**: gộp +0,47 so với +0,22 R/lệnh. Chênh lớn nhất ở 2018–2021 (+0,26 so với −0,01) và train (+0,43 so với +0,09); ở validate gần như bằng nhau.
  - Nhưng 60% số lệnh có nhãn, nên một tập con ngẫu nhiên cùng cỡ cũng gần bằng trung bình chung → hoán vị p = 0,10, chưa đạt ngưỡng 0,05.
  - Nhãn có xu hướng thật, nhưng chưa đủ chắc để đổi rủi ro.
- **Phần 2 (tham khảo, vì Phần 1 không đạt):**
  - Giảm rủi ro lệnh không nhãn (K1 1,0%, K3 0,75%) làm 2018–2026 an toàn hơn: chạm 30% từ 12% xuống 8%, DD p90 30% xuống 27%. Nhưng ở 07/2021–06/2026 tỉ số lãi/rủi ro giảm (6,3 → 6,0 / 5,6), vì giai đoạn đó lệnh không nhãn cũng tốt.
  - Tăng rủi ro lệnh có nhãn (K2 2,0%) cho tỉ số tốt nhất ở cả hai giai đoạn, nhưng phải nâng trần 1,5% của EA và chạm 30% tăng lên 13%.
- **Rủi ro lớn nhất của sổ vẫn là bồi lệnh, không phải nhãn.** Chỉ lệnh gốc: DD p90 16% (2018–2026), chưa bao giờ chạm 30%. Có bồi (S07A): DD p90 30%, chạm 30% 12%. Nếu muốn an toàn hơn trong giới hạn lỗ tổng 30%, đòn bẩy hiệu quả nhất là giảm rủi ro **lệnh bồi** (ví dụ 1,0%), không phải nhãn.
