# CtxLimitTester — chạy thử trong MT5 Strategy Tester

EA kiểm thử cho phương pháp **MKT04 vàng**: mô hình ngữ cảnh (LightGBM) dự báo R của lệnh, vào bằng **limit** (hoặc market), có **bộ lọc và trọng số họ S07**.

Cách viết giống `S07Tester.mq5`: một symbol, không cần file, phiên ký hay registry. Magic riêng (717171), nên chạy chung tài khoản với S07Tester (707070) cũng không lẫn lệnh.

## Cơ chế

1. **Ra quyết định** mỗi khi một nến M30 đóng đúng giờ tròn.
   - Tính 30 thành phần ngữ cảnh: xu hướng đa khung, EMA200 H4/D1, ADX/DI, RSI, vị trí so với đỉnh/đáy ngày trước và VWAP, giờ New York, volume…
   - Bốn mô hình (limit/market × mua/bán) dự báo R.
2. **Vào lệnh** khi dự báo > ngưỡng (limit 0,383; market 0,211, cùng giá trị MKT04 đã chọn trên validate). Nếu cả hai chiều đều qua ngưỡng, lấy chiều cao hơn.
3. **Lọc S07**:
   - chỉ vào cùng phía EMA200 H4 (nến H4 đã đóng);
   - lệnh bán cần thêm vị trí S07S: đỉnh 9 nến M30 ≥ EMA200 H4 − 0,5 ATR.
4. **Trọng số**: 1,0 khi EMA21 > 55 > 100 và giá trên EMA21 (lệnh bán thì ngược lại), ngược lại 0,67.
5. **Lệnh**:
   - **Limit**: cách giá đóng 0,5 × ATR14 H4, chờ 8 nến M30 (4 giờ). Khớp một lệnh thì các limit khác bị hủy.
   - **Market**: vào ở giá mở nến kế tiếp.
   - Cả hai: SL 1 × ATR H4, TP 2 × ATR H4, đóng sau tối đa 96 nến M30 (48 giờ). Một vị thế mỗi lúc.
6. **Rủi ro**: `InpRiskPercent` (mặc định 0,5%) × trọng số.

## File

| File | Dùng cho |
|---|---|
| `CtxLimitTester.mq5` + `CtxLimit/CtxGoldModel.mqh` | EA và mô hình, đã chép và biên dịch trong `MQL5/Experts/EnterpriseEA/` |
| `CtxLimitTester_gold_limit.set` | bản chính: limit + lọc S07 (có trong `MQL5/Presets`) |
| `CtxLimitTester_gold_market.set` | cùng cấu hình nhưng vào lệnh market |

## Chạy test

- **Expert**: `EnterpriseEA\CtxLimitTester`. **Symbol**: XAUUSD của broker. **Khung chart**: M30 hoặc nhỏ hơn.
- **Model**: "Every tick based on real ticks" hoặc "1 minute OHLC".
- **Inputs**: Load → `CtxLimitTester_gold_limit.set`.
- **Chọn ngày**:
  - Mô hình học trên dữ liệu 07/2018–09/2025, nên **chỉ từ 01/10/2025 trở đi là ngoài mẫu**.
  - Ngữ cảnh cần khoảng 200 ngày lịch sử M30 trước ngày bắt đầu, để EMA200 H4/D1 hội tụ.
  - Lịch sử broker có từ 02/2024, nên nên chạy **từ 01/10/2025** (hoặc sớm nhất 01/2025).

## Kết quả mong đợi (Python, cùng mô hình, 10/2025–10/2026)

| Bản | Lệnh | R/lệnh | R × trọng số | %/năm @0,5% × trọng số | DD | Mua / bán |
|---|---|---|---|---|---|---|
| Limit + lọc S07 (`gold_limit.set`) | 52 | +0,475 | +0,388 | +9,8% | 2,2% | 51 / 1 |
| Market + lọc S07 (`gold_market.set`) | 103 | +0,272 | +0,252 | +12,7% | 3,6% | 99 / 4 |

Kết quả tester sẽ khác vì các lý do sau:
- spread và phí thật của broker;
- EMA200 H4/D1 bắt đầu từ lịch sử ngắn hơn;
- tester khớp lệnh theo tick;
- EA cho chờ nhiều limit một lúc, lệnh nào khớp trước thì lấy.

**Lưu ý**: bản có lọc **gần như chỉ mua**, vì lọc S07S loại hầu hết lệnh bán. Muốn xem riêng chiều bán thì để `InpH4SideGate=false`, `InpSellLocation=false`.

## Kiểm tra khớp với Python

Bật `InpParityFile=true` (đã bật trong file set). EA ghi `Common\Files\CtxLimitTester_parity.csv`. Sau khi chạy, đối chiếu bằng:

```
python research/markets/ctx_parity_compare.py
```
