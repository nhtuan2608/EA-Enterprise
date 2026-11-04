# G160a: sàng manh mối — cổng đi ngang K1–K5 và 15 manh mối chưa test — báo cáo (04/11/2026)

[Kế hoạch](../plans/2026-11-04-g160a-clue-screen.md) · script `research/long/g160a_clue_screen.py` · kết quả `research/long/results/g160a/summary.json`

## Kết luận

**Không có gì qua vòng.** 0 / 5 cổng K đạt, 0 / 15 manh mối đạt.

- **Phần A:** chỉ K2 (efficiency ratio) đạt thước thị trường. Nhưng gắn vào lưới thì không giảm DD, và stress 2010–2018 vẫn cháy.
- **Phần B:** không manh mối nào hơn đối chứng; vì vậy không cần chạy null toàn họ (số đạt thật = 0).

Theo khung G159 / G160: không có cổng nào vượt được stress, nên **hướng bồi lệnh không SL trên vàng đóng ở dạng hiện tại**. G159b, G160b và G160c không còn
nền để chạy.

## Phần A — cổng đi ngang

**(A-i):** Y = giá dịch ròng ≥ 2 ADR20 trong 10 ngày. Chênh = P(Y | bật) − P(Y | tắt); cần âm. CI ở mức α = 0,05 / 5.

| Cổng | Tỷ lệ ngày bật | Chênh | CI | Vượt null dịch | Kỳ âm | (A-i) |
|---|---|---|---|---|---|---|
| K1 ADX < 20 + BB hẹp | 17 % | +0,038 | [−0,054; +0,127] | 18 % | 1/3 | không |
| **K2 ER20 < 0,3** | 66 % | **−0,099** | **[−0,185; −0,013]** | **99,6 %** | **3/3** | **đạt** |
| K3 ≥ 4 lần cắt EMA50 H4 | 58 % | −0,021 | [−0,107; +0,065] | 72 % | 2/3 | không |
| K4 biên 10 ngày < 1,5 ADR | **0,2 %** | — | — | — | 0/0 | không (định nghĩa gần như không bao giờ bật) |
| K5 Hurst < 0,45 | 6 % | +0,045 | [−0,084; +0,185] | 21 % | 1/3 | không |

**K2 trên D1 2010–02/2018** (chỉ báo cáo): P(Y | bật) = 0,347, P(Y | tắt) = 0,360. Gần như không khác nhau. Tác dụng thấy ở 2018–2026 **không có
ở 2010–2018**, đúng giai đoạn làm lưới cháy.

**K4:** biên 10 ngày gần như luôn ≥ 1,5 ADR20, nên cổng bật đúng 2 ngày. Định nghĩa đã đăng ký trước nên không sửa; ghi nhận là định nghĩa hỏng.

**(A-ii):** lưới nền chỉ mở rổ khi cổng bật.
- Nền không cổng: 84 tín hiệu, lãi 29.390, DD 0,528.
- Đối chứng: 50 chuỗi cổng dịch vòng, cùng tỷ lệ bật.

| Cổng | Tín hiệu mở | Lãi cả kỳ | DD | DD trung vị chuỗi dịch | Thắng dịch về DD / ES (/ 50) | Stress có cổng / cùng số entry không cổng | (A-ii) |
|---|---|---|---|---|---|---|---|
| K1 | 17 | 5.430 | 0,296 | 0,293 | 22 / 5 | — | không |
| K2 | 53 | 17.598 | 0,597 | 0,531 | 1 / 19 | **6 / 4** | không |
| K3 | 51 | 19.521 | 0,528 | 0,534 | 27 / 12 | — | không |
| K4 | 0 | 0 | 0 | 0 | 11 / 1 | 0 / 0 | không |
| K5 | 5 | 617 | 0,063 | 0,096 | 32 / 29 | — | không |

