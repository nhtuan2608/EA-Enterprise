# Bots trong EnterpriseEA — hướng dẫn dùng

Nhánh `feature/bots-host`. Thiết kế: `docs/superpowers/specs/2026-10-16-bots-host-design.md`.

EnterpriseEA chạy 4 chiến lược trên **cùng một tài khoản và một portfolio**:

| Bot | Code | Magic | Nguồn | Mặc định |
|---|---|---|---|---|
| S07 | `S07` | `InpLiveMagic` (888888 / 707707) | Engine S07 có sẵn của EnterpriseEA | Theo `InpS07Mode` |
| VHedge G119 | `VHEDGE` | 116119 | Chuyển từ VHedgeTester (chỉ G119, BIGV tắt) | SHADOW, 0,75%/chân |
| XauRegime | `XRT` | 969696 | Chuyển từ XauRegimeTester (chỉ mua, vào market đầu ngày) | SHADOW, 1,5% |
| CtxLimit | `CTXLIMIT` | 717171 | Chuyển từ CtxLimitTester (kế hoạch L, cổng S07) | SHADOW, 0,5% × trọng số |

## Active / Inactive

- **Inactive** = bot **không vào lệnh mới**. Lệnh đang mở và limit đã đặt vẫn được quản lý (stop, TP, trailing, thoát theo luật) cho tới khi đóng hết.
- **Trạng thái được lưu** ở `MQL5\Files\EnterpriseEA\current\bots_state.json`, gắn với tài khoản và config.
  - Lần đầu chạy: lấy Active theo input `InpBot…Active`.
  - File hỏng, hoặc thuộc tài khoản/config khác: mọi bot Inactive cho tới khi bật lại.
- **Trên chart:** Settings → tab **Bots**.
  - Bấm `ACTIVE` để tắt (1 lần bấm).
  - Bấm `INACTIVE` → nút đổi thành `Confirm ON` → bấm lần nữa trong 10 giây để bật.
- **Từ Telegram:**

| Lệnh | Tác dụng |
|---|---|
| `/bots` | Danh sách bot, chế độ, lệnh mở, lãi/lỗ hôm nay, trạng thái Guard |
| `/bot off vhedge` | Tắt ngay |
| `/bot on vhedge` | Nhận mã 6 số → gửi `/confirm <mã>` trong 2 phút |
| Nhắn tự nhiên, ví dụ "tắt VHedge đi", "bật lại s07" | AI dịch thành lệnh chuẩn và báo "AI hiểu là: …". Tắt áp dụng ngay; bật vẫn cần `/confirm` |

Tên bot chấp nhận: `s07`, `vhedge` (hoặc `g119`, `hedge`), `xrt` (hoặc `xauregime`), `ctxlimit` (hoặc `ctx`).

## SHADOW và LIVE

| Chế độ | Hành vi |
|---|---|
| **SHADOW** | Lệnh ảo: không gửi lệnh, chỉ ghi trạng thái. VHedge còn ghi `MQL5\Files\VHedge_<symbol>_116119.csv` như bản tester |
| **LIVE** | Lệnh thật. Chỉ vào khi qua đủ các cổng dưới đây |

**Các cổng của chế độ LIVE:**
1. **EA đã ARM:** `InpObserverOnly=false`, `InpExecutionEnabled=true`, `InpLiveTradeArmed=true`.
2. **Có phiên live đang ACTIVE** (Settings → Authorization, ký 24h/7d), giống S07. Tắt yêu cầu này bằng `InpBotsRequireLiveSession=false`.
3. **Không bị `/pause`, không có kill switch hay khóa recovery.**
4. **Portfolio Guard:**
   - Rủi ro mở toàn tài khoản (mọi magic) cộng lệnh mới ≤ `InpBotsMaxOpenRiskPct` (mặc định 12%) vốn ban đầu.
   - Lỗ trong ngày server < `InpBotsDailyLossPct` (6%).
   - Lệnh không có stop thì chặn (fail closed).
5. **Riêng từng bot:**
   - VHedge cần tài khoản **hedging**; tài khoản netting thì tự về SHADOW.
   - XauRegime dùng News Guard (SWING) và sentiment của EnterpriseEA.
   - CtxLimit giống bản tester: không có News Guard.

