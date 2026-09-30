# Đặc tả bổ sung vòng đời lệnh chờ theo setup

Trạng thái: **yêu cầu vòng đời đã xác nhận; ngưỡng thời gian và adapter broker còn PROPOSED**. Bổ sung yêu cầu người dùng ngày 30/09/2026 vào đặc tả v1.3. Phạm vi gồm BUY/SELL LIMIT và BUY/SELL STOP do EA tạo. Lệnh STOP LIMIT là loại hai giai đoạn, cần đặc tả và broker fixture riêng trước khi bật. Mọi con số thời gian trong fixture là seed nghiên cứu, không phải cấu hình live đã chốt. Nhánh Telegram tiếp tục tạm dừng.

## Nguyên tắc bắt buộc

Lệnh chờ là một phần của setup, không phải đối tượng để treo vô thời hạn. Mỗi order intent phải bind `candidate_id`, `setup_id`, `setup_version`, `config_version`, symbol/broker/account, hướng, loại lệnh, vị trí entry/SL/target, risk reservation và hồ sơ thời gian. EA chỉ đặt lệnh nếu thời hạn setup và broker cho phép cơ chế hết hạn/hủy có thể kiểm tra. Không dùng GTC như cách thay thế ngầm cho thời hạn chiến lược.

Tại lúc đặt, lưu `candidate_triggered_at_utc`, `submitted_at_utc`, `broker_accepted_at_utc`, `placed_after_closed_bar_sequence`, `setup_valid_until_utc`, `session_end_at_utc`, `broker_expiration_at_utc`, `max_wait_closed_bars`, `effective_expires_at_utc = min(các mốc UTC hợp lệ)`, trạng thái setup, `order_ticket` khi có, và nguồn/timezone của từng mốc. Nếu không xác định được bất kỳ mốc bắt buộc, order intent bị chặn. Hồ sơ SCALP và SWING có thời gian khác nhau, gắn với setup/symbol/session; không dùng một TTL chung cho mọi lệnh. Thời hạn server và thời hạn chiến lược được theo dõi riêng. UTC được dùng trong state; adapter xác nhận session/broker timezone và DST. Đồng hồ setup bắt đầu khi candidate chuyển `TRIGGERED`; số nến chờ bắt đầu sau nến đóng dùng để tạo order intent, không reset khi partial fill hay restart.

Ma trận cấu hình bắt buộc cho từng `(setup_id, setup_version, trade_style, canonical_symbol, session_profile, order_type)` gồm: `setup_ttl_seconds`, `max_wait_closed_bars`, nguồn session end, giới hạn dịch chuyển giá/spread/cost, quy tắc vô hiệu hóa cấu trúc, và chính sách remainder sau partial fill. Chỉ lấy cấu hình đã version hóa; không để AI hay message từ Telegram sửa các ngưỡng này khi lệnh đang treo. Giá trị cụ thể của SCALP/SWING phải được hiệu chuẩn từ fixture và paper data trước khi khóa cho live.

## Khi nào hủy phần còn chờ

EA yêu cầu hủy phần volume còn treo tại **điều kiện đến sớm nhất**: đã tới `effective_expires_at_utc`; số nến hoàn tất chờ lệnh đạt `max_wait_closed_bars`; setup bị INVALIDATED/EXPIRED hoặc vùng entry không còn ý nghĩa; session kết thúc; news/risk/FTMO/account policy chuyển sang chặn entry; instrument spec/config đổi; hoặc giá/spread/cost lệch khỏi premise đã định. Các điều kiện thị trường phải có evidence/snapshot mới, không suy từ AI prose. Thời hạn không được tự gia hạn. Muốn đặt lại phải tạo candidate và order intent mới, có quote/risk mới và audit liên kết intent cũ.

Đánh giá điều kiện hủy trên mỗi nến đóng của timeframe setup, khi có quote/risk/news/config update liên quan, và bằng timer độc lập ở deadline UTC. Nếu feed hoặc snapshot thiếu/stale, chuyển sang `CANCEL_REQUIRED` hoặc `PENDING_RACE_UNKNOWN` theo khả năng xác định order hiện hành; chặn entry mới. Không chờ nến tiếp theo khi deadline đã tới. Một order đã full fill không còn remainder để hủy; quản lý vị thế đã khớp theo Trade Manager.

`CANCEL_REQUIRED` hoặc `CANCEL_REQUESTED` vẫn **giữ risk reservation cho volume còn treo** cho tới khi broker xác nhận hủy/hết hạn hoặc lịch sử order/deal chứng minh không còn khả năng khớp. Gửi yêu cầu hủy phải idempotent theo ticket và correlation ID; response gửi thành công chưa phải xác nhận đã hủy. Lỗi mạng, timeout, terminal restart hoặc lệnh hủy chưa được ACK phải giữ trạng thái unknown/block new entries và retry/reconcile; không giải phóng risk chỉ vì local clock đã hết hạn. Giữ quản lý protective positions đã khớp.

## Limit, Stop, partial fill và race

