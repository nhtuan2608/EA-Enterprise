# Telegram Gateway v1 (05/10/2026)

Trạng thái: **IMPLEMENTED (G19, REQ-018–020)**. Cụ thể hoá `TELEGRAM_CONTROL_SPEC.md` thành bản chạy được. Gồm:
- EA: `Integration/RemoteModeRuntime.mqh` (chế độ entry của operator, hàng đợi lệnh từ xa), dùng lại bộ kiểm tra thuần `Integration/RemoteModeGate.mqh`.
- Gateway: `bridge/telegram_gateway.py` (Python, chỉ thư viện chuẩn), `bridge/run_telegram.ps1`, `bridge/telegram-gateway.service`, mẫu cấu hình `bridge/telegram.example.json`.
- AI Bridge: `ASK_AI` trả lời câu hỏi của operator.
- Test: `Tests/telegram_gateway_tests.py`, `Tests/remote_mode_runtime_tests.py`.

## 1. Quyết định của người dùng (05/10)
| # | Điểm | Chốt |
|---|---|---|
| O-11 | Người dùng | 1 operator (được pause/resume) + viewer tuỳ chọn (chỉ xem, hỏi AI). Chỉ chat riêng; kiểm tra cả `chat.id` và `from.id` |
| O-12 | `/pause` | Chặn entry mới; vị thế, lệnh chờ và Trade Manager vẫn chạy bình thường |
| O-13 | AI tự pause/resume | Không. AI không bao giờ tạo lệnh trạng thái; câu trả lời AI chỉ là văn bản |
| O-14 | Nơi chạy gateway | Cùng máy MT5, long polling `getUpdates`, không mở cổng vào |
| O-15 | Dữ liệu gửi ra | Số liệu làm tròn; không gửi số tài khoản, tên server, token; fingerprint tài khoản chỉ dùng nội bộ |
| N1 | Thông báo chủ động | Vào/chốt một phần/đóng lệnh; cảnh báo hệ thống; báo cáo AI hằng ngày; tin HIGH sắp tới |

## 2. Quyết định kỹ thuật (mặc định của bản v1)
| # | Điểm | Chọn | Lý do |
|---|---|---|---|
| T1 | Khởi động lần đầu khi chưa có `current/operator_mode.json` | Tạo trạng thái **RUNNING** (version 1) và ghi audit `OPERATOR_MODE_BOOTSTRAP` | Chưa có lệnh từ xa nào từng được phát; nếu mặc định PAUSED thì EA ngừng vào lệnh ngay khi gắn lại mà chưa có gateway để resume |
| T2 | File có nhưng hỏng / sai account / sai config | **PAUSED** (fail closed), lý do `OPERATOR_MODE_UNREADABLE` hoặc `..._IDENTITY_MISMATCH`; operator dùng `/resume` để mở | Đúng đặc tả: hỏng thì đóng |
| T3 | Kênh gateway → EA | File trong `MQL5/Files/EnterpriseEA/current/remote/` (commands, results) | Cùng máy (O-14). Mô hình tin cậy: tài khoản Windows của người dùng là ranh giới tin cậy; tiến trình khác dưới cùng tài khoản coi như tin cậy. Không có khoá ký ở v1 (ghi trong giới hạn) |
| T4 | Nonce `/resume` | Gateway tạo 6 chữ số ngẫu nhiên (`secrets`), TTL 120 s; EA lưu nonce, chat, user và kiểm tra khi `/confirm` | Hai bước, ràng buộc cùng chat/user, hết hạn ngắn |
| T5 | Token | Biến môi trường `EEA_TELEGRAM_TOKEN` hoặc `token_file` ngoài repo; không bao giờ ghi vào log/reply; mọi log đi qua hàm che token |  |
| T6 | `/ask` | Gateway ghi request `ASK_AI` (`tg-…`) vào `ai/requests`, câu hỏi nằm trong `context.operator_question` (dữ liệu, không phải chỉ dẫn); AI Bridge trả lời như mọi request; gateway gửi lại vào đúng chat, trả lời đúng tin nhắn | Dùng lại hạn mức, circuit breaker, kiểm tra JSON của bridge. EA chỉ đọc response của request do nó tạo nên không tranh chấp |
| T7 | Giới hạn | 20 lệnh/phút mỗi người; `/ask` 6 lần/giờ; câu hỏi ≤ 500 ký tự; tin trả lời ≤ 3.500 ký tự; gửi lại tối đa 5 lần với backoff | TC-TG-07 |

