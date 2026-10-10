# G91: Phối hợp setup thành sổ FX — chọn trên 2010–2020, kiểm tra trên 2021–2025

Kế hoạch: `plans/2026-10-11-g91-fx-portfolio.md`. Số liệu G55 (`scorecard.py`): chi phí thường, quản lý lệnh như EA. Ô: số lệnh / R mỗi lệnh.

| Setup | Cặp | Train 2010–16 | Validate 2017–20 | Chọn? | Test 2021–25 |
|---|---|---|---|---|---|
| S02 | EURUSD | 52 / +0.035 | 29 / -0.423 |  | 31 / +0.011 |
| S02 | GBPUSD | 42 / -0.215 | 23 / -0.375 |  | 40 / -0.245 |
| S02 | USDJPY | 36 / -0.228 | 24 / -0.250 |  | 29 / -0.233 |
| S04 | EURUSD | 16 / -0.120 | 9 / -0.110 |  | 16 / +0.092 |
| S04 | GBPUSD | 14 / +0.461 | 11 / +0.073 | **chọn** | 12 / +0.254 |
| S04 | USDJPY | 16 / +0.076 | 8 / +0.426 | **chọn** | 12 / +0.082 |
| S06 | EURUSD | 274 / -0.044 | 149 / +0.015 |  | 144 / +0.036 |
| S06 | GBPUSD | 234 / -0.004 | 156 / -0.022 |  | 167 / -0.069 |
| S06 | USDJPY | 325 / -0.092 | 153 / -0.052 |  | 186 / +0.066 |
| S06B | EURUSD | 26 / +0.576 | 8 / +0.357 | **chọn** | 14 / -0.006 |
| S06B | GBPUSD | 21 / +0.600 | 7 / +0.659 | **chọn** | 11 / -0.034 |
| S06B | USDJPY | 22 / -0.508 | 18 / +0.288 |  | 10 / +0.234 |
| S06B_USD | EURUSD | 21 / +0.509 | 8 / +0.357 | **chọn** | 13 / +0.072 |
| S06B_USD | GBPUSD | 17 / +0.754 | 7 / +0.659 | **chọn** | 10 / -0.039 |
| S06B_USD | USDJPY | 17 / -0.355 | 13 / +0.171 |  | 9 / +0.375 |
| T2 | EURUSD | 99 / +0.001 | 56 / +0.210 | **chọn** | 75 / -0.188 |
| T2 | GBPUSD | 94 / +0.214 | 60 / +0.025 | **chọn** | 70 / +0.050 |
| T2 | USDJPY | 86 / +0.441 | 64 / -0.227 |  | 83 / +0.273 |

Được chọn (chỉ nhìn 2010–2020): S04 GBPUSD, S04 USDJPY, S06B EURUSD, S06B GBPUSD, S06B_USD EURUSD, S06B_USD GBPUSD, T2 EURUSD, T2 GBPUSD.

Sổ gộp 2021–2025: 217 lệnh, R/lệnh -0.030, cận dưới 90% -0.149, sau trừ 0.10R -0.130.
- R/lệnh 2021–25 > 0: KHÔNG
- cận dưới bootstrap 90% > 0: KHÔNG
- sau trừ 0.10R/lệnh > 0: KHÔNG
- Rủi ro 0.5%/lệnh: -0.8%/năm, DD lớn nhất 13% (sau trừ 0.10R: -3.0%/năm, DD 17%)
- Rủi ro 1.0%/lệnh: -1.8%/năm, DD lớn nhất 24% (sau trừ 0.10R: -6.1%/năm, DD 32%)

**Kết luận theo luật: không đạt.**

## Nhận xét

- **Lợi thế FX không giữ được qua thời gian.** 8 ô tốt nhất 2010–2020 cho sổ gộp 2021–2025 là −0,03R/lệnh (−0,13R sau khi trừ thêm chi phí khắt khe ước lượng).
  - Các ô S06B / S06B_USD EURUSD, GBPUSD từng +0,36 đến +0,75R/lệnh, nay chỉ còn quanh 0.
  - T2 EURUSD từ +0,21 xuống −0,19.
- **Ô nào tốt 2021–2025 thì lại bị loại khi chọn**, vì 2010–2020 âm: USDJPY T2 +0,27, S06B_USD +0,38, S06B +0,23. Lợi thế "xoay vòng" giữa các cặp và các giai đoạn, nên chọn theo quá khứ không dự đoán được tương lai.
- **Ô duy nhất dương xuyên suốt: S04 GBPUSD** (+0,46 / +0,07 / +0,25), nhưng chỉ 37 lệnh trong 15 năm (khoảng 2 lệnh/năm). Quá ít để có ý nghĩa với tài khoản.
- **S07 trên FX (G90):** H4 khoảng 0R; khung nhỏ âm.
- **Kết luận:** chưa có cách phối hợp các setup hiện có để lấy lợi nhuận ổn định từ FX, ở mọi khung đã thử (M5 scalp G55, H1/H4 swing G90/G91). Lợi thế của hệ thống nằm ở vàng (S07 mua M30).
