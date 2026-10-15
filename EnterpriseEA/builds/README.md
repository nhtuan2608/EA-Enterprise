# Bản build .ex5

Build bằng MetaEditor ngày 15/10/2026 từ mã nguồn tại commit `bed12ba` trên `main`. Cả 7 EA đều 0 lỗi, 0 cảnh báo.

| File | EA | Magic mặc định |
|---|---|---|
| `EnterpriseEA.ex5` | EA chính (live, nhiều setup, phiên ký, giới hạn rủi ro) | 888888 |
| `EnterpriseS07.ex5` | Bản live chỉ họ S07 | 707707 |
| `S07Tester.ex5` | Tester / chạy trực tiếp họ S07 | 707070 |
| `XauRegimeTester.ex5` | Chế độ D1 vàng (G96) | 969696 |
| `CtxLimitTester.ex5` | MKT04 dự báo ngữ cảnh, lệnh limit | 717171 |
| `CtxBoxTester.ex5` | Bối cảnh bật + giữ theo hộp nghỉ (G106) | 106106 |
| `VHedgeTester.ex5` | Nến V quanh EMA200, hedge (G119/G120), mặc định SHADOW | 116119 |

## Cách dùng

Chép các file vào `MQL5\Experts\EnterpriseEA\` của terminal, rồi bấm Refresh trong Navigator. Trên VPS, chép vào `/opt/qtl/data/mt5/terminal/MQL5/Experts/EnterpriseEA/`.

File .set nằm trong `MQL5\Presets` và `MQL5\Profiles\Tester` của terminal, không có trong repo.

## Lưu ý

- `S07Tester` và `XauRegimeTester` khi chạy trong Strategy Tester đọc thêm `S07Tester_news.csv` và `S07Tester_sentiment.csv` trong `MQL5\Files`. Khi chạy trên chart, hai bot này đọc tin và sentiment trực tiếp từ MT5.
- Bản build không tự cập nhật. Mã nguồn đổi thì phải build lại.