## 3. EA: chế độ entry của operator
- `current/operator_mode.json` lưu toàn bộ `EEA_RemoteModeState` (paused, account, config, state_version, last sequence/update/command, nonce đang chờ). Ghi nguyên tử.
- Mỗi lượt timer: đọc lệnh trong `current/remote/commands/*.json` (theo tên file), dựng `EEA_RemoteCommand`, thu bằng chứng an toàn, gọi `EEA_EvaluateRemoteModeCommand`.
  - Hợp lệ → ghi trạng thái mới; chỉ khi ghi thành công mới áp dụng (`applied=true`).
  - Kết quả ghi vào `current/remote/results/<command_id>.json`: `accepted`, `applied`, `state_before`, `state_after`, `reason_codes`, `ea_state_version`, `observed_at_utc`. File lệnh được xoá sau khi có kết quả.
  - Audit: `REMOTE_COMMAND_APPLIED` / `REMOTE_COMMAND_REJECTED`.
- 7 bằng chứng cho `CONFIRM_RESUME`:

| Bằng chứng | Nguồn |
|---|---|
| reconciled | runtime `OBSERVING` |
| risk gate | risk ledger có vốn ban đầu; không ở trạng thái recovery blocked |
| news gate | không symbol nào `UNKNOWN` |
| broker | `TERMINAL_CONNECTED` |
| quyền MT5 | `TERMINAL_TRADE_ALLOWED` và `MQL_TRADE_ALLOWED` |
| bảo vệ vị thế | Trade Manager không ở lỗi đọc/ghi |
| độ mới | runtime refresh trong 120 s |

- Khi PAUSED: lượt vào lệnh không chạy, lý do `OPERATOR_PAUSED_ENTRIES` (sổ candidate ghi `NOT_EVALUATED:OPERATOR_PAUSED_ENTRIES`). Trade Manager, lệnh chờ đang có và News Guard vẫn chạy.
- Tab Overview, ô "New entries": `PAUSED by operator` khi đang dừng.

## 4. Gateway
- Vòng lặp: `getUpdates` (long poll 25 s, `allowed_updates=["message"]`) → xử lý → gửi kết quả lệnh/AI đã sẵn sàng → thông báo chủ động → lưu trạng thái.
- Trạng thái bền `<root>/telegram/state.json`: `offset`, `gateway_sequence`, 500 `update_id` gần nhất, lệnh và câu hỏi đang chờ kết quả, hàng gửi đi, con trỏ đọc audit, báo cáo AI và tin đã thông báo.
- Xác thực (TC-TG-01): chỉ `chat.type == "private"`, `chat.id == from.id`, `from.id` có trong `operators` (vai trò OPERATOR) hoặc `viewers` (VIEWER). Không dùng username. Người lạ không nhận được trả lời (chỉ ghi log).
- Lệnh:

| Lệnh | Vai trò | Hành vi |
|---|---|---|
| `/start`, `/help` | cả hai | danh sách lệnh theo vai trò |
| `/status` | cả hai | trạng thái từ file EA: chế độ operator (theo EA), runtime, phiên live, số vị thế/lệnh, equity làm tròn, News Guard, sentiment, AI Bridge, thời điểm snapshot; quá 120 s thì ghi `STALE` |
| `/pause` | operator | ghi `PAUSE_ENTRIES`; trả "đã nhận", sau đó trả kết quả EA thật |
| `/resume` | operator | ghi `REQUEST_RESUME` kèm nonce; khi EA chấp nhận mới gửi nonce cho người dùng |
| `/confirm <nonce>` | operator | ghi `CONFIRM_RESUME`; trả kết quả EA kèm lý do |
| `/ask <câu hỏi>` | cả hai | ACK, tạo request AI, gửi câu trả lời khi có; quá 180 s báo timeout |