Đọc kết quả:
- DD thấp hơn ở K1 / K5 **chỉ vì ít rổ hơn**. Chuỗi dịch cùng tỷ lệ bật cho DD giống hệt.
- K2 còn tệ hơn chuỗi dịch: 1 / 50 về DD.
- Trong stress, có cổng K2 cháy 6 / 20 lần chạy; cùng số entry không cổng cháy 4 / 20.

## Phần B — 15 manh mối chưa test

Nhãn ± 1 ATR H1 trong 4 giờ. CI ở mức α = 0,05 / 15. Cần n ≥ 100, CI > 0 và ≥ 2 / 3 kỳ dương.

| Manh mối | n | P | P đối chứng | Chênh | CI | Kỳ dương |
|---|---|---|---|---|---|---|
| H2 Stochastic 20 / 80 | 2.032 | 0,491 | 0,493 | −0,002 | [−0,035; +0,032] | 2/3 |
| H3 CCI ± 200 | 1.041 | 0,465 | 0,493 | −0,028 | [−0,072; +0,014] | 0/3 |
| H4 Williams %R cùng D1 | 1.588 | 0,509 | 0,512 | −0,004 | [−0,035; +0,033] | 2/3 |
| H5 phân kỳ MACD | 666 | 0,512 | 0,493 | +0,019 | [−0,044; +0,078] | 2/3 |
| I1-2 Elliott sóng 5 (k 2) | 63 | 0,587 | 0,507 | +0,080 | [−0,103; +0,272] | — (n < 100) |
| I1-3 Elliott sóng 5 (k 3) | 27 | 0,444 | 0,507 | −0,063 | rộng | — |
| I2-2 / I2-3 Elliott sau ABC | 7 / 2 | — | — | — | — | — |
| I3-2 / I3-3 harmonic chạm D | 38 / 6 | 0,395 / 0,333 | 0,493 | âm | rộng | — |
| J1 Ichimoku | 183 | 0,514 | 0,507 | +0,007 | [−0,100; +0,128] | 2/3 |
| J5 Heikin Ashi | 724 | 0,482 | 0,493 | −0,011 | [−0,072; +0,046] | 2/3 |
| J7 SAR cùng D1 | 318 | 0,538 | 0,512 | +0,025 | [−0,051; +0,100] | 1/3 |
| J4 pivot ngày: chỗ dừng | 14.225 lần chạm | 0,378 | 0,388 (mức giả) | −0,010 | [−0,030; +0,011] | 0/3 |

Đọc kết quả:
- Các dao động (Stochastic, CCI, %R, MACD, Heikin Ashi) và SAR / Ichimoku đều ở mức **ngang ngẫu nhiên**, như RSI ở G130 / G131.
- **Mô hình sóng (Elliott, harmonic)** quá hiếm khi được định nghĩa bằng luật không nhìn trước: chỉ 2–63 lần trong 8 năm. Không đủ để kết luận, và
  cũng không đủ để làm entry cho một hệ thống.
- **Pivot ngày không phải chỗ dừng:** giá đảo ở mức pivot thật hơi *ít* hơn ở mức giả giữa hai pivot.

## Hệ quả

1. **Hướng bồi lệnh / hedge không SL trên vàng (G158 → G160a) đóng.**
   - Lý do: không entry, module cơ chế hay cổng thị trường nào qua được stress 2010–2018.
   - Ở cả ba vòng, nguyên nhân cháy là một xu hướng giảm dài. Mọi quy tắc đo được đều chỉ đổi cách thua, không tránh được nó.
2. **Còn lại để dùng:**
   - P1 (cắt cặp liên tục, G159a) là ý tưởng giảm tải có ích, nếu sau này có cơ chế nhiều lệnh *có* giới hạn lỗ;
   - K2 có thể là nhãn theo dõi trong hội đồng (chỉ ghi log), không dùng làm cổng giao dịch.
3. **Ghi vào sổ cái:** 5 + 15 = 20 phép thử, 0 đạt.
