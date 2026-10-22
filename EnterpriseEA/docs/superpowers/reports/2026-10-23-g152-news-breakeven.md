# G152 — hòa vốn trước tin (News Guard) trên sổ S07 (23/10/2026)

Kế hoạch đăng ký trước: [2026-10-23-g152-news-breakeven.md](../plans/2026-10-23-g152-news-breakeven.md) (commit `a0d0c91`). Script
[`g152_news_breakeven.py`](../../research/long/g152_news_breakeven.py). Sổ S07 M30 G89, 1.208 chân, 05/2018 → 06/2026. Rủi ro như EA. Mô
phỏng vốn G134.

## Số lệnh bị ảnh hưởng

| Biến thể | Lệnh bị dời SL về giá vào | Đóng ở hòa vốn | trong đó: được cứu (gốc kém hơn) | bị cắt lãi (gốc tốt hơn) |
|---|---|---|---|---|
| V1 như EA (mọi tin trừ danh sách bỏ qua, ≥ 0,3R) | 284 | 118 | 70 | 48 |
| V2 chỉ tin lớn (NFP, CPI, Core PCE, Fed, FOMC) | 116 | 49 | 30 | 19 |
| V3 mọi tin, ≥ 2R | 126 | 20 | 12 | 8 |

## Kết quả

Ô: tổng R / R mỗi chân / **MAR** (%/năm, DD).

| Biến thể | 05/2018–2021 | 2022–2023 | 2024–06/2026 | DD p90 1 năm |
|---|---|---|---|---|
| **V0 không hòa vốn** | 50,9 / 0,113 / **0,84** (20 %, 24 %) | 76,3 / 0,291 / **2,42** (34 %, 14 %) | 282,5 / 0,568 / **13,14** (223 %, 17 %) | 20,8 % |
| **V1 như EA hiện tại** | 56,6 / 0,126 / **0,99** (22 %, 23 %) | 75,0 / 0,286 / **3,20** (36 %, 11 %) | 217,1 / 0,437 / **9,19** (145 %, 16 %) | 19,7 % |
| V2 chỉ tin lớn | 54,5 / 0,121 / **0,93** | 82,3 / 0,314 / **2,89** | 273,0 / 0,549 / **13,13** | 20,1 % |
| V3 mọi tin, ≥ 2R | 49,1 / 0,109 / **0,85** | 77,0 / 0,294 / **2,46** | 282,9 / 0,569 / **14,34** | 20,4 % |

Theo năm (tổng R), V0 so với V1:
- 2018 −10,5 / −10,5; 2019 20,2 / 21,9; 2020 43,9 / 47,2; 2021 −2,7 / −2,0;
- 2022 36,1 / 36,8; 2023 40,2 / 38,1;
- **2024 126,2 / 79,3; 2025 101,3 / 88,8**; 2026 55,1 / 49,1.

V0 − V1 tổng 61,1R, p bootstrap 0,0045.

## Kết luận theo luật: **KHÔNG ĐẠT** (bỏ hòa vốn trước tin cho S07)

Bỏ quy tắc chỉ tốt hơn ở **2024–2026** (+65R, MAR 13,1 so với 9,2), là giai đoạn vàng tăng mạnh nên để lệnh chạy là lợi. Ở **2018–2021 và
2022–2023**, quy tắc hiện tại cho MAR **cao hơn** (0,99 so với 0,84; 3,20 so với 2,42). Nó cứu 70 lệnh và cắt lãi 48 lệnh, chủ yếu giảm sụt
giảm trong giai đoạn giá đi ngang.

Đây là **đánh đổi theo chế độ thị trường**, không có lựa chọn thắng ở mọi kỳ:
- thị trường xu hướng mạnh → bỏ hòa vốn tốt hơn;
- thị trường đi ngang / giật → hòa vốn tốt hơn.

**Gợi ý (không quyết định, theo kế hoạch)**: **V2 "chỉ hòa vốn trước tin lớn"** là thỏa hiệp gần như không thua V0:
- tổng R cao hơn V0 ở 2 / 3 kỳ;
- MAR hơn V0 ở 2018–21 và 2022–23, bằng V0 ở 2024–26;
- so với V1 hiện tại, giữ được phần lớn lãi của giai đoạn xu hướng: 2024–26 273R so với 217R.

Nếu muốn đổi, V2 là ứng viên hợp lý nhất. Nhưng nó chưa qua một phép thử đăng ký riêng (V2 được ghi là "chỉ báo cáo"). Bước đúng tiếp theo:
- đăng ký G152b với V2 làm ô quyết định, kiểm bằng dữ liệu forward;
- hoặc thêm input "danh sách tin hòa vốn" cho S07, mặc định giữ như hiện tại.

Ghi chú G151: lần so sánh với tester MT5 cũng cho thấy đúng hiện tượng này trên 02/2024–10/2026. Hai nguồn khớp nhau.