- `RUNNING`/`PAUSED` chỉ được báo theo `operator_mode.json` và kết quả EA, không suy ra từ ACK của gateway (TC-TG-08). Lệnh không có kết quả sau 90 s → báo "EA chưa xác nhận (EA có thể không chạy)".
- Thông báo chủ động (đọc `logs/audit.jsonl` từ con trỏ, có xử lý xoay vòng file):
  - **Lệnh:** `TRADE_ENTERED`, `TRADE_MANAGEMENT` (chốt một phần, hoà vốn, trailing), `TRADE_EXITED`, `TRADE_NOT_FILLED`. Kèm symbol, setup, khung, MFE/MAE.
  - **Hệ thống:** `EA_STOPPED`, `EXECUTION_UNKNOWN_RECOVERY_REQUIRED`, `RUNTIME_REFRESH_FAILED`, `INTERNAL_*_LOSS_LIMIT_REACHED`, `LIVE_SESSION_REVOKED`, `AI_CIRCUIT_OPEN`, `REMOTE_COMMAND_*`. Mỗi loại tối đa 1 lần/15 phút.
  - **Báo cáo AI:** response OK mới của `EA_DIAGNOSTICS` và `NEWS_DATA_REVIEW` (tóm tắt).
  - **Tin HIGH sắp tới:** từ `current/news_state.json`, 30 phút trước mỗi tin, mỗi tin một lần.

## 5. Kiểm thử (đối chiếu TC-TG-01..08)
| TC | Test |
|---|---|
| 01 | Người lạ, group, `chat.id ≠ from.id`, viewer gọi `/pause` → từ chối, không ghi lệnh |
| 02 | Cùng `update_id` hai lần → xử lý một lần; `gateway_sequence` tăng đơn điệu và bền qua khởi động lại |
| 03 | `/confirm` sai nonce, nonce hết hạn, chat/user khác → EA từ chối (oracle gate sẵn có + test nguồn EA); bằng chứng an toàn thiếu → từ chối |
| 04 | Câu trả lời AI chứa "resume" → chỉ gửi văn bản, không có file lệnh nào được tạo |
| 05 | `/ask` → ACK, request có `operator_question`; trả lời đúng chat và `reply_to`; lỗi/timeout của AI → tin lỗi có mã |
| 06 | Khởi động lại gateway → `offset`, `gateway_sequence`, lệnh đang chờ được phục hồi; EA thiếu file chế độ → bootstrap RUNNING, file hỏng → PAUSED |
| 07 | Rate limit, câu hỏi dài bị cắt, ký tự đặc biệt không phá định dạng (gửi văn bản thuần), token không xuất hiện trong log |
| 08 | `/status` đọc chế độ từ file EA; ACK không bao giờ ghi "RUNNING" |

Thêm: thông báo từ dòng audit mẫu; tin HIGH 30 phút; báo cáo AI mới; xoay vòng audit không làm mất/lặp dòng.

## 6. Giới hạn v1
- Kênh file không có chữ ký (T3).
- Chưa diễn tập mất mạng/khởi động lại trên máy thật và chưa paper soak như đặc tả yêu cầu trước khi dùng điều khiển trên live: tài khoản hiện là demo.
- Kết quả lệnh đóng chưa có R/tiền thực hiện (Trade Manager chưa ghi), thông báo hiển thị MFE/MAE.

## 7. Kế hoạch triển khai
1. EA: `RemoteModeRuntime.mqh` (lưu/đọc trạng thái, bootstrap, hàng đợi lệnh, bằng chứng, kết quả, audit); chặn lượt vào lệnh khi PAUSED; ô Overview.
2. AI Bridge: `ASK_AI` dùng `operator_question` nếu có.
3. Gateway `telegram_gateway.py` + script chạy + service + mẫu cấu hình + README.
4. Test Python (gateway với Telegram giả, EA bằng test nguồn), compile 0/0, toàn bộ test.
5. Người dùng: tạo bot qua @BotFather, lấy `user_id`, đặt token, chạy gateway; deploy EA (cùng lần gắn lại EA đang chờ).
