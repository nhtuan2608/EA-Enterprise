# FX03: dòng tiền có cấu trúc — giờ trong ngày và chốt giá cuối tháng — kết quả

Kế hoạch: `plans/2026-10-11-fx03-structural-flows.md`. H1, giờ UTC. R = lời/lỗ sau chi phí ÷ (ATR14 H1 × √giờ giữ). Ô: số lệnh / R mỗi lệnh (sau chi phí). Cột cuối: R trước chi phí, mọi kỳ.

| Mã | Biến thể | Train 2010–16 | Validate 2017–20 | Đạt? | Test 2021–25 | R trước chi phí (mọi kỳ) |
|---|---|---|---|---|---|---|
| A-EU | 06–11 | 3628 / +0.016 | 2073 / -0.007 |  | 2476 / -0.069 | +0.056 |
| A-EU | 07–12 | 3632 / +0.015 | 2073 / -0.027 |  | 2476 / -0.038 | +0.060 |
| A-US | 12–19 | 5424 / -0.047 | 3109 / -0.045 |  | 3714 / -0.043 | +0.009 |
| A-US | 13–20 | 5390 / -0.042 | 3109 / -0.042 |  | 3714 / -0.034 | +0.011 |
| A-JP | 00–06 | 1810 / -0.135 | 1035 / -0.132 |  | 1238 / -0.012 | -0.027 |
| A-JP | 01–07 | 1809 / -0.124 | 1035 / -0.106 |  | 1238 / -0.013 | -0.018 |
| B-FIX | 10:00→chốt, ngược USD | 249 / -0.076 | 144 / -0.220 |  | 174 / +0.065 | -0.006 |
| B-POST | chốt→+4h, cùng USD | 231 / +0.041 | 144 / -0.074 |  | 174 / -0.052 | +0.036 |

## Kiểm tra cuối (2021–10/2025)

**Không mã nào qua bước chọn.**

## Kết luận

**FX03 không đạt.**

- **EUR/GBP yếu trong giờ châu Âu (A-EU) có thật nhưng quá nhỏ.** Trước chi phí +0,06R/lệnh, cùng dấu ở mọi kỳ. Sau chi phí (spread + phí khoảng 0,07R) còn khoảng 0. Với broker hiện tại, chi phí lớn hơn hiệu ứng.
- **USD yếu giờ Mỹ (A-US)** trước chi phí ≈ +0,01: gần như không có. **JPY yếu giờ Tokyo (A-JP)** thì ngược dấu.
- **Chốt giá cuối tháng (B-FIX, B-POST)** đổi dấu giữa các kỳ, khoảng 50 lệnh/năm, không ổn định. Dòng USD từ đầu tháng là đại diện yếu cho nhu cầu phòng hộ thật, vốn phụ thuộc vào chênh lệch cổ phiếu Mỹ/ngoài Mỹ, mà dữ liệu đó không có trong MT5 đủ dài.
