# G86: Gộp S07+ và bối cảnh nến (mô hình nến làm nền) — kế hoạch đăng ký trước (10/10/2026)

## Vì sao

1. Người dùng: gộp các phiên bản S07 rải rác thành một bản tốt hơn.
2. Người dùng (4 ví dụ M15): **trạng thái nến và mô hình nến** là chính, ADX/EMA chỉ phụ. Hệ thống cần nắm bối cảnh nến làm nền trước khi kích hoạt S07 hoặc các bản mở rộng.

Mô tả nến ở các ví dụ (dữ liệu MT5):

| Ví dụ | Diễn biến nến |
|---|---|
| 02/10 bán | Nến vọt 3,9 ATR (đỉnh mới 12 giờ) → nến nằm trong → **nhấn chìm giảm 2,5 ATR**; sau đó râu dưới/doji chững lại, rồi thân đặc nhấn chìm phá đáy |
| 23/09 bán | ~3 giờ **nến hẹp / doji / có râu** sát đỉnh → nhấn chìm → nến phá 2 ATR |
| 17/09 mua | Bán tháo: nhiều nến dài **volume ≥ 2×** phá đáy → doji / nến nằm trong → ~4 giờ **nến hẹp tạo nền** → **nhấn chìm tăng 1,5 ATR** qua EMA21 |
| 02/09 mua | Râu dưới quét đáy → **nhấn chìm tăng** → nền nến hẹp → nhấn chìm tăng 2,1 ATR |

## Định nghĩa nến (theo chiều lệnh d; ATR14 Wilder)

- **Nến dài:** biên độ ≥ 1,5 ATR. **Nến hẹp:** biên độ ≤ 0,5 ATR.
- **Doji:** thân ≤ 15% biên độ. **Nến nằm trong:** đỉnh ≤ đỉnh trước và đáy ≥ đáy trước.
- **Nhấn chìm theo chiều d:** thân theo chiều d, phủ trọn thân nến trước ngược chiều.

## Phần A — S07+ (gộp, sổ mua M30 + bồi S07A, mô phỏng trên nến M30)

| Bước | Thay đổi so với bước trước |
|---|---|
| A0 | S07 hiện tại: gốc M30 1,5%, bồi S07A 1,5%, tối đa 3 lệnh mở, thoát E2X |
| A1 | Lệnh gốc thoát **X3**: ADX ≥ 50 rồi quay xuống thì thoát nến sau, ngoài ra như E2X |
| A2 | Lệnh gốc **không** có nhãn dải EMA xếp thứ tự → 1,0% (có nhãn giữ 1,5%) |
| A3 | Lệnh bồi → 1,0% |

Vào sớm theo nến M15 (S07E) cần mô phỏng trên nến nhỏ, không ghép được vào sổ này. S07E tiếp tục SHADOW riêng.

**Một bước được giữ** khi, so với bước trước, ở cả 09/2018–06/2026 và 07/2021–06/2026:
- tỉ số %/năm ÷ DD p90 1 năm cao hơn;
- chạm 30% không tăng;
- %/năm ≥ 90% bước trước.

Bản cuối = bước cuối cùng còn được giữ (bỏ bước nào không đạt rồi xét bước tiếp theo trên nền đã giữ).

## Phần B — nhãn bối cảnh nến trên tín hiệu S07 (M15, M30, H1; mua và bán)

Xét K = 16 nến (M15), 8 (M30), 4 (H1) trước và gồm nến tín hiệu.

| Mã | Nhãn |
|---|---|
| C1 | **cao trào rồi đảo:** trong 3K nến trước có nến dài **ngược** chiều lệnh tạo đỉnh/đáy mới 48 nến, và sau nó có nhấn chìm hoặc nến dài **theo** chiều lệnh |
| C2 | **chững / tạo nền:** ≥ 50% của K nến trước tín hiệu là nến hẹp, doji hoặc nằm trong |
| C3 | **bán tháo / mua đuổi có volume:** trong 3K nến trước có ≥ 3 nến volume tương đối ≥ 1,8 chạy ngược chiều lệnh |
| C4 | **nến tín hiệu mạnh:** nhấn chìm theo chiều lệnh, hoặc thân ≥ 70% biên độ và biên độ ≥ 1,2 ATR |
| C5 | **râu quét ngược:** trong K nến trước có nến râu ≥ 50% biên độ tạo đỉnh/đáy mới 48 nến ngược chiều lệnh, rồi đóng ngược lại |

Cách chấm như G79 (tập con lệnh gốc, mua có lọc H4, bán không, thoát E2X, chi phí khắt khe).

**Một nhãn đạt** khi đủ cả ba:
- nhóm có nhãn tốt hơn nhóm không nhãn ở mọi kỳ có dữ liệu;
- R/lệnh nhóm có nhãn ≥ +0,3 ở validate và test;
- hoán vị p < 0,05/30.

## Phần C — setup chỉ dựa vào nến ("CB": nền rồi nhấn chìm phá nền), mua và bán

**Tín hiệu** ở nến i, khi đủ cả ba:
- ≥ 50% của 12 nến trước là nến hẹp / doji / nằm trong (nền);
- nến i là C4 theo chiều d;
- giá đóng vượt đỉnh (mua) / đáy (bán) của 12 nến nền **và** vượt EMA21 theo chiều d.

**Vào lệnh:**
- Vào ở giá mở nến kế tiếp.
- SL = đáy (đỉnh) của nền ∓ 0,1 ATR, trong 1–4 ATR.

**Lưới:**
- Khung M15, M30.
- Bối cảnh: không thêm, hoặc C1/C3/C5 (có ít nhất một).
- Thoát: X1 (E2X, TP 8R) hoặc X2 (TP 2R / đóng ngược EMA21).
- Tổng 8 bộ mỗi chiều.

**Tiêu chí** (như G80): dương ở train và validate với ≥ 60 lệnh; chọn bộ tốt nhất. Bộ đó đạt khi đủ cả ba:
- test > 0 (và 2018–2021 ≥ 0 nếu có);
- thắng ngẫu nhiên p < 0,05/8;
- khung còn lại dương ở train và validate.

Báo cáo các ví dụ của người dùng có được bắt không.

## Đầu ra

`research/long/g86_merge_candles.py`, báo cáo `reports/2026-10-10-g86-merge-candle-context.md`.
