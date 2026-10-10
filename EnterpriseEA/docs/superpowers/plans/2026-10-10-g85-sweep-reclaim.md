# G85: Quét thanh khoản rồi đảo chiều (Sweep → Reclaim), mua và bán — kế hoạch đăng ký trước (10/10/2026)

## Vì sao (từ 4 ví dụ M15 của người dùng, đối chiếu dữ liệu MT5)

- **02/10 (bán):** 12:30 UTC (New York mở / tin Mỹ) có nến vọt lên quét đỉnh 48 nến (+DI 44). 2 giờ sau −DI cắt xuống, giá đóng dưới cả 4 EMA, rồi rơi khoảng 60 giá. S07 chỉ vào sau khi giá đã rơi.
- **28/08 (bán)** và **02/09 (đáy, mua)**: cùng kiểu, râu quét đỉnh/đáy rồi đảo chiều. Đáy 02/09 quét lúc 03:30 UTC, mua lúc 10:00 UTC.
- **23/09 (bán):** không có cú quét rõ. ADX của nhịp tăng 34 rồi quay xuống, DI cắt lúc 01:00 UTC (Á mở). Đây là kiểu "đảo chiều sau cú đẩy" đã thử ở G80 (âm).
- **17/09 (mua):** sau cú sập (quét đáy, volume gấp đôi), giá nén, ADX về 12, DI cắt lên lúc 05:45 UTC. S07 M15/M30 **có ra tín hiệu mua** nhưng bị **lọc H4** chặn vì H4 vẫn dưới EMA200.

Người dùng: chú ý toàn bộ phiên, **tròn giờ**, và **quét thanh khoản ở các khung giao phiên**.

## Phần A — setup SR (Sweep → Reclaim), mua và bán

Khung vào lệnh: M15 (cửa sổ quét N = 48 nến = 12 giờ, chờ tối đa K = 12 nến = 3 giờ) và M30 (N = 24, K = 6). M5 chỉ kiểm tra từ 05/2024.

**Cú quét đỉnh** (cho lệnh bán; mua đối xứng): nến s có đỉnh > đỉnh cao nhất N nến trước đó.

**Xác nhận đảo chiều** ở nến i, trong K nến sau s (s < i ≤ s + K), lần đầu tiên thỏa:
- −DI > +DI (DI đã cắt);
- giá đóng < đáy nến quét s;
- dải EMA:
  - **E4:** giá đóng dưới cả 4 EMA;
  - **E2:** giá đóng dưới EMA21 và EMA55 (nới).

**Vào lệnh và thoát:**
- Vào ở giá mở nến kế tiếp.
- SL = đỉnh cú quét + 0,1 ATR, trong 1–4 ATR (xa hơn thì bỏ).
- Thoát:
  - X1: E2X, TP 8R;
  - X2: TP 2R hoặc đóng ngược EMA21;
  - X3: ADX ≥ 50 rồi quay xuống, ngoài ra như X1.

**Lọc thời gian của cú quét:**

| Mã | Điều kiện |
|---|---|
| T0 | mọi giờ |
| TS | nến quét nằm trong khung giao phiên: 23:00–01:59 UTC (Á mở), 06:00–08:59 (London), 12:00–14:59 (New York) |
| TR | nến quét đóng tròn giờ (:00) hoặc :30 |

**Lưới:** 2 khung × 2 dải EMA × 3 thoát × 3 lọc thời gian = **36 bộ mỗi chiều**. Một lệnh mỗi lúc, nghỉ 4 nến sau lệnh, chi phí khắt khe G68.

## Kỳ

- Train 20/07/2021–2023, validate 2024–06/2025, test 07/2025–06/2026.
- 2018–2021 (M30) và 07/2026–nay chỉ báo cáo.

## Tiêu chí (chốt trước, từng chiều)

1. Ứng viên: dương ở cả train và validate, với ≥ 60 lệnh train + validate.
2. Chọn bộ có R/lệnh train + validate cao nhất.
3. Bộ được chọn **đạt** khi đủ cả ba:
   - test > 0, và 2018–2021 ≥ 0 nếu có dữ liệu;
   - thắng vào lệnh ngẫu nhiên p < 0,05/36 (2000 lần, cùng số lệnh mỗi kỳ, cùng chiều, cùng SL theo ATR, cùng thoát);
   - cùng bộ trên khung còn lại (M15 ↔ M30) dương ở train và validate.

Báo cáo thêm: các ví dụ của người dùng có được bắt không, và lúc nào.

## Phần B — bộ lọc H4 cho lệnh mua sau cú sập (ví dụ 17/09)

Trên tập con tín hiệu mua S07 M15 / M30 **bị lọc H4 chặn** (H4 dưới EMA200), chia hai nhóm theo việc có cú quét đáy N nến trong 2W nến trước tín hiệu hay không. Chấm theo cách G79: R/lệnh từng kỳ, kèm hoán vị.

**"Nới H4 khi vừa có cú quét đáy" đạt** khi đủ cả hai:
- nhóm có cú quét đáy dương ở ≥ 3/4 kỳ (M30) hoặc 3/3 kỳ (M15), và tốt hơn nhóm không có quét;
- p < 0,05/2.

## Đầu ra

`research/long/g85_sweep.py`, báo cáo `reports/2026-10-10-g85-sweep-reclaim.md`.
