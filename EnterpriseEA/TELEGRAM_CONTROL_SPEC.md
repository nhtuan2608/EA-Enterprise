# Đặc tả bổ sung Telegram điều khiển EA và hỏi AI

Trạng thái: **PROPOSED cho tích hợp runtime**. Tài liệu này bổ sung yêu cầu người dùng ngày 30/09/2026 vào đặc tả v1.2. Phạm vi là một Telegram bot làm kênh điều khiển và hỏi đáp từ xa; EA trong MT5 vẫn quyết định giao dịch và quản lý vị thế. Đã có schema, fixture và module kiểm tra command thuần ở mức offline; chưa có Telegram Gateway, kết nối AI/MCP thực, quyền điều khiển trong EA shell hoặc quyền giao dịch mới.

## Quyết định kiến trúc đề xuất

Telegram Bot API → Telegram Gateway trên máy chạy MT5/bridge → hàng đợi command và AI request có audit → EA command validator hoặc MCP AI Bridge → reply queue → Telegram Bot API. Gateway chỉ xác thực, chuyển tiếp, giới hạn quyền, xếp hàng, gửi kết quả; không phân tích thị trường và không gọi trực tiếp hàm giao dịch. AI chỉ đọc context nằm trong allowlist, trả lời hoặc đưa khuyến nghị theo schema. Mọi thay đổi trạng thái EA đi qua cùng command validator dùng cho dashboard, không qua câu trả lời tự do của AI.

Ưu tiên `getUpdates` long polling cho gateway chạy trên máy được phép chạy MT5: không cần mở webhook công khai. Chỉ một consumer được dùng bot token; lưu `update_id` đã xử lý để chống lặp. Webhook HTTPS là phương án sau nếu có hạ tầng được duyệt. `WebRequest` của MQL5 là đồng bộ, cần URL allowlist và không chạy trong Strategy Tester, nên EA không gọi Telegram hoặc CLI trong `OnTick`; gateway/bridge xử lý bất đồng bộ. Telegram không được dùng để bật nút AutoTrading toàn terminal; `RUNNING` chỉ có nghĩa **EA này được phép xét entry mới** sau các gate, không có nghĩa MT5 đã cấp quyền giao dịch.

## Vai trò và quyền

| Vai trò | Xem trạng thái và hỏi AI | Tạm dừng entry mới | Bật lại entry mới | Lệnh giao dịch |
| --- | --- | --- | --- | --- |
| Telegram user chưa đăng ký | Không | Không | Không | Không |
| Viewer allowlist | Có, theo phạm vi dữ liệu được cấp | Không | Không | Không |
| Operator allowlist | Có | Có, qua command queue | Có, sau xác nhận và gate EA | Không trong baseline |
| AI Level 0/1 | Trả lời, cảnh báo, đề xuất | Không tự thực thi | Không | Không |
| AI Level 2 (nếu sau này được duyệt riêng) | Có | Có thể đề xuất hoặc tự đặt `PAUSE_ENTRIES` theo whitelist, TTL và audit | Không | Không |

Mặc định chỉ chat riêng tư với bot. Gateway kiểm tra đồng thời `chat_id` và `from.id` theo allowlist, không dựa vào username hoặc text tự khai. Token bot, khóa provider và secret không nằm trong config source, prompt, log hay tin trả về; gateway dùng nơi lưu bí mật được máy đích cho phép. Telegram account bị chiếm quyền có thể phát lệnh thay chủ tài khoản, nên một lệnh `RESUME_ENTRIES` cần xác nhận hai bước, nonce một lần, TTL ngắn và kiểm tra lại trạng thái tại EA. Không chuyển dữ liệu tài khoản chi tiết cho AI hoặc Telegram nếu không cần cho câu trả lời.

## Chế độ EA và lệnh Telegram

`PAUSED_ENTRIES` chặn **entry mới và tăng rủi ro**; EA tiếp tục theo dõi, giữ protective stop và quản lý an toàn vị thế hiện có theo policy. `RUNNING` chỉ gỡ chặn do operator đặt; Risk Kernel, FTMO, news, broker, config, reconcile và quyền MT5 vẫn có thể chặn entry. `SAFE_BLOCKED` là trạng thái do lỗi/risk gate; lệnh resume không được xóa trạng thái này. Restart phải phục hồi trạng thái pause đã lưu; thiếu hoặc hỏng checkpoint thì fail closed. Lệnh pause được ưu tiên xử lý nhưng vẫn phải qua xác thực, idempotency và audit. Nếu gateway offline, EA tiếp tục trạng thái cuối đã xác nhận, không tự resume.