## Nhật ký bot (bot đã làm gì, vì sao)

EA ghi mỗi sự kiện của bot thành một dòng JSON trong `MQL5\Files\EnterpriseEA\logs\bots-YYYYMM.jsonl`. Mỗi tháng (theo UTC) một file. EA chỉ ghi nối thêm, thư mục `logs` tự tạo khi ghi dòng đầu.

```json
{"at_utc":1792195200,"server":"2026.10.16 21:00","bot":"XRT","event":"DECISION","mode":"LIVE","text":"kế hoạch ngày: chế độ D1 TĂNG ...","data":{"state":1,"atr":38.20,"plan":true}}
```

| event | khi nào |
|---|---|
| `START` | EA khởi động (chế độ từng bot) |
| `SWITCH` | bật/tắt bot trên bảng điều khiển hoặc qua Telegram |
| `DECISION` | XauRegime: kế hoạch đầu ngày. CtxLimit: dự báo mỗi giờ tròn (MUA/BÁN R, ngưỡng, kết quả) |
| `ENTRY` / `ORDER` | bot vào lệnh market / đặt limit, kể cả SHADOW |
| `MANAGE` | VHedge: một chân bị cắt, giữ chiều nào, có bồi không |
| `EXIT` | bot thoát lệnh. SHADOW ghi kết quả bằng R (VHedge bằng U) |
| `BLOCKED` | lệnh bị chặn (Guard, tin, sentiment, INACTIVE...). Chỉ ghi khi lý do đổi |
| `SKIP` | bỏ tín hiệu (VHedge không hồ sơ nào đạt, XauRegime giá đã chạy quá xa...) |
| `ERROR` | broker từ chối lệnh |
| `NEAR` | mỗi nến M30 đóng: từng bot còn thiếu gì, gần khớp bao nhiêu |
| `FILL` / `CLOSE` | deal thật trên broker theo magic của bot (cả S07), kèm tiền lãi/lỗ |

Đọc nhật ký:
- Telegram: `/botlog` (24 giờ, mọi bot), `/botlog xrt`, `/botlog vhedge 72` (tối đa 168 giờ). Có tóm tắt theo bot: số lần vào/thoát, R của lệnh ảo, tiền của lệnh thật, các lý do bị chặn, dòng gần khớp mới nhất. Sau đó là các dòng gần nhất (không gồm NEAR).
- Python: `bridge/bot_journal.py` (`read_journal`, `summarize`, `journal_text`). Gateway và MCP server dùng chung module này.

## Thử trước khi chạy thật

1. Build `EnterpriseEA.ex5` từ nhánh này.
2. Strategy Tester, XAUUSD, mô hình *Every tick based on real ticks*, 2–4 tuần gần đây. Để mọi bot ở SHADOW và giữ nguyên input. Kiểm tra:
   - log có các dòng `VHedgeBot: … restored` hoặc bot đi qua kỳ thử không lỗi;
   - `MQL5\Files\EnterpriseEA\current\bots_status.json` có đủ 4 bot;
   - file CSV của VHedge có nhóm lệnh. So với `VHedgeTester` chạy cùng kỳ ở SHADOW: các nhóm phải trùng.
3. Gắn lên chart demo, xem tab **Bots**, thử bật/tắt trên chart và qua Telegram (`/bots`, `/bot off vhedge`).
4. Chuyển từng bot sang LIVE trên tài khoản cent khi shadow đã khớp.

## Lưu ý khi đưa lên VPS

- **Không chạy song song bản tester cũ:** `S07Tester`, `VHedgeTester`, `XauRegimeTester`, `CtxLimitTester` trên cùng tài khoản dùng cùng magic với các bot (S07 thì khác magic nhưng vào lệnh trùng). Tháo chúng ra trước khi chạy EnterpriseEA có bot.
- **Telegram** chỉ điều khiển được terminal mà gateway đọc được thư mục `MQL5\Files\EnterpriseEA` của nó. Gateway và AI bridge hiện chạy trên máy Windows của bạn. Muốn điều khiển EA trên VPS thì phải chạy gateway/bridge trên VPS (có sẵn file service cho Linux trong `bridge/`).
