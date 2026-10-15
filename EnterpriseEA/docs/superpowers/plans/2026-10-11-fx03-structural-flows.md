# FX03: dòng tiền có cấu trúc — giờ trong ngày và chốt giá cuối tháng — kế hoạch đăng ký trước (11/10/2026)

## Vì sao

FX01 và FX02 cho thấy mẫu hình giá (setup, chỉ báo, động lượng) không cho lợi thế FX ổn định. Hướng khác là các **dòng tiền có lịch cố định**: giá bị đẩy vì ai đó *phải* giao dịch vào một thời điểm nhất định, chứ không vì ai đoán hướng.

Hai hiệu ứng đã được ghi nhận trong nghiên cứu:
1. **Đồng tiền yếu đi trong giờ làm việc nội địa** (doanh nghiệp và quỹ trong nước mua ngoại tệ trong giờ của họ):
   - EUR/GBP giảm trong giờ châu Âu;
   - USD giảm trong giờ Mỹ;
   - JPY giảm trong giờ Tokyo.
2. **Chốt giá London 16:00 ngày giao dịch cuối tháng**: quỹ cân bằng lại phòng hộ tiền tệ. Đồng USD nào tăng mạnh trong tháng thường bị bán ra trước giờ chốt.

## Dữ liệu và chi phí

- EURUSD, GBPUSD, USDJPY, H1, 2010–10/2025 (MT5).
- Giờ tính theo UTC từ nến (đã chỉnh DST như G54).
- Chi phí mỗi lệnh = spread của nến vào lệnh + phí như G55. Không có SL.
- **Đơn vị R** = ATR14 H1 lúc vào × √(số giờ giữ), tức biên độ kỳ vọng của khung giờ. R = lời/lỗ sau chi phí ÷ đơn vị đó.
- Tiêu chí cuối trừ thêm 0,10R/lệnh.

## Kỳ

| Kỳ | Thời gian |
|---|---|
| Train | 2010–2016 |
| Validate | 2017–2020 |
| Test (không dùng để chọn) | 2021–10/2025 |

## Họ A — giờ nội địa (mỗi ngày làm việc một lệnh mỗi cặp)

Vào ở giá mở nến giờ bắt đầu, ra ở giá đóng nến cuối cửa sổ.

| Mã | Lệnh | Cửa sổ UTC (biến thể) |
|---|---|---|
| A-EU | bán EURUSD, GBPUSD (EUR/GBP yếu giờ châu Âu) | 06–11, 07–12 |
| A-US | mua EURUSD, GBPUSD; bán USDJPY (USD yếu giờ Mỹ) | 12–19, 13–20 |
| A-JP | mua USDJPY (JPY yếu giờ Tokyo) | 00–06, 01–07 |

## Họ B — cuối tháng

Áp vào ngày giao dịch cuối của tháng (theo nến). Dòng USD đầu tháng đến lúc vào = lợi nhuận log từ đầu tháng của chỉ số USD H1 (như `filters.usd_index`).

| Mã | Lệnh |
|---|---|
| B-FIX | từ 10:00 UTC đến giờ chốt (15:00 UTC mùa hè London, 16:00 UTC mùa đông), giao dịch **ngược** dòng USD từ đầu tháng, trên EURUSD, GBPUSD, USDJPY |
| B-POST | sau giờ chốt 4 giờ, giao dịch **cùng** chiều dòng USD từ đầu tháng (giá hồi lại sau chốt) |

## Chọn và kiểm tra

**Chọn** (riêng từng mã):
- Một biến thể đạt khi R/lệnh gộp các cặp > 0 ở cả train và validate, và có ≥ 60 lệnh.
- Lấy biến thể có min(train, validate) cao nhất.
- Không có bộ lọc thêm.

**Kiểm tra** (test 2021–10/2025). Có 5 ô. Ô đạt khi đủ cả ba:
1. R/lệnh > 0;
2. cận dưới bootstrap 90% > 0;
3. sau trừ 0,10R vẫn > 0.

Chỉ đề xuất SHADOW khi cận dưới Bonferroni (0,10/5, tức 98%) cũng > 0.

**Báo cáo thêm:**
- từng cặp;
- R theo năm;
- %/năm và DD ở 0,5%/lệnh;
- R trước chi phí, để thấy hiệu ứng thật lớn đến đâu.

## Đầu ra

`research/fx/fx03_flows.py`, báo cáo `reports/2026-10-11-fx03-structural-flows.md`.
