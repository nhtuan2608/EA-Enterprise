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

Phần lớn file .set nằm trong `MQL5\Presets` và `MQL5\Profiles\Tester` của terminal, không có trong repo.

Riêng các set cho VHedge G119 (bỏ BIGV, 0,75% mỗi chân, INITIAL) có trong `builds/sets/`:
- `VHedgeTester_G119_shadow.set`: chỉ lệnh ảo.
- `VHedgeTester_G119_live.set`: lệnh thật, chỉ dùng cho tài khoản hedging.

Trên VPS, chép các file này vào `/opt/qtl/data/mt5/terminal/MQL5/Presets/`.

## EnterpriseEA_Bots (build lại 23/10/2026)

`EnterpriseEA_Bots.ex5` là EnterpriseEA có lớp Bots, build từ `main` `737a3e7`. Gồm:
- nhật ký bot `logs/bots-YYYYMM.jsonl` và nhận lệnh bật/tắt bot từ MCP (input `InpBotsMcpCommands`);
- **trọng số D1 × 0,5** cho lệnh S07 ngược trạng thái golden/death cross D1 (`InpS07D1CrossWeight = 0.5`, G134, kiểm lại ở G138);
- tùy chọn S07AS độc lập (`InpS07AsStandalone`, mặc định tắt; G136 không ủng hộ bật);
- phạm vi hòa vốn trước tin cho lệnh S07 (`InpS07NewsBreakEvenScope`: `ALL` như cũ, **mặc định** / `TOP_TIER` chỉ NFP, CPI, Core PCE, Fed, FOMC / `OFF`; G152, chờ kiểm forward G152b);
- nhãn DXY cho tín hiệu S07 vàng (chỉ ghi log).

Bản 16/10 không có trọng số D1. Các preset bên dưới không ghi đè hai input này, nên dùng mặc định. Một EA chạy cả 4 chiến lược: S07, VHedge G119, XauRegime và CtxLimit. Nó thay cho 4 bản tester.

Set nằm trong `builds/sets/`:

| File | Dùng cho |
|---|---|
| `EnterpriseEA_Bots_demo.set` | Demo: S07 LIVE, các bot SHADOW |
| `EnterpriseEA_Bots_demo_all_live.set` | Demo: tất cả LIVE |
| `EnterpriseEA_Bots_vps_cent.set` | VPS cent: tất cả LIVE, cho phép phiên trên tài khoản thật |

Hướng dẫn: `docs/bots-host-guide.md`.

**Chỉ gắn một EnterpriseEA_Bots cho mỗi tài khoản**, và tháo S07Tester, VHedgeTester, XauRegimeTester, CtxLimitTester ra trước.

## Lưu ý

- `S07Tester` và `XauRegimeTester` khi chạy trong Strategy Tester đọc thêm `S07Tester_news.csv` và `S07Tester_sentiment.csv` trong `MQL5\Files`. Khi chạy trên chart, hai bot này đọc tin và sentiment trực tiếp từ MT5.
- Bản build không tự cập nhật. Mã nguồn đổi thì phải build lại.
