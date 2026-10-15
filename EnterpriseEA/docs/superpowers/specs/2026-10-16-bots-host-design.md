# Bots Host: S07 + VHedge G119 + XauRegime + CtxLimit trong EnterpriseEA — thiết kế

Ngày 16/10/2026. Nhánh `feature/bots-host`.

## Yêu cầu

Người dùng muốn bốn chiến lược chạy trong EnterpriseEA:

| Chiến lược | Nguồn hiện tại |
|---|---|
| S07 | Có sẵn trong EnterpriseEA |
| VHedge G119 | VHedgeTester |
| XauRegime | XauRegimeTester |
| CtxLimit | CtxLimitTester |

Yêu cầu chi tiết:
- Mỗi chiến lược chạy riêng nhưng dùng chung một portfolio.
- Settings trên chart có tab **Bots** để bật / tắt (Active / Inactive) từng chiến lược.
- Bật / tắt được từ Telegram, kể cả bằng câu nói tự nhiên qua AI.

**Người dùng đã chốt (16/10/2026):**
1. **Kiến trúc:** dựng một lớp Bots riêng, gồm nhiều module; tất cả qua một Portfolio Guard chung. Không đi qua đường controlled-live.
2. **S07:** dùng engine S07 có sẵn trong EnterpriseEA. Cờ Active chỉ chặn lệnh S07 mới.
3. **Khi Inactive:** không vào lệnh mới, nhưng vẫn quản lý lệnh đang mở và lệnh chờ đã đặt cho tới khi đóng hết.
4. **Telegram:** tắt có hiệu lực ngay; bật phải `/confirm` bằng mã 6 số. AI chỉ dịch câu nói thành lệnh chuẩn.

## Thành phần

| File | Vai trò |
|---|---|
| `Bots/BotRegistry.mqh` | Mã bot (`S07`, `VHEDGE`, `XRT`, `CTXLIMIT`), tên hiển thị, magic, chế độ OFF / SHADOW / LIVE |
| `Bots/BotState.mqh` | Cờ Active lưu ở `current/bots_state.json`, gắn với tài khoản và config. Có nonce chờ bật. Hàm `EEA_BotActive(id)` |
| `Bots/PortfolioGuard.mqh` | Kiểm tra trước **mọi** lệnh mới của một bot (xem bảng dưới) |
| `Bots/VHedgeBot.mqh` | Port của VHedgeTester thành class `CVHedgeBot`, giữ nguyên luật. Thêm lưu nhóm lệnh để không mất quản lý khi khởi động lại |
| `Bots/XrtBot.mqh` | Port XauRegimeTester (giai đoạn 2) |
| `Bots/CtxLimitBot.mqh` | Port CtxLimitTester (giai đoạn 2) |
| `Bots/BotHost.mqh` | Gọi các bot: `OnTick` (nến mới + quản lý lệnh), `OnTimer`. Ghi `current/bots_status.json` cho Telegram. Xử lý lệnh bật/tắt |
| `Bots/BotRemote.mqh` | Lệnh Telegram cho bot, dùng hàng đợi `current/remote/bot_commands`, ghi kết quả vào `current/remote/results` |

### Portfolio Guard: điều kiện để một bot được vào lệnh mới

Phải thỏa tất cả:

| # | Điều kiện | Ghi chú |
|---|---|---|
| 1 | Bot đang Active, chế độ LIVE | SHADOW chỉ ghi lệnh ảo |
| 2 | EA đã bật vào lệnh | `InpExecutionEnabled`, `InpLiveTradeArmed`, không ở `InpObserverOnly` — giống S07 |
| 3 | Không bị `/pause` từ Telegram | |
| 4 | Lỗ trong ngày chưa chạm trần | `InpBotsDailyLossPct`, tính từ equity đầu ngày server |
| 5 | Rủi ro mở toàn tài khoản cộng lệnh mới ≤ trần | `InpBotsMaxOpenRiskPct` × vốn ban đầu (INITIAL). Rủi ro mở là tổng khoảng tới stop của mọi lệnh và lệnh chờ trên tài khoản, mọi magic |
| 6 | Không trong cửa sổ tin HIGH | Dùng News Guard của EnterpriseEA; tắt được theo từng bot |

S07 đã tự tính rủi ro trên toàn tài khoản, kể cả lệnh của các bot khác. Luật D4 (không giữ hai chiều ngược nhau trên một symbol) chỉ xét lệnh của EnterpriseEA, nên VHedge hedge không chặn S07.

## Bảng điều khiển trên chart

**Settings › tab Bots:** mỗi bot một dòng.

| Cột | Nội dung |
|---|---|
| Tên | Tên bot |
| Magic | Magic number |
| Chế độ | OFF / SHADOW / LIVE |
| Active | Nút bật/tắt. Bấm trên chart có hiệu lực ngay, ghi audit, nguồn PANEL |
| Lệnh mở | Số lệnh đang mở |
| Rủi ro mở | Theo % vốn |
| Lãi / lỗ hôm nay | |
| Trạng thái | Tín hiệu gần nhất hoặc lý do bị chặn |

## Telegram

| Lệnh | Hành vi |
|---|---|
| `/bots` | Danh sách bot: Active/Inactive, chế độ, lệnh mở, lãi/lỗ hôm nay. Đọc từ `bots_status.json` |
| `/bot off <tên>` | Tắt ngay |
| `/bot on <tên>` | Gửi mã 6 số. `/confirm <mã>` mới bật (EA kiểm tra lại toàn bộ cổng) |
| Câu tự nhiên của operator | Ví dụ "tắt VHedge đi", "bật lại S07". Gateway gửi AI một yêu cầu chỉ để hiểu ý (chỉ cho phép `BOT_ENABLE`, `BOT_DISABLE`, `NONE`). AI trả lệnh chuẩn. Tắt thì áp dụng ngay; bật thì đi qua bước xác nhận như trên. Câu trả lời ghi rõ "AI hiểu là: …" |

Lệnh Telegram cho bot dùng hàng đợi riêng, không ảnh hưởng `operator_mode.json`. `/confirm` của gateway phân biệt mã đang chờ là mã resume hay mã bật bot.

## Lưu trạng thái và an toàn

- **`bots_state.json`:**
  - Thiếu file: lấy Active theo input, ghi file mới.
  - File hỏng hoặc thuộc tài khoản/config khác: mọi bot Inactive (fail closed) và ghi audit.
- **Lệnh mới của VHedge:** mỗi nhóm lệnh được ghi vào `current/bots/vhedge_groups.json` (ticket, stop, TP, phase). Khi khởi động lại, nhóm được khôi phục và gắn lại với lệnh thật theo ticket. Bản tester cũ bỏ mặc lệnh khi khởi động lại; bản mới thì không.
- **VHedge LIVE cần tài khoản hedging.** Tài khoản netting thì bot tự chuyển SHADOW và ghi lý do.
- **Các bot chạy theo tick** (nến mới, quản lý stop). Đường S07 vẫn chạy theo timer như cũ.

## Giai đoạn

| Giai đoạn | Nội dung |
|---|---|
| 1 | Registry + State + Guard + Host + VHedgeBot + gắn Active vào S07 + tab Bots. Biên dịch, test tĩnh, so khớp VHedgeBot với VHedgeTester trong Strategy Tester |
| 2 | XrtBot, CtxLimitBot và so khớp tương tự |
| 3 | Lệnh Telegram và hiểu ý qua AI. Test gateway |
| 4 | Tài liệu, bản build, cách triển khai lên VPS |