| Lệnh | Hành vi | Reply bắt buộc |
| --- | --- | --- |
| `/status` | Đọc trạng thái EA, AI, bridge, broker/reconcile và thời điểm snapshot | Dữ liệu có timestamp, trạng thái stale/unknown |
| `/pause` | Operator yêu cầu `PAUSE_ENTRIES`; không hủy hoặc đóng lệnh hiện có | ACK đã nhận, sau đó kết quả EA đã áp dụng hoặc từ chối |
| `/resume` | Operator tạo yêu cầu bật lại; gateway gửi nonce xác nhận riêng | Chưa đổi trạng thái cho đến khi xác nhận |
| `/confirm <nonce>` | Xác nhận một lần, cùng user/chat, còn TTL; EA chạy lại toàn bộ gate | Trạng thái áp dụng thực tế và reason codes |
| `/ask <câu hỏi>` | Tạo AI request chỉ đọc theo scope được chọn | ACK và câu trả lời hoặc timeout/error rõ ràng |
| `/help` | Liệt kê lệnh theo vai trò | Không lộ token hoặc thông tin nhạy cảm |

Ngôn ngữ tự nhiên như “bật bot” chỉ được AI diễn giải thành **đề xuất command**; gateway yêu cầu operator chọn lệnh chuẩn và xác nhận. Tin nhắn ngoài cú pháp không tự chuyển thành command. Không có `close`, `partial`, `BE`, `trail`, đổi risk/config, sửa source, chạy shell hoặc gọi công cụ MCP tùy ý qua Telegram trong baseline. Có thể mở rộng bằng đặc tả và gate riêng.

## Hỏi AI và gửi reply

Bot có thể tự gửi reply qua `sendMessage` sau khi người dùng đã bắt đầu chat với bot, bot token hợp lệ, gateway online và chat được phép. `/ask` tạo `request_id` và ACK ngay; bridge xử lý bất đồng bộ, chỉ đọc context/snapshot được EA xuất, kiểm tra schema/TTL, rồi gateway gửi câu trả lời gắn `request_id` và `reply_to_message_id`. Câu trả lời phải phân biệt dữ liệu quan sát, suy luận AI, thời điểm snapshot và tình trạng không đủ dữ liệu. Không trình bày dự đoán như chắc chắn hoặc ngầm coi AI reply là quyết định giao dịch. Nếu AI timeout/offline, trả lỗi có mã và không thay đổi EA. Nếu Telegram gửi reply lỗi, lưu trạng thái delivery và retry có giới hạn; không chạy lại command vì gửi tin lỗi.

Gateway chỉ đưa vào prompt nội dung Telegram đã escape/giới hạn kích thước và context nằm trong allowlist; nội dung chat, headline hay file đính kèm là dữ liệu, không phải instruction. Không cho AI quyền tự tìm file ngoài scope, gọi shell, sửa config, bật MT5 AutoTrading, gửi lệnh hoặc gửi tin chủ động ngoài kết quả request/cảnh báo đã cấu hình. Chặn flood, giới hạn số request đồng thời, token budget và retention. Có thể bật notification chủ động theo loại sự kiện được operator đăng ký; tách khỏi reply theo `/ask`.

## Hợp đồng command và audit tối thiểu

Command envelope: `schema_version`, `command_id`, `telegram_update_id`, `chat_id`, `telegram_user_id`, `role`, `action`, `issued_at_utc`, `expires_at_utc`, `account_id` opaque, `config_version`, `expected_ea_state_version`, `confirmation_nonce` (nếu resume), `correlation_id`. Gateway ký/xác thực envelope theo kênh nội bộ phù hợp; EA xác thực nguồn, TTL, account/config binding, sequence và quyền lần nữa. Không tin payload chỉ vì nó nằm trong file queue. Kết quả: `command_id`, `accepted`, `applied`, `state_before`, `state_after`, `reason_codes`, `ea_state_version`, `observed_at_utc`.

AI request/reply envelope: `request_id`, `telegram_update_id`, `chat_id`, `user_id`, `request_type`, `question`, `context_scope`, `created_at_utc`, `deadline`, `context_snapshot_ids`, `provider`, `response_status`, `answer`, `evidence_refs`, `delivered_at_utc`. Audit tách các bước `RECEIVED`, `AUTHORIZED`, `QUEUED`, `AI_COMPLETED`, `EA_APPLIED`/`EA_REJECTED`, `TELEGRAM_DELIVERED`/`DELIVERY_FAILED`. Log cần redaction token, prompt, account ID theo policy retention. Một `command_id` hoặc `telegram_update_id` đã xử lý không được gây side effect lần hai.

## Kiểm thử và cổng triển khai

