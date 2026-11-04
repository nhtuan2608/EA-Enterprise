# G158 — hedge / bồi lệnh không SL với entry price action (04/11/2026)

Kế hoạch: [2026-11-04-g158-hedge-recovery.md](../plans/2026-11-04-g158-hedge-recovery.md) (commit `c7f4a3e`). Script
[`g158_hedge_recovery.py`](../../research/long/g158_hedge_recovery.py), kết quả `research/long/results/g158/summary.json`.

**Mô hình tài khoản:**
- 10.000 USD, lot gốc 0,10, đòn bẩy 1:500;
- stop-out ở mức ký quỹ 50 %, tính tại giá bất lợi nhất trong nến;
- swap −30 USD / lot / đêm cho cả hai chiều.

**Kỳ:**
- H1 thật: chọn 05/2018–2022, kiểm 2023–10/2026;
- stress D1 2010–2018: entry ngẫu nhiên, đường giá bi quan.

**Kết luận: KHÔNG ĐẠT.** Không cấu hình nào sống sót đủ các điều kiện (B). Entry price action chỉ hơn entry ngẫu nhiên ở mức sát ngưỡng (E4,
E5), hoặc không hơn.

## Số tín hiệu (05/2018–10/2026)

| E1 OB H4 | E2 OB + xác nhận H1 | E3 OB + hợp lưu | E4 pullback có volume | E5 Fibonacci OTE | E6 quét thanh khoản |
|---|---|---|---|---|---|
| 212 | 73 | 157 | 84 | 874 | 1.639 |

## Cấu hình tốt nhất mỗi họ (chọn trên 05/2018–2022, ưu tiên 0 cháy)

| Họ | Cấu hình | Kỳ chọn: cháy / lãi / DD | **Kỳ kiểm**: cháy / lãi / DD | Thả nổi tệ nhất | Ngẫu nhiên cùng cấu hình: lãi p50 / p95, % lần chạy có cháy | (A) entry có giá trị |
|---|---|---|---|---|---|---|
| E1 | lưới × 1,5, bước 1 ATR, 6 lệnh, TP 3S | 0 / +15.266 / 88 % | **1 cháy** / −6.909 | −47.287 | +508 / +22.223, 80 % | không |
| E2 | lưới × 2, bước 1, 6 lệnh, TP 3S | 0 / +9.700 / 29 % | 0 / +24.508 / 49 % | −9.711 | −1.929 / +13.259, 66 % | không |
| E3 | lưới × 1,5, bước 1, 6 lệnh, TP 3S | 0 / +13.492 / 92 % | **1 cháy** / −6.909 | −45.026 | +3.360 / +20.470, 64 % | không |
| **E4** | lưới × 1,5, bước 0,5, 10 lệnh, TP 3S | 0 / +13.703 / **53 %** | 0 / +15.686 / 35 % | −5.775 | −41 / +13.478, 54 % | **có** (sát ngưỡng) |
| E5 | lưới × 2, bước 0,5, 6 lệnh, chốt cả rổ | 0 / +63.152 / 22 % | **1 cháy** / +11.576 | **−108.307** | +40.400 / +62.684, 52 % | có (sát ngưỡng) |
| E6 | lưới × 1,5, bước 0,5, 6 lệnh, chốt cả rổ | 0 / +43.773 / 80 % | **1 cháy** / +9.691 | −90.559 | +36.981 / +70.806, 74 % | không |

Số cấu hình (trong 100) không cháy ở kỳ chọn: E1 26, E2 58, E3 24, E4 51, E5 23, E6 13. Mọi cấu hình tốt nhất đều là **lưới bồi cùng chiều
(R1)**; zone recovery hedge xen kẽ (R2) không lọt lên đầu ở họ nào.

## Kiểm tra (B) cho các cấu hình tốt nhất

| Họ | Cả hai kỳ 0 cháy | Cháy trong 12 tháng | DD < 50 % | Swap −60, chi phí × 1,5 | Đòn bẩy 1:100 | Stress D1 2010–18 (% lần chạy cháy) | Láng giềng 0 cháy |
|---|---|---|---|---|---|---|---|
| E1 | không | 29 % | không | 4 cháy | 0 cháy | 40 % | 0 / 4 |
| E2 | có | **1,1 %** | có | 0 cháy, +30.402 | 0 cháy | 35 % | 1 / 3 |
| E3 | không | 27 % | không | 4 cháy | 3 cháy | 55 % | 1 / 4 |
| **E4** | **có** | **0 %** | **không (53 %)** | **0 cháy, +25.919** | 0 cháy | **35 %** | **2 / 4** |
| E5 | không | 9 % | không | 1 cháy | 1 cháy | 0 % | 0 / 3 |
| E6 | không | 29 % | không | 1 cháy | 1 cháy | 0 % | 1 / 4 |

## Đọc kết quả

1. **Entry ngẫu nhiên với cùng cơ chế bồi lệnh vẫn "lãi" trong phần lớn lần chạy**, nhưng **52–80 % số lần chạy có ít nhất một lần cháy
   tài khoản** trong 2018–2022. Lãi của hệ thống bồi lệnh chủ yếu đến từ cơ chế (bán rủi ro đuôi), không đến từ entry.
2. **Entry price action chỉ giúp một chút:**
   - E4 (pullback theo trend có volume xác nhận) và E5 (Fibonacci OTE) vượt phân vị 95 % của ngẫu nhiên, nhưng sát ngưỡng;
   - OB khung lớn (E1), OB + hợp lưu (E3), quét thanh khoản (E6) **không hơn** ngẫu nhiên.

   Khớp G109 / G111 / G156c (mức và vùng không giữ giá hơn mức giả).
3. **Lãi càng lớn thì rủi ro đuôi càng lớn.** E5 lãi +63.152 ở kỳ chọn nhưng kỳ kiểm có lúc thả nổi −108.307 USD trên vốn 10.000, rồi cháy.
4. **E4 là nền gần đạt nhất:**
   - 0 cháy ở cả hai kỳ;
   - xác suất cháy 12 tháng 0 %;
   - chịu được swap −60 và chi phí × 1,5;
   - thả nổi tệ nhất chỉ −5.775.

   Trượt ở:
   - DD 53 % (theo giá bất lợi trong nến) ở kỳ chọn;
   - stress 2010–2018 (35 % lần chạy cháy với entry ngẫu nhiên, đợt vàng giảm 2011–2015);
   - chỉ 2 / 4 láng giềng không cháy.
5. **Swap đáng kể:** E1 / E3 trả 5.000–7.000 USD swap mỗi kỳ. Swap gấp đôi (−60) làm E1 / E3 cháy 4 lần.

## Kết luận và hướng G159

Theo luật đăng ký: **không có cấu hình nào đạt**. Không đề xuất chạy, kể cả chạy ảo.

Cho G159 (khung đã viết trước kết quả, commit `c98ef9d`):
- **cấu hình nền** = E4 + lưới × 1,5, bước 0,5 ATR D1, tối đa 10 lệnh, TP 3S;
- module ưu tiên, nhắm đúng ba chỗ E4 trượt:
  - F1 (không bồi ngược chiều D1) + H1 / H2 (hedge khi D1 đổi chiều hoặc cấu trúc H4 gãy): nhắm stress 2011–2015;
  - F5 / F6 (ký quỹ tối thiểu để bồi, trần lot) và P1 (cắt cặp liên tục): nhắm DD 53 %;
  - kiểm láng giềng lại sau khi thêm module.