- BUY/SELL LIMIT: kiểm tra entry đúng phía giá thực thi, stop/freeze/min distance, spread và session theo broker spec tại đặt và trước khi giữ lệnh. Khi giá đi xa khiến setup hết hiệu lực, hủy thay vì chờ quay lại vô hạn.
- BUY/SELL STOP: kiểm tra breakout/acceptance và thời gian valid của trigger. Nếu lệnh không kích hoạt trong cửa sổ setup hoặc thị trường chuyển regime, hủy; không biến tín hiệu cũ thành entry muộn.
- Partial fill: phần đã khớp trở thành vị thế/virtual position với fill time, giá, chi phí và initial risk riêng; phần chưa khớp giữ TTL ban đầu và reservation riêng. Hết hạn hoặc setup invalidation hủy **phần còn lại**, không tự đóng phần đã khớp. Trade Manager xử lý phần đã khớp theo policy của position.
- Fill và cancel gần cùng timestamp: không giả định thứ tự từ local clock. Reconcile order/deal history, ticket, sequence và broker state; nếu thiếu bằng chứng thì `PENDING_RACE_UNKNOWN`, block entry mới và bảo vệ vị thế. Một fill đến sau thời điểm hết hạn vẫn phải được ghi nhận và đánh dấu breach/review, không được bỏ qua để làm đẹp sổ risk.
- Lệnh STOP LIMIT cần theo dõi thời điểm trigger và thời hạn riêng cho LIMIT thứ cấp; chưa thuộc prototype đầu tiên.

MT5 có loại BUY/SELL LIMIT, BUY/SELL STOP và các time-in-force GTC, DAY, SPECIFIED, SPECIFIED_DAY. `ORDER_TIME_EXPIRATION`, `ORDER_TIME_SETUP`, `ORDER_TIME_DONE`, `ORDER_VOLUME_CURRENT` và `ORDER_STATE` là bằng chứng broker cần đọc khi triển khai. Broker có thể hỗ trợ khác nhau; adapter phải xác minh loại expiration thực tế và không suy rằng local cancel đã được broker chấp nhận. Nguồn: <https://www.mql5.com/en/docs/constants/tradingconstants/orderproperties>, <https://www.mql5.com/en/docs/constants/structures/mqltraderequest>.

## State và audit

State tối thiểu: `CREATED → WORKING → PARTIAL/FILLED`, hoặc `CANCEL_REQUIRED → CANCEL_REQUESTED → CANCELLED/EXPIRED`; `BREACH_REVIEW` và `PENDING_RACE_UNKNOWN` là nhánh cần reconcile. `PARTIAL` có thể chuyển sang `CANCEL_REQUIRED`; `CANCEL_REQUESTED` vẫn có thể nhận fill trước xác nhận cuối. Theo dõi `bars_waited`, `last_closed_bar_sequence`, `last_setup_snapshot_id`, `effective_expires_at_utc`, `remaining_volume`, `filled_volume`, `risk_reserved_for_remaining`, `filled_initial_risk`, `cancel_reason`, `cancel_requested_at_utc`, `broker_confirmed_at_utc`. Bất biến `requested_volume = filled_volume + cancelled_volume + remaining_volume` được kiểm tra với volume step/tolerance của symbol. Mỗi transition ghi `event_id`, order/candidate ID, config/setup version, timestamp UTC, broker snapshot/ticket, state before/after và reason code; xử lý duplicate/out-of-order idempotent hoặc fail closed.

Deadline phải được kiểm tra cả trên closed bar lẫn timer/clock độc lập để khi không có nến mới vẫn yêu cầu hủy đúng hạn. Nếu máy/terminal offline tại deadline, ngay khi khôi phục phải reconcile orders/deals trước khi quyết định trạng thái; không coi lệnh đã tự hết hạn. Lưu checkpoint order và deadline để restart không làm mới thời gian chờ.

## Traceability, test và plan

`REQ-021`: vòng đời pending order gắn với setup, chiến lược, broker và thời hạn; cancel/reconcile phần còn treo. Liên quan REQ-005/006/011/016/017, Phase 3 risk và Phase 4 Virtual Trader/Trade Manager.

- `TC-046`: LIMIT/STOP chưa fill hết `max_wait_closed_bars` hoặc UTC deadline phải chuyển `CANCEL_REQUIRED`, không tự fill về sau.
- `TC-047`: setup invalidated, session/news/risk block, config/spec đổi phải yêu cầu hủy trước TTL.
- `TC-048`: partial fill tại gần expiry giữ filled position riêng, hủy remainder, risk reservation chỉ giải phóng sau confirm.
- `TC-049`: fill và cancel/expire race, duplicate, broker reject/timeout, offline/restart không làm mất fill hoặc đếm risk hai lần.
- `TC-050`: SCALP/SWING có profile khác, broker time-in-force hỗ trợ khác nhau, DST/session end và no-new-bar timer.
- `TC-051`: stale setup hoặc giá/spread/cost drift chặn đặt lại; re-entry cần candidate/intent và quote/risk mới.

Plan: (1) chốt profile TTL per setup/style/symbol/session và broker expiration capability trong Phase 0/3; (2) thêm state machine + fixture offline cho LIMIT/STOP, deadline, partial và cancel race trong Phase 4; (3) làm broker adapter đọc active orders, deals, history, OnTradeTransaction/timer và persisted checkpoint; (4) chạy MT5 Strategy Tester/paper với các TC trên, kể cả restart/offline; (5) chỉ bật Paper/Live sau khi risk/account ledger reconcile và audit chứng minh hủy thật. Không có MT5 trên máy hiện tại nên code offline chỉ là thiết kế và oracle.

Quyết định còn mở: giá trị `setup_ttl_seconds` và `max_wait_closed_bars` cho từng profile SCALP/SWING; ngưỡng drift khiến entry không còn hợp lệ; quy tắc giữ/hủy remainder sau partial fill; broker nào hỗ trợ `ORDER_TIME_SPECIFIED` và độ trễ cancel/reconcile trong tình huống mất kết nối. Đề xuất mặc định: clock setup bắt đầu khi candidate TRIGGERED, order timer bắt đầu khi broker chấp nhận; hiệu lực cuối lấy mốc sớm nhất, và nếu không đảm bảo hủy có thể xác nhận thì không đặt pending order live. Những giá trị mở này không ngăn xây state machine offline, nhưng chặn Paper/Live.