Traceability: `REQ-018` Telegram gateway xác thực và chuyển tiếp lệnh/reply; `REQ-019` chế độ EA `PAUSED_ENTRIES`/`RUNNING` với resume hai bước và fail closed; `REQ-020` hỏi đáp AI bất đồng bộ qua Telegram với scope, TTL và delivery audit. Các yêu cầu này là bổ sung sau REQ-017 của đặc tả v1.1.

- `TC-TG-01`: user/chat ngoài allowlist, group, username trùng, update giả hoặc mất quyền đều bị từ chối.
- `TC-TG-02`: `/pause` lặp hoặc update Telegram gửi lại chỉ đổi trạng thái một lần; vị thế cũ vẫn được bảo vệ.
- `TC-TG-03`: `/resume` thiếu/sai/hết hạn nonce, khác user/chat, khác account/config, stale state version hoặc risk/reconcile/news unknown đều bị từ chối.
- `TC-TG-04`: AI trả “resume/enable/trade” trong prose hoặc JSON ngoài whitelist không đổi trạng thái EA.
- `TC-TG-05`: `/ask` nhận ACK rồi reply đúng chat/request; timeout/malformed/injection/AI offline cho reply lỗi, không đổi trading state.
- `TC-TG-06`: gateway, Telegram hoặc PC restart; offset, queue, pause state và delivery được phục hồi hoặc fail closed, không mất lệnh đã ACK và không tự resume.
- `TC-TG-07`: rate limit, nhiều request đồng thời, nội dung dài, Markdown escape, token không xuất hiện trong log/reply.
- `TC-TG-08`: trạng thái Telegram khác trạng thái thực tế MT5/EA được báo rõ; chỉ báo `RUNNING` sau khi EA xác nhận, không suy từ ACK của gateway.

Phase thiết kế: thêm schema và threat model sau Phase 1, mock gateway/Telegram ở Phase 7 cùng MCP Level 0; chỉ thử `/status` và `/ask` trong observer/paper. Thêm `/pause` rồi `/resume` sau khi command queue, persisted mode, reconciliation và runtime MT5 được kiểm chứng. Không mở điều khiển Telegram trên live trước paper soak, security review và diễn tập mất mạng/restart. Máy hiện tại không cần cài MT5 để thiết kế schema/fixture; các gate runtime phải chạy sau trên máy được phép.

Tiến độ offline: `Integration/RemoteModeGate.mqh` hiện chỉ đánh giá lệnh `PAUSE_ENTRIES`, `REQUEST_RESUME`, `CONFIRM_RESUME` và xuất `VALIDATED_PENDING_COMMIT`; không tự lưu state hoặc gửi reply. `schemas/remote-command.schema.json`, `schemas/telegram-ai-request.schema.json`, `schemas/telegram-ai-reply.schema.json` và fixture/test Python kiểm tra các trường hợp tổng hợp. Xem `Integration/REMOTE_MODE_GATE_OFFLINE.md` để biết trust boundary và phần còn thiếu. Các quyết định O-11 đến O-15 được dùng làm mặc định cho prototype offline, chưa phải cấu hình live được khóa.

## Quyết định cần người dùng chốt trước khi code Telegram

1. `O-11`: Bot chỉ dùng chat riêng một operator hay có nhiều operator/viewer? Đề xuất: một operator và một viewer optional.
2. `O-12`: `/pause` có chặn entry mới nhưng tiếp tục quản lý vị thế hiện có không? Đề xuất: có.
3. `O-13`: Có cho AI Level 2 tự `PAUSE_ENTRIES` khi phát hiện rủi ro không? Đề xuất: **chưa trong baseline**, chỉ cảnh báo/đề xuất; xem xét sau paper evidence. AI không tự `RESUME_ENTRIES` ở mọi level.
4. `O-14`: Gateway chạy trên máy MT5 được phép hay máy bridge riêng? Đề xuất: cùng máy được phép ở bản đầu, long polling, không mở inbound port.
5. `O-15`: Những trường account/portfolio nào được phép hiển thị qua Telegram và gửi provider AI? Đề xuất: trạng thái/risk đã làm tròn, ẩn account number và thông tin định danh.

Nguồn kỹ thuật: Telegram Bot API <https://core.telegram.org/bots/api>, Telegram bot introduction <https://core.telegram.org/bots>, MQL5 WebRequest <https://www.mql5.com/en/docs/network/webrequest>, MQL5 Strategy Tester limitations <https://www.mql5.com/en/docs/runtime/testing>. Các quyết định quyền và fail closed ở trên là đề xuất thiết kế cho dự án, không phải tính năng Telegram/MT5 cấp sẵn.
